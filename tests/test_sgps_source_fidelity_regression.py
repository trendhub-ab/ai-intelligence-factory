from __future__ import annotations

import json
from pathlib import Path

import canonical_article_contract as cac
import fact_validation_signals as fvs


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "source_fidelity" / "sgps_pre_canonical_article_20260919.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_sgps_real_pre_fix_regressions_are_blocked():
    data = _fixture()
    source = data["source_context"]

    for case in data["regressions"]:
        failures = fvs._find_source_semantic_fidelity_violations(case["claim"], source)
        assert any(case["expected_reason"] in row for row in failures), (
            case["id"],
            case["claim"],
            failures,
        )


def test_sgps_grounded_rewrites_remain_allowed():
    data = _fixture()
    source = data["source_context"]

    for claim in data["safe_rewrites"]:
        failures = fvs._find_source_semantic_fidelity_violations(claim, source)
        assert failures == [], (claim, failures)


def test_cadence_value_cannot_change_roles():
    source = (
        "The controller runs at 50 Hz. "
        "The recurrent depth encoder updates at 10 Hz."
    )
    failures = fvs._find_source_semantic_fidelity_violations(
        "実機では推論・制御ループ全体を10 Hzで実行する。",
        source,
    )
    assert "source-fidelity cadence role mismatch: 10 Hz" in failures

    safe = fvs._find_source_semantic_fidelity_violations(
        "深度エンコーダは10 Hzで更新され、制御ループは50 Hzで動く。",
        source,
    )
    assert safe == []


def test_canonical_contract_names_source_fidelity_failures_explicitly():
    contract = cac.canonical_writer_contract()
    assert "別工程・別ハードウェア・別測定条件" in contract
    assert "補助Evidenceの固有ハードウェアや数値" in contract
    assert "「計算グラフから除外」を「処理自体が不要」" in contract
    assert "「改善」を「最適解への収束・完全解決」" in contract


def test_fact_gate_is_wired_to_source_semantic_fidelity_guard():
    pipeline = (ROOT / "pipeline.py").read_text(encoding="utf-8")
    assert "_find_source_semantic_fidelity_violations_impl" in pipeline
    assert "failures.extend(_find_source_semantic_fidelity_violations(claim_surface, source_context))" in pipeline
    assert 'parsed.get("title_text", "")' in pipeline
