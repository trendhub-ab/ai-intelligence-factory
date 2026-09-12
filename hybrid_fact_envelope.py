"""Deterministic fact-lock layer for the Hybrid Groq -> Gemini article path.

The envelope never asks an LLM to restate source facts. It preserves the verified ledger
verbatim and carries only source metadata that already exists in the candidate input.
Groq receives this envelope as read-only evidence and returns judgment/editorial fields only.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from groq_article_parity import load_input


class FactEnvelopeError(RuntimeError):
    pass


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_fact_envelope(input_path: str) -> dict:
    item = load_input(input_path)
    ledger = str(item.get("source_context") or "").strip()
    if not ledger:
        raise FactEnvelopeError("fact_ledger_missing")
    provenance = item.get("provenance") if isinstance(item.get("provenance"), dict) else {}
    envelope = {
        "version": 1,
        "candidate_id": item["candidate_id"],
        "name": item["name"],
        "primary_url": item["url"],
        "source": item.get("source"),
        "grounding_status": item.get("grounding_status_hint"),
        "source_date": provenance.get("primary_source_date"),
        "fact_ledger": ledger,
        "fact_ledger_sha256": _sha256(ledger),
    }
    return envelope


def validate_fact_envelope(envelope: dict) -> dict:
    required = {
        "version", "candidate_id", "name", "primary_url", "source", "grounding_status",
        "source_date", "fact_ledger", "fact_ledger_sha256",
    }
    if not isinstance(envelope, dict) or set(envelope) != required:
        raise FactEnvelopeError("fact_envelope_shape_invalid")
    ledger = envelope.get("fact_ledger")
    if not isinstance(ledger, str) or not ledger.strip():
        raise FactEnvelopeError("fact_ledger_missing")
    if envelope.get("fact_ledger_sha256") != _sha256(ledger):
        raise FactEnvelopeError("fact_ledger_hash_mismatch")
    return envelope


def dump_fact_envelope(input_path: str, output_path: str) -> dict:
    envelope = validate_fact_envelope(build_fact_envelope(input_path))
    Path(output_path).write_text(json.dumps(envelope, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return envelope
