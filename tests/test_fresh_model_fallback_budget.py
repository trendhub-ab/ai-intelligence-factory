"""Zero-provider falsification of Fresh's real 503 fallback + hard send budget."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

import fresh_model_fallback_budget as budget
import gemini_provider_resilience
import local_skills_daily_canary as daily_canary
from tests.test_run398_gemini_503_fallback import FakeAPIError, make_pipeline


def test_real_provider_routing_preserves_distinct_model_503_fallback(monkeypatch):
    pipeline, attempts, unavailable = make_pipeline()
    gemini_provider_resilience.install(pipeline)
    send_budget = budget.FreshModelSendBudget()
    pipeline._generate_via_chat = send_budget.wrapped(pipeline._generate_via_chat)
    response, selected = pipeline._call_model_pool(
        "same article prompt", None, "deep_dive", 0,
        ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"],
        deep_dive=True,
    )
    assert response == {"ok": True}
    assert selected == "gemini-3.6-flash"
    assert [model for model, _ in attempts] == [
        "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash",
    ]
    assert send_budget.article_slots == 3
    assert send_budget.pre_article_slots == 0
    assert len(unavailable) == 2


def test_503_storm_exhausts_four_model_pool_with_no_extra_sends(monkeypatch):
    pipeline, _, _ = make_pipeline()
    actual_sends = []
    def all_503(model, prompt, **kwargs):
        actual_sends.append(model)
        raise FakeAPIError(503)

    pipeline._generate_via_chat = all_503
    gemini_provider_resilience.install(pipeline)
    guard = budget.FreshModelSendBudget()
    pipeline._generate_via_chat = guard.wrapped(pipeline._generate_via_chat)
    with pytest.raises(pipeline.NoAvailableModelError):
        pipeline._call_model_pool(
            "same article prompt", None, "deep_dive", 0,
            ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"],
            deep_dive=True,
        )
    assert len(actual_sends) == budget.MAX_ARTICLE_SEND_SLOTS
    assert guard.total_slots == budget.MAX_ARTICLE_SEND_SLOTS
    assert all(model in {
        "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash",
        "gemini-3.5-flash",
    } for model in actual_sends)


def test_pre_article_fallback_and_total_cap_never_spill_to_extra_article():
    actual_sends = []
    def original(model, prompt, **kwargs):
        actual_sends.append((model, kwargs.get("request_kind")))
        return "ok"

    guard = budget.FreshModelSendBudget()
    wrapped = guard.wrapped(original)
    for _ in range(budget.MAX_PRE_ARTICLE_SEND_SLOTS):
        wrapped("screening-model", "batch", request_kind="screening_batch")
    with pytest.raises(budget.FreshProviderBudgetExhausted, match="pre-article model cap"):
        wrapped("another-screening-model", "batch", request_kind="global_calibration")
    for _ in range(budget.MAX_ARTICLE_SEND_SLOTS):
        wrapped("ranked-article-model", "same article", request_kind="deep_dive",
                count_as_deep_dive=True)
    with pytest.raises(budget.FreshProviderBudgetExhausted, match="hard cap"):
        wrapped("another-model", "same article", request_kind="deep_dive",
                count_as_deep_dive=True)
    assert len(actual_sends) == budget.MAX_TOTAL_SEND_SLOTS
    assert guard.snapshot()["total_slots_reserved"] == budget.MAX_TOTAL_SEND_SLOTS


def test_canary_restores_provider_and_disables_quality_retry_after_measurement(monkeypatch):
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY", "false")
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", "GitHub")
    repo = {"source": "GitHub", "nameWithOwner": "never-seen synthetic experiment"}
    captures = []
    actual_models = []
    usage = SimpleNamespace(records=[])

    def original_send(model_name, prompt, **kwargs):
        actual_models.append(model_name)
        if model_name == "gemini-3.8-flash":
            raise FakeAPIError(503)
        usage.records.append({"kind": kwargs.get("request_kind")})
        return {"ok": True}

    original = original_send
    mock = SimpleNamespace(
        MAX_QUALITY_RETRIES=2,
        ENABLE_DETERMINISTIC_PUBLICATION_RESCUE=True,
        _generate_via_chat=original,
        GEMINI_USAGE_AUDIT=usage,
        initialize_runtime=lambda: None,
        reset_article_style_memory=lambda: None,
        screen_candidates_in_batches=lambda rows: (rows, 0),
        calibrate_candidates=lambda rows: (rows, 0),
        NOTION_SAVE_THRESHOLD_SCORE=60,
        _select_stocked_deep_dive_candidates=lambda rows: rows,
        logger=SimpleNamespace(info=lambda *args: None),
    )

    def generate(candidate, **kwargs):
        assert mock.MAX_QUALITY_RETRIES == 0
        assert mock.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE is False
        # The first 503 must be followed by another model on this same candidate.
        for model in ("gemini-3.8-flash", "gemini-3.7-flash"):
            try:
                mock._generate_via_chat(
                    model, "unchanged article", request_kind="deep_dive",
                    count_as_deep_dive=True,
                )
                break
            except FakeAPIError as exc:
                assert exc.code == 503
        mock._LOCAL_SKILLS_CANARY_LAST_COMPILE = {"verified": True}
        mock._LOCAL_SKILLS_CANARY_LAST_RESULT = {"fact": "PASS"}
        return True, "accepted"

    mock.generate_intelligence_report = generate
    monkeypatch.setattr(
        daily_canary, "_fresh_candidates",
        lambda pipeline: ([repo], {"requested_source": "GitHub", "source_attrition": {}}),
    )
    monkeypatch.setattr(daily_canary, "_screening_diagnostics",
                        lambda rows, pipeline: {"screened_count": len(rows)})
    monkeypatch.setattr(daily_canary, "_write", lambda result: captures.append(dict(result)))
    result = daily_canary.run(mock)
    assert result["outcome"] == "accepted"
    assert result["measurement_status"] == "MEASURED"
    assert result["provider_budget"]["article_slots_reserved"] == 2
    assert actual_models == ["gemini-3.8-flash", "gemini-3.7-flash"]
    assert mock._generate_via_chat is original
    assert mock.MAX_QUALITY_RETRIES == 2
    assert mock.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE is True
    assert len(captures) == 1


def test_pre_article_budget_exhaustion_is_unmeasured_and_restores_send(monkeypatch):
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY", "false")
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", "GitHub")
    repo = {"source": "GitHub", "nameWithOwner": "unmeasured synthetic"}
    output = []
    actual = []
    def original_send(model, prompt, **kwargs):
        actual.append(model)
        return {"ok": True}
    mock = SimpleNamespace(
        _generate_via_chat=original_send,
        MAX_QUALITY_RETRIES=3,
        ENABLE_DETERMINISTIC_PUBLICATION_RESCUE=True,
        initialize_runtime=lambda: None,
        reset_article_style_memory=lambda: None,
        logger=SimpleNamespace(info=lambda *args: None),
    )
    def screen(rows):
        for idx in range(budget.MAX_PRE_ARTICLE_SEND_SLOTS + 1):
            mock._generate_via_chat(str(idx), "screen", request_kind="screening_batch")
        raise AssertionError("excess screening call should never execute")
    mock.screen_candidates_in_batches = screen
    monkeypatch.setattr(daily_canary, "_fresh_candidates",
                        lambda pipeline: ([repo], {"requested_source": "GitHub"}))
    monkeypatch.setattr(daily_canary, "_write", lambda result: output.append(dict(result)))
    with pytest.raises(budget.FreshProviderBudgetExhausted):
        daily_canary.run(mock)
    assert len(actual) == budget.MAX_PRE_ARTICLE_SEND_SLOTS
    assert output[0]["measurement_status"] == "UNMEASURED"
    assert output[0]["provider_budget"]["pre_article_slots_reserved"] == budget.MAX_PRE_ARTICLE_SEND_SLOTS
    assert mock._generate_via_chat is original_send
