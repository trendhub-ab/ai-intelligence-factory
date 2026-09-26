"""Run-scoped adapter from current Production parsed fields to frozen Local Skills.

This module is canary-only.  It does not write to Notion, publish to note, call a
provider, or alter Gate policy.  The Gemini Deep Dive may still produce its normal
structured fields; its generated article body is discarded and replaced with the
frozen provider-free compiler output.
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .compiler import compile_snapshot


def _text(value: Any) -> str:
    return str(value or "").strip()


def _evidence_urls(primary_url: str, grounding: Mapping[str, Any] | None) -> list[str]:
    values: list[str] = []
    for value in list((grounding or {}).get("evidence_urls") or []):
        url = _text(value)
        if url and url not in values:
            values.append(url)
    primary = _text(primary_url)
    if primary and primary not in values:
        values.append(primary)
    return values


def build_snapshot(
    repo: Mapping[str, Any],
    parsed: Mapping[str, Any],
    *,
    source: str,
    primary_url: str,
    grounding: Mapping[str, Any] | None,
) -> dict[str, Any]:
    name = _text(repo.get("nameWithOwner") or repo.get("name"))
    entity_url = _text(repo.get("primaryUrl") or primary_url or repo.get("url"))
    seed = f"{source}|{entity_url}|{name}"
    return {
        "schema": "aiif_local_writer_snapshot_v1",
        "case_id": hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32],
        "canonical_entity_id": _text(repo.get("canonical_entity_id")) or f"url:{entity_url}",
        "name": name,
        "reader_title": _text(parsed.get("title_text")),
        "source": _text(source),
        "source_summary": _text(parsed.get("source_summary_text")),
        "what": _text(parsed.get("what_text")),
        "why_important": _text(parsed.get("why_important_text")),
        "decision": _text(parsed.get("decision_text")).upper(),
        "decision_score": int(parsed.get("score") or 0),
        "decision_reason": _text(parsed.get("decision_reason_text")),
        "action": _text(parsed.get("action_text")),
        "primary_risk": _text(parsed.get("why_not_important_text")),
        "best_for": _text(parsed.get("who_should_use_text")),
        "avoid_for": _text(parsed.get("who_should_not_use_text")),
        "evidence_urls": _evidence_urls(primary_url, grounding),
    }


def apply_to_production_parsed(
    repo: Mapping[str, Any],
    parsed: Mapping[str, Any],
    *,
    source: str,
    primary_url: str,
    grounding: Mapping[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    snapshot = build_snapshot(
        repo, parsed, source=source, primary_url=primary_url, grounding=grounding
    )
    compiled = compile_snapshot(snapshot)
    out = dict(parsed)
    out["title_text"] = compiled["parsed"]["title_text"]
    out["note_draft"] = compiled["parsed"]["note_draft"]
    meta = {
        "status": compiled["status"],
        "case_id": snapshot["case_id"],
        "canonical_entity_id": snapshot["canonical_entity_id"],
        "canonicalizer_version": compiled["canonicalizer_version"],
        "canonicalizer_blob_sha": compiled["canonicalizer_blob_sha"],
        "writer_blob_sha": compiled["writer_blob_sha"],
        "source": snapshot["source"],
        "evidence_url_count": len(snapshot["evidence_urls"]),
    }
    out["_local_skills_canary"] = dict(meta)
    return out, meta
