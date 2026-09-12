from types import SimpleNamespace

import run260_gemini_model_routing as run260


def _pipeline(pool):
    calls = []

    def call_model_pool(*args, **kwargs):
        calls.append((args, kwargs))
        return "ok"

    def call_deep_dive_pool(prompt, config=None, kind="deep_dive", request_context="", request_origin="new"):
        calls.append(((prompt, config, kind), {"request_context": request_context, "request_origin": request_origin}))
        return "ok"

    return SimpleNamespace(
        DEEP_DIVE_MODEL_POOL=list(pool),
        _call_model_pool=call_model_pool,
        _call_deep_dive_pool=call_deep_dive_pool,
        MODEL_DAILY_BUDGETS={},
        PERSISTENT_GEMINI_COUNTER=SimpleNamespace(model_budgets={}),
    ), calls


def test_implicit_legacy_singleton_keeps_default_37_first():
    p, _ = _pipeline(["gemini-3.6-flash"])
    run260.install(p)

    assert p.DEEP_DIVE_MODEL_POOL == [
        "gemini-3.7-flash",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ]


def test_explicit_38_first_order_is_preserved():
    p, _ = _pipeline(["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash"])
    run260.install(p)

    assert p.DEEP_DIVE_MODEL_POOL == [
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3.7-flash",
    ]


def test_missing_defaults_are_appended_after_explicit_models():
    p, _ = _pipeline(["custom-model", "gemini-3.8-flash"])
    run260.install(p)

    assert p.DEEP_DIVE_MODEL_POOL == [
        "custom-model",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ]


def test_duplicate_explicit_models_are_removed_without_reordering():
    p, _ = _pipeline([
        "gemini-3.8-flash",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.8-flash",
    ])
    run260.install(p)

    assert p.DEEP_DIVE_MODEL_POOL[:2] == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert len(p.DEEP_DIVE_MODEL_POOL) == len(set(p.DEEP_DIVE_MODEL_POOL))


def test_quality_retry_still_prefers_38_and_is_bounded_to_two_models():
    p, calls = _pipeline(["gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash"])
    run260.install(p)

    p._call_deep_dive_pool("prompt", {}, "quality_retry")

    args, kwargs = calls[-1]
    assert args[2] == "quality_retry"
    assert args[4] == ["gemini-3.8-flash", "gemini-3.6-flash"]
    assert kwargs["deep_dive"] is True
