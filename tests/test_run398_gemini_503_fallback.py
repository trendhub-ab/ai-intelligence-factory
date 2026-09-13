from contextlib import nullcontext
from types import SimpleNamespace

import gemini_provider_resilience


class FakeAPIError(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


class Budget:
    used = 0
    budget = 99

    def can_request(self):
        return True


class Logger:
    def warning(self, *args, **kwargs):
        pass

    def info(self, *args, **kwargs):
        pass


def make_pipeline():
    calls = []
    unavailable = []

    def generate(model, prompt, **kwargs):
        calls.append((model, kwargs.get("config")))
        if model in {"gemini-3.8-flash", "gemini-3.7-flash"}:
            raise FakeAPIError(503)
        return {"ok": True}

    p = SimpleNamespace(
        GEMINI_API_KEY="",
        APIError=FakeAPIError,
        _generate_via_chat=generate,
        _mark_model_unavailable=lambda model, reason="": unavailable.append((model, reason)),
        _mark_model_exhausted=lambda *args, **kwargs: None,
        _extract_retry_delay=lambda exc, default: default,
        _is_gemini_transport_timeout=lambda exc: False,
        _gemini_call_timeout=lambda seconds: nullcontext(),
        classify_gemini_quota_error=lambda exc: "",
        SESSION_EXHAUSTED_MODELS=set(),
        SESSION_UNAVAILABLE_MODELS=set(),
        DEEP_DIVE_MODEL_BUDGET=Budget(),
        PENDING_RETRY_REQUEST_BUDGET=Budget(),
        GEMINI_DEEP_DIVE_CALL_PACING_SECONDS=0,
        GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS=120,
        GEMINI_SCREENING_CALL_TIMEOUT_SECONDS=60,
        PendingRetryBudgetExceededError=type("PendingRetryBudgetExceededError", (Exception,), {}),
        DeepDiveRunBudgetExceededError=type("DeepDiveRunBudgetExceededError", (Exception,), {}),
        GeminiBudgetExceededError=type("GeminiBudgetExceededError", (Exception,), {}),
        GeminiCallTimeoutError=type("GeminiCallTimeoutError", (Exception,), {}),
        NoAvailableModelError=type("NoAvailableModelError", (Exception,), {}),
        logger=Logger(),
    )
    return p, calls, unavailable


def test_deep_dive_503_uses_one_request_per_model_then_reaches_stable_fallback():
    p, calls, unavailable = make_pipeline()
    gemini_provider_resilience.install(p)

    response, model = p._call_model_pool(
        "prompt",
        None,
        "deep_dive",
        0,
        ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"],
        deep_dive=True,
    )

    assert response == {"ok": True}
    assert model == "gemini-3.6-flash"
    assert [x[0] for x in calls] == ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash"]
    assert unavailable == [
        ("gemini-3.8-flash", "provider_503_deep_dive_fallback_preserved"),
        ("gemini-3.7-flash", "provider_503_deep_dive_fallback_preserved"),
    ]


def test_normal_deep_dive_forces_low_thinking_without_mutating_input_config():
    p, calls, _ = make_pipeline()
    original = {"max_output_tokens": 1234, "thinking_config": {"thinking_level": "medium"}}
    gemini_provider_resilience.install(p)

    p._call_model_pool(
        "prompt",
        original,
        "deep_dive",
        0,
        ["gemini-3.6-flash"],
        deep_dive=True,
    )

    assert original["thinking_config"]["thinking_level"] == "medium"
    assert calls[0][1]["thinking_config"]["thinking_level"] == "low"
    assert calls[0][1]["max_output_tokens"] == 1234


def test_quality_repair_keeps_caller_thinking_level():
    p, calls, _ = make_pipeline()
    config = {"thinking_config": {"thinking_level": "medium"}}
    gemini_provider_resilience.install(p)

    p._call_model_pool(
        "prompt",
        config,
        "quality_retry",
        0,
        ["gemini-3.6-flash"],
        deep_dive=True,
    )

    assert calls[0][1]["thinking_config"]["thinking_level"] == "medium"
