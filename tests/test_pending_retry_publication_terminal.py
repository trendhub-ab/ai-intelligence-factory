from types import SimpleNamespace

import pending_retry_validation as fast_lane


class _Budget:
    def can_request(self):
        return True


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


def _pipeline(calls):
    return SimpleNamespace(
        PENDING_RETRY_REQUEST_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_BUDGET=_Budget(),
        GEMINI_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_POOL=["m1"],
        _model_pool_has_session_candidate=lambda pool: True,
        generate_intelligence_report=lambda repo, *args, **kwargs: calls.append((repo, args, kwargs)) or ("manuscript", "accepted"),
        logger=_Logger(),
    )


def _item(page_id="a" * 32):
    return {
        "notion_page_id": page_id,
        "screening_score": 90,
        "screening_reason": "transient provider failure",
        "repo": {"nameWithOwner": "vendor/project"},
    }


def test_pending_retry_blocks_already_delivered_before_model(monkeypatch):
    calls = []
    pipeline = _pipeline(calls)
    monkeypatch.setattr(
        fast_lane,
        "automatic_regeneration_decision",
        lambda page_id: (False, "already_delivered"),
        raising=False,
    )

    result = fast_lane.run_pending_retry_lane(pipeline, [_item()])

    assert result["attempted"] == 0
    assert result["quality_passed"] == 0
    assert calls == []


def test_pending_retry_fails_closed_when_delivery_authority_unavailable(monkeypatch):
    calls = []
    pipeline = _pipeline(calls)
    monkeypatch.setattr(
        fast_lane,
        "automatic_regeneration_decision",
        lambda page_id: (False, "delivery_authority_unavailable"),
        raising=False,
    )

    result = fast_lane.run_pending_retry_lane(pipeline, [_item()])

    assert result["attempted"] == 0
    assert calls == []


def test_pending_retry_missing_article_identity_fails_closed(monkeypatch):
    calls = []
    pipeline = _pipeline(calls)
    seen = []
    monkeypatch.setattr(
        fast_lane,
        "automatic_regeneration_decision",
        lambda page_id: seen.append(page_id) or (True, "not_queued"),
        raising=False,
    )

    result = fast_lane.run_pending_retry_lane(pipeline, [_item("")])

    assert result["attempted"] == 0
    assert calls == []
    assert seen == []


def test_pending_retry_prepublication_item_remains_eligible(monkeypatch):
    calls = []
    pipeline = _pipeline(calls)
    monkeypatch.setattr(
        fast_lane,
        "automatic_regeneration_decision",
        lambda page_id: (True, "not_queued"),
        raising=False,
    )

    result = fast_lane.run_pending_retry_lane(pipeline, [_item()])

    assert result["attempted"] == 1
    assert result["quality_passed"] == 1
    assert len(calls) == 1
