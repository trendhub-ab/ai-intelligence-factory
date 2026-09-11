from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

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
    """Validate exactly one saved discovery candidate and its saved source text.

    This contract deliberately accepts no list/batch input. X remains discovery-only;
    the official primary-source body must already be saved in the payload so this lane
    never needs Apify, FetchLayer, page fetching, redirect resolution, or evidence
    promotion.
    """
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
    """Map saved X provenance to the existing Factory screening candidate shape.

    X engagement is intentionally not mapped into Factory engagement/scoring.
    """
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


def run_bounded_validation(pipeline_module: Any, payload: Mapping[str, Any]) -> dict[str, Any]:
    """Reach the real installed screening prompt boundary with zero model/write calls.

    The only permitted external Factory operation is the existing Notion dedup READ.
    Telegram is suppressed for this validation call so a dedup outage cannot create an
    external notification side effect. No source fetch, provider request, persistence,
    evidence promotion, generation, or publication function is invoked here.
    """
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


def run_from_path(pipeline_module: Any, path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BoundedValidationError(f"could not read validation payload: {exc}") from exc
    result = run_bounded_validation(pipeline_module, payload)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result
