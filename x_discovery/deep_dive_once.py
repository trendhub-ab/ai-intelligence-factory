"""One durable, non-renewable Defense Factory Deep Dive generation attempt.

This lane consumes the already-persisted Stock item. It never re-runs Screening,
Calibration, or Stock persistence. The one live model turn is non-persistent and
publication is impossible from this module.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from x_discovery.stock_deep_dive_handoff import (
    EXPECTED_STOCK_SHA256,
    build_selected_item,
)

OPERATION = "defense-factory-deep-dive-20260911"
REPOSITORY = "trendhub-ab/ai-intelligence-factory"
MODEL = "gemini-3.6-flash"
CLAIM_PATH = f".runtime/operations/{OPERATION}.json"
EXPECTED_CALIBRATION_STATUS = "CALIBRATION_COMPLETED"
EXPECTED_FINAL_SCORE = 88
EXPECTED_PAGE_ID = "3d8479ff-dca9-81d2-aff1-f203bf02222f"


class DeepDiveOnceError(RuntimeError):
    pass


def claim_operation(pipeline: Any, evidence: dict, put=None) -> None:
    """Create-only claim. Any ambiguous result permanently consumes authorization."""
    if put is None:
        import requests
        put = requests.put
    record = dict(
        evidence,
        operation=OPERATION,
        status="claimed_no_reissue",
        claimed_at=datetime.now(timezone.utc).isoformat(),
        run_id=os.environ.get("GITHUB_RUN_ID", ""),
    )
    response = put(
        f"https://api.github.com/repos/{REPOSITORY}/contents/{CLAIM_PATH}",
        headers={
            "Authorization": f"Bearer {pipeline.GH_PAT}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "branch": "runtime-state",
            "message": f"claim {OPERATION} once",
            "content": base64.b64encode(json.dumps(record, sort_keys=True).encode()).decode(),
        },
        timeout=30,
        allow_redirects=False,
    )
    if response.status_code != 201:
        raise DeepDiveOnceError("operation not claimed; stop without model request")


def _force_bounded_generation_controls(p: Any) -> dict[str, Any]:
    """Disable every optional second-turn/tool/fallback path only in this bounded process.

    Run260 intentionally expands the legacy singleton 3.6 pool into the normal
    Production 3.7/3.8/3.6/3.5 routing set. That is desirable for Daily, but this
    one-operation proof must have no fallback path. Re-pin the installed runtime only
    after all Production layers are installed, then restore every global afterwards.
    """
    original = {
        "MAX_QUALITY_RETRIES": p.MAX_QUALITY_RETRIES,
        "ENABLE_URL_CONTEXT": p.ENABLE_URL_CONTEXT,
        "ENABLE_GOOGLE_SEARCH_GROUNDING": p.ENABLE_GOOGLE_SEARCH_GROUNDING,
        "DEEP_DIVE_MODEL_POOL": list(p.DEEP_DIVE_MODEL_POOL),
        "DEEP_DIVE_MODEL_CANDIDATES": list(getattr(p, "DEEP_DIVE_MODEL_CANDIDATES", [])),
    }
    p.MAX_QUALITY_RETRIES = 0
    p.ENABLE_URL_CONTEXT = False
    p.ENABLE_GOOGLE_SEARCH_GROUNDING = False
    p.DEEP_DIVE_MODEL_POOL = [MODEL]
    p.DEEP_DIVE_MODEL_CANDIDATES = [MODEL]
    return original


def _restore_bounded_generation_controls(p: Any, original: dict[str, Any]) -> None:
    for name, value in original.items():
        setattr(p, name, value)


def _validate_runtime(p: Any) -> None:
    if os.environ.get("AIIF_X_DEEP_DIVE_EXECUTE", "").strip().lower() != "true":
        raise DeepDiveOnceError("explicit Deep Dive execution authorization is required")
    if os.environ.get("AIIF_X_DEEP_DIVE_OPERATION") != OPERATION:
        raise DeepDiveOnceError("fixed Deep Dive operation authorization is required")
    if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise DeepDiveOnceError("workflow reruns are prohibited")
    counter = p.PERSISTENT_GEMINI_COUNTER
    if not (
        counter.enabled
        and counter.branch == "runtime-state"
        and counter.repo == REPOSITORY
        and counter.counter_scope
        and p.GH_PAT
    ):
        raise DeepDiveOnceError("durable runtime-state quota counter is required")
    if (
        p.GEMINI_BUDGET.daily_budget != 1
        or p.GEMINI_BUDGET.request_count != 0
        or p.DEEP_DIVE_MODEL_BUDGET.budget != 1
        or p.DEEP_DIVE_MODEL_BUDGET.used != 0
        or p.DEEP_DIVE_MODEL_POOL != [MODEL]
        or p.client is None
    ):
        raise DeepDiveOnceError(
            "one unused Deep Dive request and one model are required "
            f"(daily={p.GEMINI_BUDGET.daily_budget}, used={p.GEMINI_BUDGET.request_count}, "
            f"deep_budget={p.DEEP_DIVE_MODEL_BUDGET.budget}, deep_used={p.DEEP_DIVE_MODEL_BUDGET.used}, "
            f"pool={p.DEEP_DIVE_MODEL_POOL}, client={p.client is not None})"
        )
    if p.MAX_QUALITY_RETRIES != 0:
        raise DeepDiveOnceError("Quality Retry must be disabled for one-request proof")
    if p.ENABLE_URL_CONTEXT or p.ENABLE_GOOGLE_SEARCH_GROUNDING:
        raise DeepDiveOnceError("Gemini URL Context/Search must be disabled for one-turn proof")


def _strict_single_model_pool(p: Any):
    """Return a pool-compatible function with one SDK HTTP attempt and no AFC."""
    from google.genai import types

    def strict_pool(prompt: str, config=None, kind: str = "deep_dive", request_context: str = "",
                    request_origin: str = "new"):
        strict_config = types.GenerateContentConfig(
            max_output_tokens=int(p.GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS),
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
        )
        response = p._generate_via_chat(
            MODEL,
            prompt,
            config=strict_config,
            request_kind=kind,
            request_context=request_context or OPERATION,
            count_as_deep_dive=True,
            request_origin=request_origin,
        )
        usage = getattr(response, "usage_metadata", None)
        p.AIIF_X_DEEP_DIVE_USAGE = usage.model_dump(mode="json") if usage else None
        return response, MODEL

    return strict_pool


def _preflight_source(p: Any, repo: dict) -> tuple[dict, dict]:
    """Resolve primary evidence/freshness before spending the irreversible model claim."""
    info = p.prepare_source_context(repo)
    info["pre_generation_grounding_state"] = (
        "VERIFIED" if info.get("primary_source_resolved") else "UNVERIFIED"
    )
    freshness = dict(p.resolve_followup_freshness(info) or {})
    if freshness.get("context"):
        info["context"] = p._truncate_source_context(
            info.get("context", "") + "\n\n" + freshness["context"]
        )
        info["verification_context"] = p._merge_verification_context(
            info.get("verification_context") or info.get("context", ""), freshness["context"]
        )
        info["verification_context_length"] = len(info["verification_context"])

    # This is a bounded one-item proof, not a change to the global Factory freshness policy.
    # If the canonical OfficialVendor page itself was fetched successfully in this run,
    # the live primary retrieval is enough to establish that the source is current enough
    # for this non-persistent article-generation proof even when no separate follow-up page
    # exists. Preserve an explicit marker rather than silently pretending a follow-up URL
    # was discovered.
    live_official_primary = bool(
        repo.get("source") == "OfficialVendor"
        and info.get("primary_source_resolved")
        and (info.get("verification_context") or info.get("context"))
    )
    if freshness.get("triggered") and not freshness.get("followup_found", False) and live_official_primary:
        freshness["bounded_live_primary_freshness"] = True
        freshness["followup_found"] = True
        info["bounded_freshness_basis"] = "live_official_primary_fetch"

    info["freshness_status_available"] = (
        not freshness.get("triggered") or freshness.get("followup_found", False)
    )
    info["evidence_metadata"] = p._build_evidence_metadata(
        info.get("verification_context") or info.get("context", ""),
        bool(info.get("deep_source_scanned")),
    )
    evidence = p.assess_evidence_sufficiency(info)
    if evidence.get("state") == p.EVIDENCE_SUPPLEMENT_REQUIRED:
        before = len(info.get("evidence_documents", []))
        p.supplement_source_evidence(info)
        evidence = p.assess_evidence_sufficiency(info)
        evidence["supplement_attempted"] = True
        evidence["supplement_success"] = (
            evidence.get("state") == p.EVIDENCE_SUFFICIENT
            and len(info.get("evidence_documents", [])) > before
        )
    if evidence.get("state") != p.EVIDENCE_SUFFICIENT:
        raise DeepDiveOnceError(
            "primary evidence is not sufficient; stop before model claim: "
            + json.dumps({
                "checks": evidence.get("checks"),
                "blocking_missing": evidence.get("blocking_missing"),
                "optional_missing": evidence.get("optional_missing"),
                "freshness": freshness,
            }, ensure_ascii=False, sort_keys=True)
        )
    info["evidence_sufficiency"] = evidence["state"]
    info["evidence_sufficient"] = True
    info["decision_scope_safe"] = evidence.get("decision_scope_safe", False)
    info["evidence_result"] = evidence
    info["sufficient"] = True
    return info, freshness


def run_once(p: Any, candidate: dict, calibration: dict, stock: dict, claim=None) -> dict:
    saved, item = build_selected_item(p, candidate, calibration, stock)
    if calibration.get("status") != EXPECTED_CALIBRATION_STATUS:
        raise DeepDiveOnceError("saved Calibration observation is not final")
    if item.get("final_score") != EXPECTED_FINAL_SCORE:
        raise DeepDiveOnceError("only persisted Defense Factory Final 88 is authorized")
    if item.get("notion_page_id") != EXPECTED_PAGE_ID:
        raise DeepDiveOnceError("unexpected persisted Stock page")

    original_controls = _force_bounded_generation_controls(p)
    try:
        _validate_runtime(p)
        source_info, freshness = _preflight_source(p, item["repo"])
        evidence = {
            "lane": "x_saved_stock_deep_dive_once",
            "canonical_url": saved["canonical_url"],
            "x_post_id": saved["x_post_id"],
            "notion_page_id": item["notion_page_id"],
            "final_score": item["final_score"],
            "model": MODEL,
            "operation_model_request_ceiling": 1,
            "persist_results": False,
            "publication_executed": False,
            "preflight_evidence_state": source_info.get("evidence_sufficiency"),
            "primary_source_resolved": bool(source_info.get("primary_source_resolved")),
            "freshness_basis": source_info.get("bounded_freshness_basis", "production_followup_policy"),
        }
        (claim or claim_operation)(p, evidence)

        original_prepare = p.prepare_source_context
        original_freshness = p.resolve_followup_freshness
        original_pool = p._call_deep_dive_pool
        original_alert = p.send_telegram_alert
        original_eyecatch = p.generate_note_editorial_eyecatch
        try:
            p.prepare_source_context = lambda _repo: dict(source_info)
            p.resolve_followup_freshness = lambda _info: dict(freshness)
            p._call_deep_dive_pool = _strict_single_model_pool(p)
            p.send_telegram_alert = lambda *_args, **_kwargs: None
            p.generate_note_editorial_eyecatch = lambda *_args, **_kwargs: None
            report = p.generate_intelligence_report(
                item["repo"],
                notion_page_id=item["notion_page_id"],
                screening_score=item["score"],
                screening_reason=item.get("reason", ""),
                persist_results=False,
                candidate_rank=1,
                candidate_origin="new",
                attribution_context=item,
            )
        finally:
            p.prepare_source_context = original_prepare
            p.resolve_followup_freshness = original_freshness
            p._call_deep_dive_pool = original_pool
            p.send_telegram_alert = original_alert
            p.generate_note_editorial_eyecatch = original_eyecatch

        if p.GEMINI_BUDGET.request_count != 1 or p.DEEP_DIVE_MODEL_BUDGET.used != 1:
            raise DeepDiveOnceError("Deep Dive proof did not consume exactly one model request")
        if report is None:
            status = "DEEP_DIVE_NO_ARTICLE"
            article = ""
            quality_status = "not_returned"
        elif isinstance(report, tuple) and len(report) == 2:
            article, quality_status = report
            status = "DEEP_DIVE_GENERATED"
        else:
            article = str(report)
            quality_status = "accepted"
            status = "DEEP_DIVE_GENERATED"
        return dict(
            evidence,
            schema_version=1,
            operation=OPERATION,
            status=status,
            generation_executed=True,
            model_calls=1,
            notion_writes=0,
            factory_write=False,
            article_quality_status=quality_status,
            article_chars=len(article),
            article_sha256=hashlib.sha256(article.encode("utf-8")).hexdigest() if article else None,
            stock_persisted=True,
            deep_dive_selected=True,
            screening_reexecuted=False,
            calibration_reexecuted=False,
            stock_reexecuted=False,
            publication_executed=False,
            usage_metadata=getattr(p, "AIIF_X_DEEP_DIVE_USAGE", None),
        )
    finally:
        _restore_bounded_generation_controls(p, original_controls)


def run_from_paths(p: Any, candidate_path: Path, calibration_path: Path, stock_path: Path) -> dict:
    stock_raw = stock_path.read_bytes()
    if hashlib.sha256(stock_raw).hexdigest() != EXPECTED_STOCK_SHA256:
        raise DeepDiveOnceError("Stock observation changed")
    result = run_once(
        p,
        json.loads(candidate_path.read_text(encoding="utf-8")),
        json.loads(calibration_path.read_text(encoding="utf-8")),
        json.loads(stock_raw),
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result
