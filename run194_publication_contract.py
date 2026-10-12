"""Publication-integrity overlay for persisted Ready and Review manuscripts.

The publication contract is content-addressed: Ready captions contain an automatic SHA-256 of
the publication-policy files and the manuscript body.  This overlay also owns the persistence
invariant introduced after the stale-manuscript audit:

* a page may reach Ready only after exactly one current, byte-exact Ready manuscript remains;
* a page may reach Needs Editorial Review only after exactly one byte-exact Review manuscript
  remains;
* stale Ready, stale Review, captionless legacy, and duplicate-current manuscript blocks are
  archived before the status/property commit;
* cleanup/readback failures fail closed and route the record to Pending Retry instead of allowing
  a misleading Ready/Review state.

The raw pipeline remains frozen for Fresh protocol compatibility.  These guarantees are installed
at runtime as an overlay, preserving the frozen pipeline blob while tightening persistence.
"""
from __future__ import annotations

import inspect
from typing import Any, Callable

import publication_contract as contract

_INSTALLED_ATTR = "_run194_publication_contract_installed"
_DEFAULT_NOTION_RICH_TEXT_LIMIT = 1900


def _block_body(block: dict) -> str:
    code = (block or {}).get("code") or {}
    return "".join(
        str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
        for item in (code.get("rich_text") or [])
    )


def _lossless_text_segments(text: str, limit: int) -> list[str]:
    """Split only for Notion transport; joining the segments must reproduce text exactly."""
    if limit <= 0:
        raise ValueError("Notion rich_text limit must be positive")
    value = str(text or "")
    return [value[i:i + limit] for i in range(0, len(value), limit)]


def _rewrite_code_rich_text_losslessly(children: list, manuscript: str, limit: int) -> list:
    """Replace a real Notion code-block payload's rich_text without changing stub/test shapes."""
    if not children or not isinstance(children[0], dict):
        return children
    code = children[0].get("code")
    if not isinstance(code, dict) or "rich_text" not in code:
        return children

    segments = _lossless_text_segments(manuscript, limit)
    code["rich_text"] = [
        {"type": "text", "text": {"content": segment}}
        for segment in segments
    ]
    roundtrip = "".join(
        str(((item.get("text") or {}).get("content")) or "")
        for item in code["rich_text"]
    )
    if roundtrip != str(manuscript or ""):
        raise RuntimeError("Notion manuscript segmentation changed persisted bytes")
    return children


def _latest_current_block(pipeline_module: Any, page_id: str, headers: dict) -> tuple[str, str] | None:
    latest: tuple[str, str] | None = None
    for block in pipeline_module._notion_page_manuscript_blocks(page_id, headers):
        caption = pipeline_module._notion_code_caption(block)
        body = _block_body(block)
        if contract.is_current_ready_block(body, caption):
            latest = (body, caption)
    return latest


def _strict_archive_block(pipeline_module: Any, block_id: str, repo_name: str, headers: dict) -> bool:
    try:
        res = pipeline_module.requests.delete(
            f"https://api.notion.com/v1/blocks/{block_id}",
            headers=headers,
            timeout=10,
        )
    except Exception as exc:
        pipeline_module.logger.error(
            f"[NOTION SINGLE CANONICAL ARCHIVE EXCEPTION] {repo_name} block={block_id}: {exc}"
        )
        return False
    if res.status_code != 200:
        pipeline_module.logger.error(
            f"[NOTION SINGLE CANONICAL ARCHIVE ERROR] {repo_name} block={block_id} -> {res.text}"
        )
        return False
    return True


def _ensure_single_canonical(
    pipeline_module: Any,
    *,
    page_id: str,
    repo_name: str,
    expected_body: str,
    headers: dict,
    caption_for_append: str,
    matches: Callable[[dict], bool],
) -> bool:
    """Persist/retain one canonical manuscript and archive every other manuscript block.

    The canonical body is never selected by recency or ordering.  It must satisfy the supplied
    identity predicate.  When multiple byte-identical canonical candidates exist, the first
    existing block is retained and duplicate copies are archived.  A second readback proves the
    final one-block invariant before any caller commits Ready/Review properties.
    """
    try:
        blocks = list(pipeline_module._notion_page_manuscript_blocks(page_id, headers))
    except Exception as exc:
        pipeline_module.logger.error(
            f"[NOTION SINGLE CANONICAL READ FAILED] {repo_name} -> {exc}"
        )
        return False

    candidates = [block for block in blocks if matches(block)]
    if not candidates:
        try:
            children = pipeline_module.build_notion_manuscript_children(
                expected_body, caption_for_append
            )
            res = pipeline_module.requests.patch(
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                json={"children": children},
                headers=headers,
                timeout=10,
            )
        except Exception as exc:
            pipeline_module.logger.error(
                f"[NOTION SINGLE CANONICAL APPEND EXCEPTION] {repo_name}: {exc}"
            )
            return False
        if res.status_code != 200:
            pipeline_module.logger.error(
                f"[NOTION SINGLE CANONICAL APPEND ERROR] {repo_name} -> {res.text}"
            )
            return False
        try:
            blocks = list(pipeline_module._notion_page_manuscript_blocks(page_id, headers))
        except Exception as exc:
            pipeline_module.logger.error(
                f"[NOTION SINGLE CANONICAL POST-APPEND READ FAILED] {repo_name}: {exc}"
            )
            return False
        candidates = [block for block in blocks if matches(block)]

    if not candidates:
        pipeline_module.logger.error(
            f"[NOTION SINGLE CANONICAL MISSING] {repo_name} -> expected manuscript not found"
        )
        return False

    canonical = candidates[0]
    canonical_id = str(canonical.get("id") or "").strip()
    if not canonical_id:
        pipeline_module.logger.error(
            f"[NOTION SINGLE CANONICAL ID MISSING] {repo_name}"
        )
        return False

    for block in blocks:
        if block is canonical:
            continue
        block_id = str(block.get("id") or "").strip()
        if not block_id:
            pipeline_module.logger.error(
                f"[NOTION STALE MANUSCRIPT ID MISSING] {repo_name}"
            )
            return False
        if not _strict_archive_block(pipeline_module, block_id, repo_name, headers):
            return False

    try:
        remaining = list(pipeline_module._notion_page_manuscript_blocks(page_id, headers))
    except Exception as exc:
        pipeline_module.logger.error(
            f"[NOTION SINGLE CANONICAL VERIFY READ FAILED] {repo_name}: {exc}"
        )
        return False

    if len(remaining) != 1:
        pipeline_module.logger.error(
            f"[NOTION SINGLE CANONICAL COUNT FAILED] {repo_name} -> count={len(remaining)}"
        )
        return False
    final = remaining[0]
    if str(final.get("id") or "").strip() != canonical_id or not matches(final):
        pipeline_module.logger.error(
            f"[NOTION SINGLE CANONICAL VERIFY FAILED] {repo_name}"
        )
        return False
    return True


def install(pipeline_module: Any) -> Any:
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_build_children = pipeline_module.build_notion_manuscript_children
    original_upgrade = pipeline_module.upgrade_notion_page_with_report
    original_review_persist = pipeline_module.persist_notion_needs_editorial_review
    upgrade_signature = inspect.signature(original_upgrade)
    legacy_ready_caption = str(
        getattr(pipeline_module, "MANUSCRIPT_CAPTION_READY", "AIIF_MANUSCRIPT:READY")
    )

    def build_current_manuscript_children(clean_manuscript: str, caption: str | None = None) -> list:
        effective = caption
        if effective is None or str(effective).strip() == legacy_ready_caption:
            effective = contract.current_ready_caption(clean_manuscript)
        children = original_build_children(clean_manuscript, effective)
        limit = int(
            getattr(pipeline_module, "NOTION_BLOCK_LIMIT", _DEFAULT_NOTION_RICH_TEXT_LIMIT)
            or _DEFAULT_NOTION_RICH_TEXT_LIMIT
        )
        return _rewrite_code_rich_text_losslessly(children, clean_manuscript, limit)

    def has_current_ready_manuscript(page_id: str, headers: dict) -> bool:
        return _latest_current_block(pipeline_module, page_id, headers) is not None

    def upgrade_with_exact_body_idempotency(*args, **kwargs):
        bound = upgrade_signature.bind_partial(*args, **kwargs)
        page_id = str(bound.arguments.get("page_id") or "")
        repo_name = str(bound.arguments.get("repo_name") or "")
        clean_manuscript = str(bound.arguments.get("clean_manuscript") or "")
        if not clean_manuscript or not page_id:
            return original_upgrade(*args, **kwargs)
        if not getattr(pipeline_module, "NOTION_API_KEY", ""):
            return False

        headers = pipeline_module._notion_headers()

        def exact_ready(block: dict) -> bool:
            body = _block_body(block)
            caption = pipeline_module._notion_code_caption(block)
            return contract.is_exact_current_ready_block(body, caption, clean_manuscript)

        if not _ensure_single_canonical(
            pipeline_module,
            page_id=page_id,
            repo_name=repo_name,
            expected_body=clean_manuscript,
            headers=headers,
            caption_for_append=contract.current_ready_caption(clean_manuscript),
            matches=exact_ready,
        ):
            pipeline_module._mark_pending_retry_or_escalate(
                page_id,
                repo_name,
                "Notion single-canonical Ready manuscript verification failed",
            )
            return False

        previous_has = pipeline_module._notion_page_has_manuscript_child

        def exact_exists(_page_id: str, _headers: dict) -> bool:
            try:
                blocks = pipeline_module._notion_page_manuscript_blocks(_page_id, _headers)
            except Exception:
                return False
            return len(blocks) == 1 and exact_ready(blocks[0])

        # The raw pipeline now sees an already-persisted canonical child, so its Phase 1 skips
        # append and its existing Phase 2 property transaction remains authoritative.  If the
        # property commit fails, appended_block_ids is empty and the verified canonical body is
        # intentionally retained as the safe retry anchor.
        pipeline_module._notion_page_has_manuscript_child = exact_exists
        try:
            return original_upgrade(*args, **kwargs)
        finally:
            pipeline_module._notion_page_has_manuscript_child = previous_has

    def persist_single_review(
        page_id: str,
        repo_name: str,
        clean_manuscript: str,
        properties: dict,
        reasons: list[str],
    ) -> bool:
        if not page_id or not getattr(pipeline_module, "NOTION_API_KEY", ""):
            return False
        headers = pipeline_module._notion_headers()
        expected_body = str(clean_manuscript or "")

        def exact_review(block: dict) -> bool:
            return (
                _block_body(block) == expected_body
                and pipeline_module._notion_code_caption(block)
                == pipeline_module.MANUSCRIPT_CAPTION_REVIEW
            )

        if not _ensure_single_canonical(
            pipeline_module,
            page_id=page_id,
            repo_name=str(repo_name),
            expected_body=expected_body,
            headers=headers,
            caption_for_append=pipeline_module.MANUSCRIPT_CAPTION_REVIEW,
            matches=exact_review,
        ):
            pipeline_module._mark_pending_retry_or_escalate(
                page_id,
                str(repo_name),
                "Notion single-canonical editorial-review manuscript verification failed",
            )
            return False

        review_props = dict(properties)
        review_props[pipeline_module.PROP_STATUS] = {
            "select": {"name": pipeline_module.STATUS_DEEP_DIVE}
        }
        review_props[pipeline_module.PROP_CONTENT_STATUS] = {
            "select": {"name": pipeline_module.CONTENT_STATUS_DEEP_DIVE}
        }
        review_props[pipeline_module.PROP_ARTICLE_STATUS] = {
            "select": {"name": pipeline_module.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW}
        }
        review_props[pipeline_module.PROP_SUBSCRIPTION_VISIBILITY] = {
            "select": {"name": pipeline_module.VISIBILITY_SUBSCRIBER_ONLY}
        }
        review_props.pop(pipeline_module.PROP_REVIEW_STATUS, None)
        if reasons:
            pipeline_module.logger.info(
                "[NOTION EDITORIAL REVIEW REASON] %s: %s",
                repo_name,
                ", ".join(reasons)[:500],
            )
        try:
            res_props = pipeline_module.requests.patch(
                f"https://api.notion.com/v1/pages/{page_id}",
                json={"properties": review_props},
                headers=headers,
                timeout=10,
            )
        except Exception as exc:
            pipeline_module.logger.error(
                "[NOTION EDITORIAL REVIEW PROPERTIES EXCEPTION] %s: %s", repo_name, exc
            )
            pipeline_module._mark_pending_retry_or_escalate(
                page_id, str(repo_name), "Notion editorial review properties commit exception"
            )
            return False
        if res_props.status_code != 200:
            pipeline_module.logger.error(
                "[NOTION EDITORIAL REVIEW PROPERTIES ERROR] %s -> %s", repo_name, res_props.text
            )
            pipeline_module._mark_pending_retry_or_escalate(
                page_id, str(repo_name), "Notion editorial review properties commit failed"
            )
            return False
        pipeline_module.logger.info(
            "[NOTION EDITORIAL REVIEW STORED] %s -> single canonical manuscript + internal review state",
            repo_name,
        )
        return True

    pipeline_module.build_notion_manuscript_children = build_current_manuscript_children
    pipeline_module._notion_page_has_manuscript_child = has_current_ready_manuscript
    pipeline_module.upgrade_notion_page_with_report = upgrade_with_exact_body_idempotency
    pipeline_module.persist_notion_needs_editorial_review = persist_single_review
    pipeline_module.CURRENT_PUBLICATION_CONTRACT = contract.CONTRACT_ID
    pipeline_module.CURRENT_PUBLICATION_POLICY_SHA256 = contract.policy_sha256()
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
