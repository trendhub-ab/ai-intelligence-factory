import sys
from types import SimpleNamespace

import pending_retry_validation


class _Budget:
    def __init__(self):
        self.can_request_calls = 0

    def can_request(self):
        self.can_request_calls += 1
        return True


class _Logger:
    def info(self, *args, **kwargs):
        pass


def _pipeline(model_calls):
    return SimpleNamespace(
        PENDING_RETRY_REQUEST_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_BUDGET=_Budget(),
        GEMINI_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_POOL=["m1"],
        _model_pool_has_session_candidate=lambda pool: True,
        logger=_Logger(),
        generate_intelligence_report=lambda *args, **kwargs: model_calls.append((args, kwargs)) or ("article", "accepted"),
    )


def _install_delivery(monkeypatch, state, *, configured=True):
    fake = SimpleNamespace(
        DEST_DATA_SOURCE_ID="configured" if configured else "",
        DEST_DATABASE_ID="",
        classify_exact_delivery_state=lambda _: state,
    )
    monkeypatch.setitem(sys.modules, "note_ready_sync", fake)


def _item(page_id="a" * 32):
    return {
        "notion_page_id": page_id,
        "screening_score": 90,
        "screening_reason": "retry",
        "repo": {"nameWithOwner": "vendor/story"},
    }


def test_already_delivered_pending_retry_skips_before_budget_and_model(monkeypatch):
    _install_delivery(monkeypatch, "already_delivered")
    calls = []
    pipeline = _pipeline(calls)

    result = pending_retry_validation.run_pending_retry_lane(pipeline, [_item()])

    assert result["attempted"] == 0
    assert calls == []
    assert pipeline.PENDING_RETRY_REQUEST_BUDGET.can_request_calls == 0
    assert pipeline.DEEP_DIVE_MODEL_BUDGET.can_request_calls == 0
    assert pipeline.GEMINI_BUDGET.can_request_calls == 0


def test_missing_delivery_authority_pending_retry_fails_closed(monkeypatch):
    _install_delivery(monkeypatch, "not_queued", configured=False)
    calls = []
    pipeline = _pipeline(calls)

    result = pending_retry_validation.run_pending_retry_lane(pipeline, [_item()])

    assert result["attempted"] == 0
    assert calls == []


def test_missing_article_identity_pending_retry_fails_closed(monkeypatch):
    _install_delivery(monkeypatch, "not_queued")
    calls = []
    pipeline = _pipeline(calls)

    result = pending_retry_validation.run_pending_retry_lane(pipeline, [_item("")])

    assert result["attempted"] == 0
    assert calls == []


def test_not_queued_pending_retry_remains_eligible(monkeypatch):
    _install_delivery(monkeypatch, "not_queued")
    calls = []
    pipeline = _pipeline(calls)

    result = pending_retry_validation.run_pending_retry_lane(pipeline, [_item()])

    assert result["attempted"] == 1
    assert result["quality_passed"] == 1
    assert len(calls) == 1


def test_waiting_pending_retry_remains_eligible(monkeypatch):
    _install_delivery(monkeypatch, "waiting")
    calls = []
    pipeline = _pipeline(calls)

    result = pending_retry_validation.run_pending_retry_lane(pipeline, [_item()])

    assert result["attempted"] == 1
    assert len(calls) == 1
