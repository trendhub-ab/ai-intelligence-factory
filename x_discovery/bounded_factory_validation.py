from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from candidate_identity import canonicalize_url


class BoundedValidationError(RuntimeError):
    """Fail-closed contract violation for the saved-X validation lane."""


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise BoundedValidationError(f"{label} must be an object")
    return value


def _require_nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BoundedValidationError(f"{label} must be a non-empty string")
    return value.strip()


def _canonical(value: object, label: str) -> str:
    raw = _require_nonempty_string(value, label)
    try:
        normalized = canonicalize_url(raw)
    except Exception as exc:
        raise BoundedValidationError(f"{label} is not a valid canonical URL") from exc
    if not normalized:
        raise BoundedValidationError(f"{label} is not a valid canonical URL")
    return normalized


def validate_saved_candidate(payload: Mapping[str, Any]) -> dict[str, Any]:
    root = _require_mapping(payload, "payload")
    if root.get("schema_version") != 1:
        raise BoundedValidationError("schema_version must be 1")
    if root.get("lane") != "x_saved_candidate_validation":
        raise BoundedValidationError("lane must be x_saved_candidate_validation")
    if root.get("factory_write") is not False:
        raise BoundedValidationError("factory_write must be false")
    if root.get("evidence_promoted") is not False:
        raise BoundedValidationError("evidence_promoted must be false")

    candidate = _require_mapping(root.get("candidate"), "candidate")
    if candidate.get("source_platform") != "x":
        raise BoundedValidationError("candidate.source_platform must be x")
    if candidate.get("source_role") != "discovery_signal":
        raise BoundedValidationError("candidate.source_role must be discovery_signal")
    if candidate.get("evidence_status") != "discovery_only":
        raise BoundedValidationError("candidate.evidence_status must be discovery_only")
    if candidate.get("is_evidence") is not False:
        raise BoundedValidationError("candidate.is_evidence must be false")
    if candidate.get("factory_write") is not False:
        raise BoundedValidationError("candidate.factory_write must be false")

    canonical_url = _canonical(candidate.get("canonical_url"), "candidate.canonical_url")
    x_post_id = _require_nonempty_string(candidate.get("x_post_id"), "candidate.x_post_id")
    x_post_url = _canonical(candidate.get("x_post_url"), "candidate.x_post_url")
    author = _require_nonempty_string(candidate.get("author"), "candidate.author")

    prepared = _require_mapping(root.get("prepared_primary_source"), "prepared_primary_source")
    prepared_url = _canonical(prepared.get("url"), "prepared_primary_source.url")
    if prepared_url != canonical_url:
        raise BoundedValidationError("prepared_primary_source.url must match candidate.canonical_url")
    title = _require_nonempty_string(prepared.get("title"), "prepared_primary_source.title")
    source_text = _require_nonempty_string(prepared.get("text"), "prepared_primary_source.text")
    if len(source_text) < 200:
        raise BoundedValidationError("prepared_primary_source.text is too short for bounded validation")

    return {
        "canonical_url": canonical_url,
        "x_post_id": x_post_id,
        "x_post_url": x_post_url,
        "author": author,
        "title": title,
        "source_text": source_text,
    }


def _canonical_existing_urls(existing: object) -> set[str]:
    if existing is None:
        raise BoundedValidationError("Factory deduplication could not be verified")
    try:
        values = list(existing)
    except TypeError as exc:
        raise BoundedValidationError("Factory deduplication returned an invalid collection") from exc
    normalized: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            url = canonicalize_url(value)
        except Exception:
            continue
        if url:
            normalized.add(url)
    return normalized


def build_screening_repo(validated: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "nameWithOwner": validated["title"],
        "description": validated["source_text"][:4000],
        "url": validated["canonical_url"],
        "source": "XDiscoverySavedPrimary",
        "stargazerCount": 0,
        "publishedAt": None,
        "x_discovery_provenance": {
            "post_id": validated["x_post_id"],
            "post_url": validated["x_post_url"],
            "author": validated["author"],
            "evidence_status": "discovery_only",
            "is_evidence": False,
        },
    }


def _prepare_boundary(pipeline_module: Any, payload: Mapping[str, Any]):
    validated = validate_saved_candidate(payload)
    original_alert = getattr(pipeline_module, "send_telegram_alert", None)
    if original_alert is not None:
        pipeline_module.send_telegram_alert = lambda *_args, **_kwargs: None
    try:
        existing = pipeline_module.get_existing_repo_urls()
    finally:
        if original_alert is not None:
            pipeline_module.send_telegram_alert = original_alert
    existing_urls = _canonical_existing_urls(existing)
    if validated["canonical_url"] in existing_urls:
        raise BoundedValidationError("candidate already exists in Factory; refusing duplicate screening")
    repo = build_screening_repo(validated)
    screening_item = {"screening_id": "X0001", "repo": repo}
    prompt = pipeline_module._batch_screening_prompt([screening_item])
    if not isinstance(prompt, str) or not prompt.strip():
        raise BoundedValidationError("Factory screening prompt could not be constructed")
    return validated, screening_item, prompt


def run_bounded_validation(pipeline_module: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    validated, _screening_item, prompt = _prepare_boundary(pipeline_module, payload)
    return {
        "schema_version": 1,
        "lane": "x_saved_candidate_validation",
        "status": "SCREENING_BOUNDARY_READY",
        "candidate_count": 1,
        "canonical_url": validated["canonical_url"],
        "x_post_id": validated["x_post_id"],
        "dedup_verified": True,
        "screening_id": "X0001",
        "screening_prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "screening_prompt_chars": len(prompt),
        "screening_executed": False,
        "model_calls": 0,
        "source_fetch_calls": 0,
        "apify_calls": 0,
        "fetchlayer_calls": 0,
        "factory_write": False,
        "evidence_promoted": False,
        "generation_executed": False,
        "publication_executed": False,
    }


def run_single_screening_validation(pipeline_module: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Execute exactly one Gemini screening request and stop before every downstream lane."""
    validated, _screening_item, prompt = _prepare_boundary(pipeline_module, payload)
    if getattr(pipeline_module.GEMINI_BUDGET, "daily_budget", None) != 1:
        raise BoundedValidationError("single screening validation requires GEMINI_DAILY_REQUEST_BUDGET=1")
    if getattr(pipeline_module.GEMINI_BUDGET, "screening_retry_budget", None) != 0:
        raise BoundedValidationError("single screening validation requires GEMINI_SCREENING_RETRY_BUDGET=0")
    pool = list(getattr(pipeline_module, "SCREENING_MODEL_POOL", []) or [])
    if len(pool) != 1 or not str(pool[0]).strip():
        raise BoundedValidationError("single screening validation requires exactly one screening model")
    model_name = str(pool[0]).strip()
    if not getattr(pipeline_module, "GEMINI_API_KEY", None) or getattr(pipeline_module, "client", None) is None:
        raise BoundedValidationError("GEMINI_API_KEY is required for single screening validation")

    register = getattr(pipeline_module, "_register_gemini_usage_atexit", None)
    if callable(register):
        register()

    # Deliberately do not call _call_screening_pool/_call_model_pool. Those production
    # helpers can retry/fallback on provider errors. The direct provider wrapper still
    # enforces local + persistent quota accounting, but this lane gets one send only.
    response = pipeline_module._generate_via_chat(
        model_name,
        prompt,
        config={"response_mime_type": "application/json", "max_output_tokens": 1000},
        request_kind="x_saved_screening_validation",
        request_context="x_saved:X0001",
        count_as_deep_dive=False,
        request_origin="new",
    )

    text = str(getattr(response, "text", "") or "")
    parsed, missing, diagnostic = pipeline_module._parse_batch_screening_response(
        text, {"X0001"}, include_diagnostic=True
    )
    if missing or "X0001" not in parsed:
        raise BoundedValidationError(
            "single screening response failed Factory parser: " + (diagnostic or "missing X0001")
        )
    row = parsed["X0001"]
    if row.get("commercial_score") is None or row.get("shelf_life_score") is None or not row.get("topic_valid"):
        raise BoundedValidationError("single screening response is incomplete: " + (diagnostic or "schema fields missing"))
    if int(getattr(pipeline_module.GEMINI_BUDGET, "request_count", 0)) != 1:
        raise BoundedValidationError("single screening validation did not consume exactly one model request")

    return {
        "schema_version": 1,
        "lane": "x_saved_candidate_screening_validation",
        "status": "SCREENING_VALIDATED",
        "candidate_count": 1,
        "canonical_url": validated["canonical_url"],
        "x_post_id": validated["x_post_id"],
        "dedup_verified": True,
        "screening_id": "X0001",
        "screening_model": model_name,
        "score": row["score"],
        "commercial_score": row["commercial_score"],
        "shelf_life_score": row["shelf_life_score"],
        "portfolio_topic": row["portfolio_topic"],
        "tracking_eligible": row["tracking_eligible"],
        "tracking_reason": row["tracking_reason"],
        "reason": row["reason"],
        "screening_executed": True,
        "model_calls": 1,
        "source_fetch_calls": 0,
        "apify_calls": 0,
        "fetchlayer_calls": 0,
        "factory_write": False,
        "evidence_promoted": False,
        "calibration_executed": False,
        "generation_executed": False,
        "publication_executed": False,
    }


def _load_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BoundedValidationError(f"could not read validation payload: {exc}") from exc
    if not isinstance(payload, dict):
        raise BoundedValidationError("validation payload must be an object")
    return payload


def run_from_path(pipeline_module: Any, path: Path) -> dict[str, Any]:
    payload = _load_payload(path)
    execute_one = os.environ.get("AIIF_X_SCREENING_EXECUTE", "false").strip().lower() in {"1", "true", "yes", "on"}
    result = (
        run_single_screening_validation(pipeline_module, payload)
        if execute_one
        else run_bounded_validation(pipeline_module, payload)
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result
