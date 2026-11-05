"""No-API regression for read-only V1 Human Narrative prompt assembly."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import re

import pytest

import offline_v1_writer_prompt_stack_receipt as trace


def test_synthetic_receipt_has_7_pinned_layers_without_actual_run_claim():
    result = trace.trace_synthetic()
    assert result["schema"] == "v1-synthetic-writer-prompt-stack-receipt-v1"
    assert result["status"] == "SYNTHETIC_ONLY_NOT_ACTUAL_NOV05_PROMPT"
    assert result["v1_run_id"] == 42016503443
    assert result["observed_style"] == "human_narrative"
    assert len(result["stages"]) == 7
    assert [x["stage"] for x in result["stages"]] == [
        "base_generation_protocol",
        "run226_reader_delight",
        "run228_reader_rhythm",
        "reader_value_bridge",
        "run208_reader_value",
        "a_plus_prewrite",
        "run248_final_reader_check",
    ]
    assert all(re.fullmatch(r"[a-f0-9]{64}", x["prompt_sha256"])
               for x in result["stages"])
    assert all(x["prompt_utf8_bytes"] > 0 for x in result["stages"])
    assert result["stages"][0]["prompt_sha256"] != result["stages"][-1]["prompt_sha256"]


def test_synthetic_receipt_is_deterministic_and_contains_no_manuscript():
    r1 = trace.trace_synthetic()
    assert trace.trace_synthetic() == r1
    serialized = json.dumps(r1, ensure_ascii=False)
    for forbidden in (
        "SYNTHETIC FIXTURE", "架空の品質検証用題材", "ARTICLE本文の冒頭",
        "【Output Contract｜完成稿のみ】", "【Source Native Context】",
        "=== MANAGEMENT DATA ===",
    ):
        assert forbidden not in serialized


def test_future_writer_comparison_and_provider_execution_stay_closed():
    data = trace.trace_synthetic()
    assert data["actual_run_prompt_sha256"] is None
    for key in (
        "actual_run_input_evidence_verified",
        "actual_run_dynamic_display_rotation_verified",
        "actual_run_retry_prompt_verified",
        "real_world_fact_verified",
        "next_v04_identical_evidence_verified",
        "can_rank_writers",
        "eligible_for_live_generation",
        "publication_approved",
        "production_modified",
    ):
        assert data[key] is False
    assert data["authorized_model_requests"] == 0


def test_pinned_source_drift_fails_closed(monkeypatch):
    tampered = deepcopy(trace.SOURCE_BLOBS)
    tampered["run226_reader_delight_planning.py"] = "0" * 40
    monkeypatch.setattr(trace, "SOURCE_BLOBS", tampered)
    with pytest.raises(ValueError, match="V1_SOURCE_DRIFT"):
        trace.trace_synthetic()


def test_wrapper_order_drift_fails_closed(monkeypatch):
    monkeypatch.setattr(trace, "ORDER", tuple(reversed(trace.ORDER)))
    with pytest.raises(ValueError, match="V1_PROMPT_LAYER_ORDER_DRIFT"):
        trace.trace_synthetic()


def test_all_receipts_are_shas_of_utf8_bytes():
    for row in trace.trace_synthetic()["stages"]:
        assert len(row["prompt_sha256"]) == 64
        assert type(row["prompt_utf8_bytes"]) is int
        assert row["prompt_utf8_bytes"] > 1000
