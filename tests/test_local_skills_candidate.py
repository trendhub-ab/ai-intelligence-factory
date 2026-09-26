from __future__ import annotations

import hashlib
import re
from pathlib import Path

from local_skills import (
    CANONICALIZER_BLOB_SHA,
    WRITER_BLOB_SHA,
    CANDIDATE_STATUS,
    compile_snapshot,
)


ROOT = Path(__file__).resolve().parents[1]
WRITER_PATH = ROOT / "local_skills" / "writer.py"
CANON_PATH = ROOT / "local_skills" / "publication_canonicalizer.py"


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\x00" + data).hexdigest()


def _snapshot() -> dict:
    return {
        "schema": "aiif_local_writer_snapshot_v1",
        "case_id": "fresh-synthetic-contract-case",
        "canonical_entity_id": "url:https://example.invalid/kernel",
        "name": "Benchmark example: measured 7x faster kernel",
        "reader_title": "Kernel benchmark candidate",
        "source": "HackerNews",
        "source_summary": "A benchmark example measured 7x faster on a fixed workload.",
        "what": "A kernel implementation evaluated with a benchmark example.",
        "why_important": "It can be checked as a bounded engineering result rather than a universal claim.",
        "decision": "WATCH",
        "decision_score": 60,
        "decision_reason": "The benchmark is useful, but the result needs workload-specific verification.",
        "action": "Inspect the implementation and reproduce the benchmark.",
        "primary_risk": "The observed speedup may not transfer to another workload.",
        "best_for": "Teams that can reproduce kernel benchmarks.",
        "avoid_for": "Teams that need a universal performance guarantee.",
        "evidence_urls": ["https://example.invalid/kernel"],
    }


def test_frozen_candidate_blobs_are_byte_identical_to_stage6_freeze():
    assert _git_blob_sha(WRITER_PATH) == WRITER_BLOB_SHA
    assert _git_blob_sha(CANON_PATH) == CANONICALIZER_BLOB_SHA


def test_compiler_preserves_evidence_surface_and_numeric_lexemes():
    original = _snapshot()
    result = compile_snapshot(original)

    assert result["status"] == CANDIDATE_STATUS
    assert result["canonicalizer_version"] == "stage6-v4"
    assert result["original_snapshot"] == original
    assert result["original_snapshot"] is not original

    canonical = result["canonicalized_snapshot"]
    assert canonical["canonical_entity_id"] == original["canonical_entity_id"]
    assert canonical["decision"] == original["decision"]
    assert canonical["decision_score"] == original["decision_score"]
    assert canonical["evidence_urls"] == original["evidence_urls"]
    assert "7x faster（一次情報で示された特定条件下の目安）" in canonical["name"]
    assert "実際の改善幅は処理内容・条件・実行環境によって変わります。" in canonical["primary_risk"]

    number_re = re.compile(r"[+-]?(?:\\d{1,3}(?:,\\d{3})+|\\d+)(?:\\.\\d+)?(?:[eE][+-]?\\d+)?")
    fields = (
        "name", "reader_title", "source_summary", "what", "why_important",
        "decision_reason", "action", "primary_risk", "best_for", "avoid_for",
    )
    before = number_re.findall("\\n".join(str(original.get(k) or "") for k in fields))
    after = number_re.findall("\\n".join(str(canonical.get(k) or "") for k in fields))
    assert before == after

    # Gate evidence context must come from the untouched record, not the
    # canonicalized publication surface.
    assert "一次情報で示された特定条件下の目安" not in result["evidence_context"]
    assert "Benchmark example: measured 7x faster kernel" in result["evidence_context"]
    assert result["parsed"]["note_draft"]


def test_candidate_is_idempotent():
    first = compile_snapshot(_snapshot())
    second = compile_snapshot(first["canonicalized_snapshot"])
    assert second["canonicalized_snapshot"] == first["canonicalized_snapshot"]


def test_production_is_not_wired_to_local_skills_candidate():
    # Stage 7 packages the frozen candidate only.  Production behavior must stay
    # byte-semantically independent until a fresh untouched holdout validates it.
    for path in (ROOT / "pipeline.py", ROOT / "production_pipeline.py"):
        text = path.read_text(encoding="utf-8")
        assert "local_skills" not in text
