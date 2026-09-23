"""Bounded validation/recovery lanes for existing Deep Dive candidates.

A candidate that is already stored in Notion must not need to pass through fresh
acquisition/dedup again just because a publication gate or policy fingerprint changed.

Two deliberately different contracts live here:
- ``article_validation`` is read-only and may inspect Editorial Review, stale Ready,
  or Quality Failed;
- normal/full Production may recover Editorial Review first and then stale Ready,
  at most one candidate total, after fresh + Deferred + Pending Retry have had first
  access to article capacity.

A Ready row is recoverable here only when its persisted manuscript no longer satisfies
the current publication contract. Current-policy Ready remains terminal. Quality Failed
is intentionally not auto-recovered because it can represent Fact/Evidence HARD BLOCKs.
Pending Retry keeps its dedicated operational lane.
"""
from __future__ import annotations

from pending_retry_validation import classify_nonpersistent_report

import os
from typing import Any


DEFAULT_LIMIT = 1
DEFAULT_SCAN_LIMIT = 100
DEFAULT_REQUEST_BUDGET = 4
DEFAULT_FULL_RECOVERY_LIMIT = 1
DEFAULT_STALE_READY_PROBE_LIMIT = 5
_INSTALLED_ATTR = "_run277_existing_editorial_recovery_installed"


def _select_name(prop: dict[str, Any] | None) -> str:
    selected = ((prop or {}).get("select") or {})
    return str(selected.get("name") or "")


def _read_current_statuses(pipeline, page_id: str) -> tuple[str, str] | None:
    """Read current lifecycle state without changing the page."""
    try:
        response = pipeline.requests.get(
            f"https://api.notion.com/v1/pages/{page_id}",
            headers=pipeline._notion_headers(),
            timeout=10,
        )
    except Exception as exc:
        pipeline.logger.warning("[ARTICLE REVALIDATION STATUS READ FAILED] %s: %s", page_id, exc)
        return None
    if int(getattr(response, "status_code", 0) or 0) != 200:
        pipeline.logger.warning(
            "[ARTICLE REVALIDATION STATUS READ FAILED] %s HTTP %s",
            page_id,
            getattr(response, "status_code", 0),
        )
        return None
    props = (response.json() or {}).get("properties", {})
    return (
        _select_name(props.get(pipeline.PROP_ARTICLE_STATUS)),
        _select_name(props.get(pipeline.PROP_CONTENT_STATUS)),
    )


def select_revalidation_items(
    pipeline,
    limit: int = DEFAULT_LIMIT,
    scan_limit: int = DEFAULT_SCAN_LIMIT,
    *,
    include_quality_failed: bool = True,
    include_stale_ready: bool = False,
    prefer_stale_ready: bool = False,
    stale_ready_probe_limit: int = DEFAULT_STALE_READY_PROBE_LIMIT,
    exact_target: str = "",
    exclude_page_ids: set[str] | None = None,
):
    """Return existing Deep Dive rows that require current-gate revalidation.

    ``get_regen_test_items`` already reconstructs the source/candidate payload from
    Notion without screening or Stock writes. We deliberately scan a larger bounded
    window, then verify the *current* page lifecycle before selecting anything.

    Ready is included only when explicitly requested and only when the installed
    publication-contract predicate proves that no current-policy Ready manuscript exists.
    Missing/failed provenance checks fail closed and leave Ready terminal. When
    ``prefer_stale_ready`` is enabled, at most five Ready rows are provenance-probed
    before falling back to Editorial Review, bounding Notion read cost.
    """
    limit = max(0, int(limit))
    if limit == 0:
        return []
    scan_limit = max(limit, min(100, int(scan_limit)))
    rows = pipeline.get_regen_test_items(scan_limit, "")
    if rows is None:
        return None
    exact_target = str(exact_target or "").strip()
    if exact_target:
        rows = [row for row in rows if str((row.get("repo") or {}).get("nameWithOwner") or "").strip() == exact_target]
        if not rows:
            pipeline.logger.warning("[ARTICLE REVALIDATION EXACT TARGET MISS] %s", exact_target)
            return []

    editorial: list[dict] = []
    ready_candidates: list[tuple[dict, str, str]] = []
    stale_ready: list[dict] = []
    quality_failed: list[dict] = []
    for item in rows:
        page_id = str(item.get("notion_page_id") or "")
        if not page_id or page_id in (exclude_page_ids or set()):
            continue
        statuses = _read_current_statuses(pipeline, page_id)
        if statuses is None:
            continue
        article_status, content_status = statuses

        # Delay the more expensive manuscript-provenance read until after higher-priority
        # Editorial Review rows are known. If Editorial already fills the caller's limit,
        # no Ready block read is necessary at all.
        if article_status == pipeline.ARTICLE_STATUS_READY:
            if include_stale_ready:
                ready_candidates.append((item, article_status, content_status))
            continue

        # Pending Retry belongs to its dedicated operational recovery lane and must never
        # be double-consumed here.
        if content_status == pipeline.CONTENT_STATUS_PENDING_RETRY:
            continue
        if not include_quality_failed and content_status == pipeline.CONTENT_STATUS_QUALITY_FAILED:
            continue

        selected = dict(item)
        selected["revalidation_article_status"] = article_status
        selected["revalidation_content_status"] = content_status
        if article_status == pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW:
            editorial.append(selected)
            if len(editorial) >= limit and not prefer_stale_ready:
                break
        elif include_quality_failed and content_status == pipeline.CONTENT_STATUS_QUALITY_FAILED:
            quality_failed.append(selected)

    # Current-policy Ready is terminal. Only prove enough Ready rows to fill capacity
    # not already owned by Editorial Review. Missing/failed provenance proof fails closed.
    stale_slots = limit if prefer_stale_ready else max(0, limit - len(editorial))
    if stale_slots and ready_candidates:
        has_current = getattr(pipeline, "_notion_page_has_manuscript_child", None)
        headers_factory = getattr(pipeline, "_notion_headers", None)
        if not callable(has_current) or not callable(headers_factory):
            pipeline.logger.warning(
                "[ARTICLE REVALIDATION READY SKIP] current publication-contract proof unavailable"
            )
        else:
            try:
                headers = headers_factory()
            except Exception as exc:
                pipeline.logger.warning(
                    "[ARTICLE REVALIDATION READY SKIP] Notion headers unavailable: %s",
                    exc,
                )
                headers = None
            if headers is not None:
                for item, article_status, content_status in ready_candidates[:max(0, int(stale_ready_probe_limit))]:
                    if len(stale_ready) >= stale_slots:
                        break
                    page_id = str(item.get("notion_page_id") or "")
                    try:
                        current_ready = bool(has_current(page_id, headers))
                    except Exception as exc:
                        pipeline.logger.warning(
                            "[ARTICLE REVALIDATION READY SKIP] current publication-contract proof failed page=%s: %s",
                            page_id,
                            exc,
                        )
                        continue
                    if current_ready:
                        continue
                    selected = dict(item)
                    selected["revalidation_article_status"] = article_status
                    selected["revalidation_content_status"] = content_status
                    selected["revalidation_stale_ready"] = True
                    stale_ready.append(selected)

    ordered = (
        stale_ready + editorial + quality_failed
        if prefer_stale_ready
        else editorial + stale_ready + quality_failed
    )
    return ordered[:limit]


def rehydrate_recovery_repo(pipeline, item: dict) -> dict | None:
    """Restore a durable primary URL for legacy stale-Ready discovery rows."""
    repo = dict(item.get("repo") or {})
    if not item.get("revalidation_stale_ready"):
        return repo
    source = str(repo.get("source") or "")
    if source not in {"HackerNews", "ProductHunt"}:
        return repo
    logger = getattr(pipeline, "logger", None)
    resolver = getattr(pipeline, "resolve_recovery_primary_url", None)
    if not callable(resolver):
        if logger:
            logger.warning("[STALE READY REHYDRATE SKIP] canonical primary resolver unavailable")
        return None
    recovery_repo = dict(repo)
    recovery_repo["notion_page_id"] = item.get("notion_page_id") or ""
    primary = str(resolver(recovery_repo) or "").strip()
    if not primary or not primary.startswith(("http://", "https://")):
        if logger:
            logger.warning(
                "[STALE READY REHYDRATE SKIP] no durable first-party primary source: %s",
                repo.get("nameWithOwner") or "unknown",
            )
        return None
    repo["primaryUrl"] = primary
    details = dict(repo.get("sourceDetails") or {})
    details["external_url"] = primary
    details["recovery_primary_rehydrated"] = True
    repo["sourceDetails"] = details
    return repo

def _cap_validation_budget(pipeline) -> int:
    requested = max(1, int(os.environ.get("ARTICLE_REVALIDATION_REQUEST_BUDGET", str(DEFAULT_REQUEST_BUDGET))))
    budget = getattr(pipeline, "DEEP_DIVE_MODEL_BUDGET", None)
    if budget is None:
        return requested
    current = max(0, int(getattr(budget, "budget", requested)))
    capped = min(current, requested)
    budget.budget = capped
    return capped


def run_article_revalidation(pipeline, limit: int | None = None) -> dict[str, Any]:
    """Regenerate current revalidation candidates under today's gates, read-only."""
    selected_limit = max(1, int(limit or os.environ.get("ARTICLE_REVALIDATION_LIMIT", str(DEFAULT_LIMIT))))
    request_budget = _cap_validation_budget(pipeline)
    pipeline.logger.warning(
        "[ARTICLE REVALIDATION] existing current-gate lane limit=%s request_budget=%s persist=false",
        selected_limit,
        request_budget,
    )
    exact_target = str(os.environ.get("ARTICLE_REVALIDATION_EXACT_TARGET", "") or "").strip()
    items = select_revalidation_items(
        pipeline,
        selected_limit,
        DEFAULT_SCAN_LIMIT,
        include_stale_ready=True,
        exact_target=exact_target,
    )
    if items is None:
        raise RuntimeError("Article revalidation candidate read failed")
    if not items:
        pipeline.logger.info("[ARTICLE REVALIDATION] no eligible existing current-gate Deep Dive candidate")
        return {"selected": 0, "generated": 0, "accepted": 0, "rejected": 0, "unverified": 0}

    result = {"selected": len(items), "generated": 0, "accepted": 0, "rejected": 0, "unverified": 0}
    for index, item in enumerate(items, start=1):
        repo = rehydrate_recovery_repo(pipeline, item)
        if repo is None:
            continue
        name = repo.get("nameWithOwner") or "unknown"
        pipeline.logger.info(
            "[ARTICLE REVALIDATION %s/%s] %s prior_article=%s prior_content=%s",
            index,
            len(items),
            name,
            item.get("revalidation_article_status"),
            item.get("revalidation_content_status"),
        )
        is_safe, license_status = pipeline.legal_safety_gate(repo)
        if not is_safe:
            pipeline.logger.warning("[ARTICLE REVALIDATION SKIP: LICENSE] %s -> %s", name, license_status)
            continue
        try:
            generated = pipeline.generate_intelligence_report(
                repo,
                notion_page_id=item.get("notion_page_id"),
                screening_score=item.get("screening_score"),
                screening_reason=item.get("screening_reason", ""),
                candidate_rank=index,
                candidate_origin="article_revalidation",
                persist_results=False,
            )
        except pipeline.DailyQuotaExhaustedError:
            pipeline.logger.error("[ARTICLE REVALIDATION STOP] Gemini daily quota exhausted")
            break
        if not generated:
            continue
        status = classify_nonpersistent_report(generated)
        manuscript = generated[0] if isinstance(generated, tuple) and generated else generated
        result["generated"] += 1
        if status == "accepted":
            result["accepted"] += 1
        elif status == "rejected":
            result["rejected"] += 1
        else:
            result["unverified"] += 1
        pipeline.logger.info(
            "[ARTICLE REVALIDATION RESULT] %s status=%s chars=%s",
            name,
            status,
            len(str(manuscript or "")),
        )

    pipeline.logger.info("[ARTICLE REVALIDATION COMPLETE] %s", result)
    return result


def _full_recovery_budget_available(pipeline) -> bool:
    """Use only the same remaining article budgets; never create/reset a budget."""
    global_budget = getattr(pipeline, "GEMINI_BUDGET", None)
    deep_budget = getattr(pipeline, "DEEP_DIVE_MODEL_BUDGET", None)
    model_pool = getattr(pipeline, "DEEP_DIVE_MODEL_POOL", ())
    has_candidate = getattr(pipeline, "_model_pool_has_session_candidate", None)
    if global_budget is not None and not global_budget.can_request():
        return False
    if deep_budget is not None and not deep_budget.can_request():
        return False
    if callable(has_candidate) and not has_candidate(model_pool):
        return False
    return True


def run_existing_editorial_recovery(
    pipeline,
    generated_count: int,
    next_candidate_rank: int,
    limit: int = DEFAULT_FULL_RECOVERY_LIMIT,
) -> tuple[int, int]:
    """Use leftover full-run capacity to recover one existing article.

    Normal/full recovery keeps Editorial Review first. During the explicit Run374 Ready
    Rescue slot only, stale Ready is preferred within a bounded five-row provenance probe
    because it already passed a previous publication generation. This is a business-write
    lane: the same existing Notion page id is supplied and ``persist_results=True`` is
    explicit. No Stock row is created, no acquisition dedup is weakened, and no separate
    Gemini budget exists.
    """
    target = int(getattr(pipeline, "TOP_N_FOR_DEEP_DIVE", 0) or 0)
    limit = max(0, min(DEFAULT_FULL_RECOVERY_LIMIT, int(limit)))
    if limit == 0 or generated_count >= target:
        return generated_count, next_candidate_rank
    if not str(getattr(pipeline, "NOTION_API_KEY", "") or "").strip():
        pipeline.logger.info("[EXISTING EDITORIAL RECOVERY] Notion unavailable; skip")
        return generated_count, next_candidate_rank
    if not _full_recovery_budget_available(pipeline):
        pipeline.logger.info("[EXISTING EDITORIAL RECOVERY] article budget/model capacity exhausted; skip")
        return generated_count, next_candidate_rank

    prefer_stale_ready = bool(getattr(pipeline, "_READY_RESCUE_ACTIVE", False))
    attempted_ids = set(getattr(pipeline, "_existing_article_recovery_attempted_ids", set()))
    items = select_revalidation_items(
        pipeline,
        limit=limit,
        scan_limit=DEFAULT_SCAN_LIMIT,
        include_quality_failed=False,
        include_stale_ready=True,
        prefer_stale_ready=prefer_stale_ready,
        exclude_page_ids=attempted_ids,
    )
    if items is None:
        # Unlike authoritative fresh dedup, this optional leftover lane must not stop a
        # completed fresh run merely because its recovery read failed.
        pipeline.logger.warning("[EXISTING EDITORIAL RECOVERY] candidate read failed; skip")
        return generated_count, next_candidate_rank
    if not items:
        pipeline.logger.info("[EXISTING ARTICLE RECOVERY] no eligible Editorial Review or stale Ready row")
        return generated_count, next_candidate_rank

    for item in items[:limit]:
        if generated_count >= target or not _full_recovery_budget_available(pipeline):
            break
        repo = rehydrate_recovery_repo(pipeline, item)
        if repo is None:
            continue
        name = repo.get("nameWithOwner") or "unknown"
        is_safe, license_status = pipeline.legal_safety_gate(repo)
        if not is_safe:
            pipeline.logger.warning("[EXISTING EDITORIAL RECOVERY SKIP: LICENSE] %s -> %s", name, license_status)
            continue
        next_candidate_rank += 1
        is_stale_ready = bool(item.get("revalidation_stale_ready"))
        origin = "existing_stale_ready_recovery" if is_stale_ready else "existing_editorial_recovery"
        pipeline.logger.info(
            "[EXISTING ARTICLE RECOVERY] %s origin=%s prior_article=%s",
            name,
            origin,
            item.get("revalidation_article_status"),
        )
        # Preflight and leftover recovery share the same run. A rejected manuscript
        # can remain Editorial Review, so lifecycle status alone cannot deduplicate it.
        attempted_ids.add(str(item.get("notion_page_id") or ""))
        pipeline._existing_article_recovery_attempted_ids = attempted_ids
        try:
            report = pipeline.generate_intelligence_report(
                repo,
                notion_page_id=item.get("notion_page_id"),
                screening_score=item.get("screening_score"),
                screening_reason=item.get("screening_reason", ""),
                candidate_rank=next_candidate_rank,
                candidate_origin=origin,
                attribution_context=item,
                persist_results=True,
            )
            if report:
                generated_count += 1
                pipeline.logger.info("[EXISTING ARTICLE RECOVERY READY] %s origin=%s", name, origin)
        except pipeline.DailyQuotaExhaustedError:
            pipeline.logger.warning("[EXISTING EDITORIAL RECOVERY STOP] Gemini daily quota exhausted")
            break
    return generated_count, next_candidate_rank


def install_full_recovery(pipeline):
    """Install the leftover Editorial Review / stale Ready lane around the canonical backlog helper.

    Production must fail closed if the canonical backlog surface disappears. A handful
    of long-lived orchestration tests intentionally use a file-less ``ModuleType``
    double exposing only ``main``; those doubles are compatibility-only and receive a
    no-op instead of pretending the recovery layer was installed.
    """
    if getattr(pipeline, _INSTALLED_ATTR, False):
        return pipeline
    original = getattr(pipeline, "process_article_backlog", None)
    if not callable(original):
        if getattr(pipeline, "__file__", None):
            raise RuntimeError(
                "Run277 recovery requires canonical pipeline.process_article_backlog"
            )
        return pipeline

    def process_article_backlog_with_existing_editorial(pending_items, generated_count, next_candidate_rank):
        # Preserve the validated order first: fresh acquisition already ran before this helper,
        # then canonical Deferred -> Pending Retry. Existing Editorial Review, followed by
        # stale Ready, receives only capacity that would otherwise remain unused before Product Review.
        generated_count, next_candidate_rank = original(
            pending_items, generated_count, next_candidate_rank
        )
        return run_existing_editorial_recovery(
            pipeline, generated_count, next_candidate_rank, DEFAULT_FULL_RECOVERY_LIMIT
        )

    pipeline.process_article_backlog = process_article_backlog_with_existing_editorial
    setattr(pipeline, _INSTALLED_ATTR, True)
    return pipeline
