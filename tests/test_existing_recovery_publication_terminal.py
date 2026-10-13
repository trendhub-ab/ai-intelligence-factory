from types import SimpleNamespace

import article_revalidation


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class _Budget:
    budget = 12

    def can_request(self):
        return True


class _DailyQuotaExhaustedError(Exception):
    pass


def _pipeline(generated_calls):
    return SimpleNamespace(
        logger=_Logger(),
        TOP_N_FOR_DEEP_DIVE=3,
        NOTION_API_KEY="test",
        GEMINI_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_POOL=["m1"],
        _model_pool_has_session_candidate=lambda pool: True,
        legal_safety_gate=lambda repo: (True, "SAFE"),
        generate_intelligence_report=lambda repo, **kwargs: generated_calls.append((repo, kwargs)) or "report",
        DailyQuotaExhaustedError=_DailyQuotaExhaustedError,
        _READY_RESCUE_ACTIVE=True,
    )


def _stale_item():
    return {
        "notion_page_id": "a" * 32,
        "repo": {"nameWithOwner": "vendor/project"},
        "screening_score": 81,
        "screening_reason": "current policy stale",
        "revalidation_article_status": "Ready",
        "revalidation_content_status": "Deep Dive",
        "revalidation_stale_ready": True,
    }


def test_ready_rescue_blocks_already_delivered_before_provider(monkeypatch):
    generated_calls = []
    pipeline = _pipeline(generated_calls)
    monkeypatch.setattr(article_revalidation, "select_revalidation_items", lambda *a, **k: [_stale_item()])
    monkeypatch.setattr(
        article_revalidation,
        "automatic_regeneration_decision",
        lambda page_id: (False, "already_delivered"),
        raising=False,
    )

    generated_count, next_rank = article_revalidation.run_existing_editorial_recovery(
        pipeline, generated_count=0, next_candidate_rank=4, limit=1
    )

    assert (generated_count, next_rank) == (0, 4)
    assert generated_calls == []


def test_ready_rescue_fails_closed_when_delivery_authority_unavailable(monkeypatch):
    generated_calls = []
    pipeline = _pipeline(generated_calls)
    monkeypatch.setattr(article_revalidation, "select_revalidation_items", lambda *a, **k: [_stale_item()])
    monkeypatch.setattr(
        article_revalidation,
        "automatic_regeneration_decision",
        lambda page_id: (False, "delivery_authority_unavailable"),
        raising=False,
    )

    generated_count, next_rank = article_revalidation.run_existing_editorial_recovery(
        pipeline, generated_count=0, next_candidate_rank=4, limit=1
    )

    assert (generated_count, next_rank) == (0, 4)
    assert generated_calls == []


def test_ready_rescue_keeps_prepublication_stale_ready_recoverable(monkeypatch):
    generated_calls = []
    pipeline = _pipeline(generated_calls)
    monkeypatch.setattr(article_revalidation, "select_revalidation_items", lambda *a, **k: [_stale_item()])
    monkeypatch.setattr(
        article_revalidation,
        "automatic_regeneration_decision",
        lambda page_id: (True, "not_queued"),
        raising=False,
    )

    generated_count, next_rank = article_revalidation.run_existing_editorial_recovery(
        pipeline, generated_count=0, next_candidate_rank=4, limit=1
    )

    assert generated_count == 1
    assert next_rank == 5
    assert len(generated_calls) == 1
