"""Single-article Production E2E validation without weakening publication gates.

The lane is deliberately narrow:
- scan a bounded set of existing revalidation candidates with zero model calls;
- preflight current Evidence sufficiency at LOW action risk;
- choose exactly one strongest publishable candidate;
- send only that candidate through the normal Production generation / Gate / persistence path;
- emit an audit record with the exact Notion sync_id for downstream note delivery.

Evidence/Fact/Publication/Human Appeal/Reader policies are not changed here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from article_revalidation import rehydrate_recovery_repo, select_revalidation_items

DEFAULT_CANDIDATE_LIMIT = 8
AUDIT_PATH = Path("article_audit/production_e2e_validation.json")


def _sync_id(page_id: object) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", str(page_id or "")).lower()


def _jsonable_evidence(result: dict[str, Any]) -> dict[str, Any]:
    """Keep only deterministic, serializable Evidence diagnostics."""
    return {
        "state": result.get("state", ""),
        "initial_state": result.get("initial_state", ""),
        "checks": dict(result.get("checks") or {}),
        "core_missing": list(result.get("core_missing") or []),
        "optional_missing": list(result.get("optional_missing") or []),
        "blocking_missing": list(result.get("blocking_missing") or []),
        "documents_checked": int(result.get("documents_checked", 0) or 0),
        "decision_scope_safe": bool(result.get("decision_scope_safe")),
        "action_risk_tier": str(result.get("action_risk_tier") or ""),
        "action_supported_at_current_tier": bool(result.get("action_supported_at_current_tier")),
        "numeric_claims_allowed": bool(result.get("numeric_claims_allowed")),
        "freshness_scope_limited": bool(result.get("freshness_scope_limited")),
        "supplement_attempted": bool(result.get("supplement_attempted")),
        "supplement_success": bool(result.get("supplement_success")),
    }


def _prepare_evidence_preflight(pipeline: Any, repo: dict) -> tuple[dict, dict]:
    """Run the same pre-generation Evidence decision path with zero provider calls."""
    source_info = pipeline.prepare_source_context(repo)
    source_info["requested_action_risk_tier"] = "LOW"
    freshness = pipeline.resolve_followup_freshness(source_info)
    if freshness.get("context"):
        source_info["context"] = pipeline._truncate_source_context(
            source_info.get("context", "") + "\n\n" + freshness["context"]
        )
        source_info["verification_context"] = pipeline._merge_verification_context(
            source_info.get("verification_context") or source_info.get("context", ""),
            freshness["context"],
        )
        source_info["verification_context_length"] = len(source_info["verification_context"])
    source_info["freshness_status_available"] = (
        not freshness.get("triggered") or freshness.get("followup_found", False)
    )
    source_info["evidence_metadata"] = pipeline._build_evidence_metadata(
        source_info.get("verification_context") or source_info.get("context", ""),
        bool(source_info.get("deep_source_scanned")),
    )

    evidence = pipeline.assess_evidence_sufficiency(source_info)
    initial_state = evidence["state"]
    supplement_attempted = False
    supplement_success = False
    if evidence["state"] == pipeline.EVIDENCE_SUPPLEMENT_REQUIRED:
        before_docs = len(source_info.get("evidence_documents", []))
        pipeline.supplement_source_evidence(source_info)
        supplement_attempted = True
        evidence = pipeline.assess_evidence_sufficiency(source_info)
        supplement_success = (
            evidence["state"] == pipeline.EVIDENCE_SUFFICIENT
            and len(source_info.get("evidence_documents", [])) > before_docs
        )
    evidence["initial_state"] = initial_state
    evidence["supplement_attempted"] = supplement_attempted
    evidence["supplement_success"] = supplement_success
    return source_info, evidence


def _eligible_evidence(pipeline: Any, evidence: dict) -> bool:
    checks = evidence.get("checks") or {}
    return bool(
        evidence.get("state") == pipeline.EVIDENCE_SUFFICIENT
        and evidence.get("action_risk_tier") == "LOW"
        and checks.get("primary_source_resolved")
        and checks.get("technical_claims_available")
        and checks.get("action_support_available")
        and checks.get("conditions_for_numbers_available")
        and checks.get("freshness_status_available_if_time_sensitive")
    )


def select_candidate(pipeline: Any, limit: int = DEFAULT_CANDIDATE_LIMIT):
    """Choose one existing candidate only after bounded zero-provider Evidence preflight."""
    items = select_revalidation_items(
        pipeline,
        limit=max(1, int(limit)),
        scan_limit=100,
        include_quality_failed=False,
        include_stale_ready=True,
        prefer_stale_ready=False,
    )
    if items is None:
        raise RuntimeError("Production E2E candidate read failed")

    ordered = sorted(
        items,
        key=lambda row: int(row.get("screening_score") or 0),
        reverse=True,
    )
    diagnostics: list[dict[str, Any]] = []
    eligible: list[tuple[tuple[int, int, int], dict, dict, dict]] = []

    for item in ordered:
        repo = rehydrate_recovery_repo(pipeline, item)
        if repo is None:
            diagnostics.append({
                "name": str((item.get("repo") or {}).get("nameWithOwner") or "unknown"),
                "page_id": str(item.get("notion_page_id") or ""),
                "eligible": False,
                "reason": "primary_rehydration_failed",
            })
            continue

        source = str(repo.get("source") or "")
        if source == "ArXiv":
            verifier = getattr(pipeline, "_verify_arxiv_source_integrity", None)
            if not callable(verifier):
                diagnostics.append({
                    "name": str(repo.get("nameWithOwner") or "unknown"),
                    "page_id": str(item.get("notion_page_id") or ""),
                    "eligible": False,
                    "reason": "arxiv_integrity_verifier_unavailable",
                })
                continue
            ok, reason, verified_repo = verifier(repo)
            if not ok:
                diagnostics.append({
                    "name": str(repo.get("nameWithOwner") or "unknown"),
                    "page_id": str(item.get("notion_page_id") or ""),
                    "eligible": False,
                    "reason": f"arxiv_integrity:{reason}",
                })
                continue
            repo = verified_repo

        safe, license_status = pipeline.legal_safety_gate(repo)
        if not safe:
            diagnostics.append({
                "name": str(repo.get("nameWithOwner") or "unknown"),
                "page_id": str(item.get("notion_page_id") or ""),
                "eligible": False,
                "reason": f"legal_safety:{license_status}",
            })
            continue

        _source_info, evidence = _prepare_evidence_preflight(pipeline, repo)
        evidence_view = _jsonable_evidence(evidence)
        is_eligible = _eligible_evidence(pipeline, evidence)
        row = {
            "name": str(repo.get("nameWithOwner") or "unknown"),
            "page_id": str(item.get("notion_page_id") or ""),
            "source": source,
            "screening_score": int(item.get("screening_score") or 0),
            "eligible": is_eligible,
            "evidence": evidence_view,
        }
        diagnostics.append(row)
        if is_eligible:
            checks = evidence_view.get("checks") or {}
            score = (
                int(item.get("screening_score") or 0),
                int(evidence_view.get("documents_checked") or 0),
                int(bool(checks.get("limitations_or_constraints_available"))),
            )
            eligible.append((score, item, repo, evidence_view))

    if not eligible:
        return None, diagnostics
    eligible.sort(key=lambda row: row[0], reverse=True)
    _score, item, repo, evidence_view = eligible[0]
    return {"item": item, "repo": repo, "evidence": evidence_view}, diagnostics


def _write_audit(result: dict[str, Any]) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run(pipeline: Any) -> dict[str, Any]:
    """Run one exact existing article through normal Production and persist only if Ready."""
    pipeline.initialize_runtime()
    budget = getattr(pipeline, "DEEP_DIVE_MODEL_BUDGET", None)
    used_before = int(getattr(budget, "used", 0) or 0)
    total_cap = int(getattr(budget, "budget", 0) or 0)

    result: dict[str, Any] = {
        "mode": "production_e2e_validation",
        "ready": 0,
        "sync_id": "",
        "candidate": "",
        "source": "",
        "provider_requests": 0,
        "total_cap": total_cap,
        "preflight_candidates": [],
        "error": "",
    }

    try:
        selected, diagnostics = select_candidate(pipeline)
        result["preflight_candidates"] = diagnostics
        if selected is None:
            pipeline.logger.warning(
                "[PRODUCTION E2E VALIDATION] no candidate passed zero-provider Evidence preflight"
            )
            return result

        item = selected["item"]
        repo = selected["repo"]
        page_id = str(item.get("notion_page_id") or "")
        normalized_sync_id = _sync_id(page_id)
        if len(normalized_sync_id) != 32:
            raise RuntimeError("Production E2E requires an existing 32-hex Notion sync_id")

        result.update({
            "candidate": str(repo.get("nameWithOwner") or "unknown"),
            "source": str(repo.get("source") or ""),
            "sync_id": normalized_sync_id,
            "evidence_preflight": selected["evidence"],
        })
        pipeline.logger.info(
            "[PRODUCTION E2E SELECTED] %s source=%s sync_id=%s",
            result["candidate"], result["source"], normalized_sync_id,
        )

        report = pipeline.generate_intelligence_report(
            repo,
            notion_page_id=page_id,
            screening_score=item.get("screening_score"),
            screening_reason=item.get("screening_reason", ""),
            candidate_rank=1,
            candidate_origin="production_e2e_validation",
            attribution_context=item,
            persist_results=True,
        )
        result["ready"] = 1 if report else 0
        if not report:
            result["sync_id"] = ""
        return result
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        used_after = int(getattr(budget, "used", used_before) or 0)
        result["provider_requests"] = max(0, used_after - used_before)
        _write_audit(result)
        pipeline.logger.info("[PRODUCTION E2E VALIDATION] %s", result)
