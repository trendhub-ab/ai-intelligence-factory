"""Fail-closed budgeted original-P5 provider proof, no external API calls."""
from types import SimpleNamespace

import pytest

from local_skills.v3_p5_call_contract import P5BaselineCallContractError
from local_skills.v3_p5_pure_provider import (
    P5PureProviderError, call_p5_pure_writer,
)

SOURCE = {
    "evidence_result": {"state": "SUFFICIENT"},
    "evidence_sufficient": True,
    "primary_url": "https://example.org/primary",
    "verification_context": "Source-native facts with verified scope and qualifiers. "
                            "This dataset has a comparison but does not show "
                            "human treatment efficacy or clinical benefit.",
}
PROMPT = ("1. Writer Reaction\n2. Editorial Discovery\n3. Cognitive Shift\n"
          "4. Persona Article Generation\n5. Fact-Safe Review")


def runtime(models=None):
    sends = []
    if models is None:
        models = ("gemini-3-flash-preview", "gemini-3.5-flash", "gemini-3.7-flash",
                  "gemini-3.1-flash-lite", "gemini-3.8-flash")
    def pool(prompt, config, kind, reserve, choices, **kwargs):
        sends.append((prompt, config, kind, reserve, choices, kwargs))
        return (SimpleNamespace(text="valid output", candidates=[]), choices[0])
    obj = SimpleNamespace(
        AIIF_EDITORIAL_STYLE="v3_p5",
        AIIF_P5_WRITER_BOUNDARY="original",
        DEEP_DIVE_MODEL_POOL=list(models),
        _call_model_pool=pool,
        _extract_usage_metadata=lambda response: None,
        extract_grounding_metadata=lambda *a: {
            "grounding_status": "Source Native", "evidence_urls": [SOURCE["primary_url"]],
        },
        GROUNDING_FAILED="Failed",
        SELECTED_DEEP_DIVE_MODEL=None,
    )
    return obj, sends


def test_only_allowlisted_nonpreview_models_reach_canonical_budgeted_pool():
    p, sends = runtime()
    response, grounded = call_p5_pure_writer(
        p, PROMPT, {}, SOURCE,
        request_kind="deep_dive", request_origin="article_revalidation",
        request_context="p5:golden",
    )
    assert response.text == "valid output"
    assert len(sends) == 1
    _, config, kind, reserve, candidates, kw = sends[0]
    assert config == {}
    assert kind == "deep_dive" and reserve == 0
    assert candidates == ["gemini-3.8-flash"]
    assert kw == {
        "deep_dive": True, "request_context": "p5:golden",
        "request_origin": "article_revalidation",
    }
    assert p.SELECTED_DEEP_DIVE_MODEL == "gemini-3.8-flash"
    assert grounded["evidence_urls"] == [SOURCE["primary_url"]]


@pytest.mark.parametrize("bad", ["new", "pending_retry", "quality_retry"])
def test_rejects_nonvalidation_origin_or_kind_before_provider_send(bad):
    p, sends = runtime()
    with pytest.raises(P5BaselineCallContractError):
        call_p5_pure_writer(
            p, PROMPT, {}, SOURCE,
            request_kind="quality_retry" if bad == "quality_retry" else "deep_dive",
            request_origin="article_revalidation" if bad == "quality_retry" else bad,
        )
    assert sends == []


def test_managed_or_classic_is_never_pure():
    for style, boundary in (("classic", "original"), ("v3_p5", "managed")):
        p, sends = runtime()
        p.AIIF_EDITORIAL_STYLE = style
        p.AIIF_P5_WRITER_BOUNDARY = boundary
        with pytest.raises(P5BaselineCallContractError):
            call_p5_pure_writer(
                p, PROMPT, {}, SOURCE,
                request_origin="article_revalidation",
            )
        assert sends == []


def test_preview_or_lite_only_pool_fails_before_provider():
    p, sends = runtime(("gemini-3-flash-preview", "gemini-3.5-flash-lite"))
    with pytest.raises(P5PureProviderError, match="No allowlisted"):
        call_p5_pure_writer(
            p, PROMPT, {}, SOURCE,
            request_origin="article_revalidation",
        )
    assert sends == []


def test_unverified_evidence_is_rejected_before_provider():
    p, sends = runtime()
    unverified = dict(SOURCE, evidence_sufficient=False, evidence_result={"state": "INSUFFICIENT"})
    with pytest.raises(P5PureProviderError, match="Unverified"):
        call_p5_pure_writer(
            p, PROMPT, {}, unverified,
            request_origin="article_revalidation",
        )
    assert sends == []


def test_native_budget_pool_failure_never_uses_ungated_backup():
    p, sends = runtime()
    def stop_budget(*a, **kw):
        sends.append("budget reject")
        raise RuntimeError("Deep Dive run budget exhausted")
    p._call_model_pool = stop_budget
    with pytest.raises(RuntimeError, match="budget exhausted"):
        call_p5_pure_writer(
            p, PROMPT, {}, SOURCE,
            request_origin="article_revalidation",
        )
    assert sends == ["budget reject"]



def test_incomplete_editorial_stage_prompt_never_reaches_provider():
    p, sends = runtime()
    with pytest.raises(P5PureProviderError, match="five-stage"):
        call_p5_pure_writer(
            p, "1. Writer Reaction\\n2. Editorial Discovery",
            {}, SOURCE, request_origin="article_revalidation",
        )
    assert sends == []



def test_nonpersisting_new_origins_allow_pure_writer_but_cannot_be_spoofed():
    p, sends = runtime(("gemini-3.6-flash", "gemini-3.8-flash"))
    with pytest.raises(P5BaselineCallContractError):
        call_p5_pure_writer(p, PROMPT, {}, SOURCE, request_origin="new")
    assert sends == []
    p._P5_NONPERSISTING_VALIDATION_ACTIVE = True
    _, _ = call_p5_pure_writer(p, PROMPT, {}, SOURCE, request_origin="new")
    assert len(sends) == 1
    assert sends[0][4] == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert sends[0][5]["request_origin"] == "new"


def test_p5_provider_38_36_only_with_reverse_order_and_preview_never_selected():
    p, sends = runtime(("gemini-3.6-flash", "gemini-3.7-flash",
                        "gemini-3-flash-preview", "gemini-3.8-flash"))
    call_p5_pure_writer(p, PROMPT, {}, SOURCE, request_origin="article_revalidation")
    assert sends[0][4] == ["gemini-3.8-flash", "gemini-3.6-flash"]



def test_original_p5_provider_config_reaches_deep_dive_without_forced_low_thinking():
    """Catch real integration regression: downstream resilience used to add thinking=low."""
    from local_skills.v3_p5_call_contract import P5OriginalWriterConfig
    from gemini_provider_resilience import _deep_dive_generation_config
    p, sends = runtime(("gemini-3.6-flash", "gemini-3.8-flash"))
    _, _ = call_p5_pure_writer(
        p, PROMPT, {}, SOURCE, request_origin="article_revalidation",
    )
    assert len(sends) == 1
    marker = sends[0][1]
    assert type(marker) is P5OriginalWriterConfig
    assert marker == {}
    assert _deep_dive_generation_config(marker, "deep_dive") is None
    assert _deep_dive_generation_config({}, "deep_dive") == {
        "thinking_config": {"thinking_level": "low"},
    }
    assert _deep_dive_generation_config(None, "deep_dive") == {
        "thinking_config": {"thinking_level": "low"},
    }


def test_p5_original_config_marker_cannot_hide_generation_overrides():
    from local_skills.v3_p5_call_contract import P5OriginalWriterConfig
    from gemini_provider_resilience import _deep_dive_generation_config
    marker = P5OriginalWriterConfig()
    marker["system_instruction"] = "Unapproved hidden persona"
    with pytest.raises(ValueError, match="cannot contain overrides"):
        _deep_dive_generation_config(marker, "deep_dive")
    # Passing the marker for unrelated provider kinds cannot disable normal config.
    assert _deep_dive_generation_config(P5OriginalWriterConfig(), "screening") == {
        "thinking_config": {"thinking_level": "low"},
    }
