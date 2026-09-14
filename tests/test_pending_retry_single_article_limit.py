from types import SimpleNamespace

import pending_retry_validation as prv


class _Budget:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def can_request(self):
        return self.allowed


def _pipeline(generate):
    return SimpleNamespace(
        PENDING_RETRY_REQUEST_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_BUDGET=_Budget(),
        GEMINI_BUDGET=_Budget(),
        DEEP_DIVE_MODEL_POOL=["model-a", "model-b"],
        _model_pool_has_session_candidate=lambda pool: bool(pool),
        generate_intelligence_report=generate,
        logger=None,
    )


def _items():
    return [
        {
            "repo": {"nameWithOwner": "first/high-score"},
            "notion_page_id": "p1",
            "screening_score": 91,
            "screening_reason": "top candidate",
        },
        {
            "repo": {"nameWithOwner": "second/lower-score"},
            "notion_page_id": "p2",
            "screening_score": 80,
            "screening_reason": "must not be attempted",
        },
    ]


def test_failed_first_article_never_advances_to_second_candidate():
    calls = []

    def generate(repo, *args, **kwargs):
        calls.append(repo["nameWithOwner"])
        return None

    result = prv.run_pending_retry_lane(_pipeline(generate), _items())

    assert result == {"attempted": 1, "succeeded": 0}
    assert calls == ["first/high-score"]


def test_successful_first_article_stops_after_single_candidate():
    calls = []

    def generate(repo, *args, **kwargs):
        calls.append(repo["nameWithOwner"])
        return {"note_draft": "generated"}

    result = prv.run_pending_retry_lane(_pipeline(generate), _items())

    assert result == {"attempted": 1, "succeeded": 1}
    assert calls == ["first/high-score"]


def test_default_article_limit_is_one_even_when_success_target_is_larger():
    calls = []

    def generate(repo, *args, **kwargs):
        calls.append(repo["nameWithOwner"])
        return {"note_draft": "generated"}

    result = prv.run_pending_retry_lane(_pipeline(generate), _items(), success_target=2)

    assert result == {"attempted": 1, "succeeded": 1}
    assert calls == ["first/high-score"]


def test_fast_lane_env_keeps_three_request_budget_for_same_article_fallback():
    env = {}
    result = prv.prepare_fast_lane_env(env)

    assert result["GEMINI_PENDING_RETRY_REQUEST_BUDGET"] == "3"
    assert result[prv.FAST_LANE_ENV] == "1"
    assert prv.FAST_LANE_ARTICLE_ATTEMPT_LIMIT == 1
