"""Zero-provider regression for the selected 83-point P5 Writer.

Structural PASS is NEVER editorial score approval. The three archived
human-scored original manuscripts remain the editorial comparison authority.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments import v3_p5_baseline_repro as golden
from local_skills.v3_p5_call_contract import (
    P5BaselineCallContractError, pure_p5_writer_config,
)


def test_selected_p5_prompts_are_byte_identical_for_all_three_golden_cases():
    assert golden.BASELINE == "95016a65701979063f56130bf181bca831661f5d"
    assert golden.BASELINE_LIVE_RUN == 39963513015
    assert golden.BASELINE_HUMAN_SCORES == {
        "FFT": 75, "Elastic": 85, "Claude": 88,
    }
    prompts = golden.frozen_case_prompts()
    assert len(prompts) == 3
    assert len({case_id for case_id, _ in prompts}) == 3
    for _, prompt in prompts:
        assert "1. Writer Reaction" in prompt
        assert "2. Editorial Discovery" in prompt
        assert "3. Cognitive Shift" in prompt
        assert "4. Persona Article Generation" in prompt
        assert "5. Fact-Safe Review" in prompt
        assert "【P5 会話の温度とテンポ】" in prompt
        assert "【P5 読者が先に発見する】" in prompt


def test_original_call_config_has_no_integrated_system_or_forced_temperature():
    assert pure_p5_writer_config(
        {"system_instruction": "AIIF Editor Persona", "max_output_tokens": 18000,
         "temperature": 0.65},
        editorial_style="v3_p5", writer_boundary="original",
        request_origin="article_revalidation", request_kind="deep_dive",
    ) == {}


@pytest.mark.parametrize("style,boundary,origin,kind", [
    ("classic", "original", "article_revalidation", "deep_dive"),
    ("v3_p5", "managed", "article_revalidation", "deep_dive"),
    ("v3_p5", "original", "new", "deep_dive"),
    ("v3_p5", "original", "article_revalidation", "quality_retry"),
])
def test_original_call_rejects_every_nonproof_path(style, boundary, origin, kind):
    with pytest.raises(P5BaselineCallContractError):
        pure_p5_writer_config(
            {}, editorial_style=style, writer_boundary=boundary,
            request_origin=origin, request_kind=kind,
        )


def test_original_call_fails_closed_if_external_url_or_search_tools_active():
    with pytest.raises(P5BaselineCallContractError, match="no provider search"):
        pure_p5_writer_config(
            {"tools": [{"url_context": {}}]},
            editorial_style="v3_p5", writer_boundary="original",
            request_origin="article_revalidation", request_kind="deep_dive",
        )


def test_frozen_proof_explicitly_rejects_preview_and_flash_lite():
    assert "gemini-3-flash-preview" not in golden.ALLOWED_MODELS
    assert not any("preview" in model or "lite" in model for model in golden.ALLOWED_MODELS)
    assert set(golden.ALLOWED_MODELS) == {
        "gemini-3.5-flash", "gemini-3.6-flash",
        "gemini-3.7-flash", "gemini-3.8-flash",
    }


def test_provider_free_preflight_never_sends_api_or_claims_editorial_approval(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(golden, "OUTPUT", tmp_path)
    monkeypatch.delenv("AIIF_P5_LIVE_CONFIRM", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("AIIF_P5_PROOF_MODEL", "gemini-3.5-flash")
    golden.main()
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["status"] == "PROVIDER_FREE_BASELINE_PREFLIGHT_PASS"
    assert manifest["provider_attempts"] == 0
    assert manifest["human_quality_approval"] is False
    assert manifest["generation_config_overrides"] is False
    assert manifest["system_instruction"] is False
    assert (manifest["note_write"], manifest["notion_write"], manifest["publication"]) == (
        False, False, False,
    )


def test_p5_83point_replay_cannot_run_unknown_or_preview_model(
    tmp_path, monkeypatch,
):
    monkeypatch.setattr(golden, "OUTPUT", tmp_path)
    monkeypatch.setenv("AIIF_P5_PROOF_MODEL", "gemini-3-flash-preview")
    monkeypatch.delenv("AIIF_P5_LIVE_CONFIRM", raising=False)
    with pytest.raises(RuntimeError, match="Forbidden or unknown"):
        golden.main()


def test_original_phase0_call_was_plain_no_system_or_token_config():
    # Programmatic check protects against accidentally calling an altered
    # Phase0 provider contract the selected P5 never used.
    import inspect
    source = inspect.getsource(golden.main)
    assert 'response = client.models.generate_content(model=model, contents=prompt)' in source
    assert 'system_instruction=' not in source
    assert 'temperature=' not in source
