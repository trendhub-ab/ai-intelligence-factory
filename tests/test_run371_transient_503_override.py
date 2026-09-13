from types import SimpleNamespace

import gemini_transient_recovery as transient


def _pipeline():
    unavailable = []

    def mark_model_unavailable(model_name, reason=""):
        unavailable.append((model_name, reason))

    return SimpleNamespace(
        _mark_model_unavailable=mark_model_unavailable,
        logger=None,
    ), unavailable


def test_default_production_threshold_remains_two(monkeypatch):
    monkeypatch.delenv("GEMINI_TRANSIENT_503_COOLDOWN_THRESHOLD", raising=False)
    p, unavailable = _pipeline()
    transient.install(p)

    p._mark_model_unavailable("gemini-3.8-flash", "503")
    assert unavailable == []
    p._mark_model_unavailable("gemini-3.8-flash", "503")
    assert unavailable == [("gemini-3.8-flash", "transient_503_cooldown:2")]


def test_validation_override_one_cools_down_after_first_503(monkeypatch):
    monkeypatch.setenv("GEMINI_TRANSIENT_503_COOLDOWN_THRESHOLD", "1")
    p, unavailable = _pipeline()
    transient.install(p)

    p._mark_model_unavailable("gemini-3.8-flash", "503")
    assert unavailable == [("gemini-3.8-flash", "transient_503_cooldown:1")]


def test_env_override_cannot_raise_production_default(monkeypatch):
    monkeypatch.setenv("GEMINI_TRANSIENT_503_COOLDOWN_THRESHOLD", "99")
    p, unavailable = _pipeline()
    transient.install(p)

    p._mark_model_unavailable("gemini-3.8-flash", "503")
    assert unavailable == []
    p._mark_model_unavailable("gemini-3.8-flash", "503")
    assert unavailable == [("gemini-3.8-flash", "transient_503_cooldown:2")]


def test_invalid_override_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("GEMINI_TRANSIENT_503_COOLDOWN_THRESHOLD", "invalid")
    p, unavailable = _pipeline()
    transient.install(p)

    p._mark_model_unavailable("gemini-3.8-flash", "503")
    assert unavailable == []


def test_non_503_reason_remains_immediately_authoritative(monkeypatch):
    monkeypatch.setenv("GEMINI_TRANSIENT_503_COOLDOWN_THRESHOLD", "1")
    p, unavailable = _pipeline()
    transient.install(p)

    p._mark_model_unavailable("gemini-3.8-flash", "404")
    assert unavailable == [("gemini-3.8-flash", "404")]
