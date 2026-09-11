import types

import run346_backlog_budget_reserve as run346


class Budget:
    def __init__(self, budget, used=0):
        self.budget = budget
        self.used = used

    def can_request(self):
        return self.used < self.budget


def make_pipeline(total=12, pending=2, deferred=1):
    p = types.SimpleNamespace()
    p.DEEP_DIVE_MODEL_BUDGET = Budget(total)
    p.GEMINI_PENDING_RETRY_REQUEST_BUDGET = pending
    p.DEFERRED_DEEP_DIVE_MAX_PER_RUN = deferred
    p.logger = None
    seen = {}

    def backlog(items, generated, rank):
        seen["budget"] = p.DEEP_DIVE_MODEL_BUDGET.budget
        seen["used"] = p.DEEP_DIVE_MODEL_BUDGET.used
        seen["pending"] = len(items or [])
        return generated, rank

    p.process_article_backlog = backlog
    return p, seen


def test_reserves_existing_budget_without_increasing_total(monkeypatch):
    monkeypatch.delenv("GEMINI_BACKLOG_RESERVED_REQUESTS", raising=False)
    p, seen = make_pipeline(total=12, pending=2, deferred=1)
    run346.install(p)
    assert p.DEEP_DIVE_MODEL_BUDGET.budget == 9
    p.DEEP_DIVE_MODEL_BUDGET.used = 9
    p.process_article_backlog([{"repo": {}}], 0, 0)
    assert seen == {"budget": 12, "used": 9, "pending": 1}
    assert p.DEEP_DIVE_MODEL_BUDGET.budget == 12


def test_never_resets_used_requests(monkeypatch):
    monkeypatch.delenv("GEMINI_BACKLOG_RESERVED_REQUESTS", raising=False)
    p, seen = make_pipeline(total=12, pending=2, deferred=1)
    p.DEEP_DIVE_MODEL_BUDGET.used = 5
    run346.install(p)
    p.process_article_backlog([], 0, 0)
    assert seen["used"] == 5


def test_reserve_is_capped_by_original_budget(monkeypatch):
    monkeypatch.setenv("GEMINI_BACKLOG_RESERVED_REQUESTS", "99")
    p, _ = make_pipeline(total=4)
    run346.install(p)
    assert p.DEEP_DIVE_MODEL_BUDGET.budget == 0
    p.process_article_backlog([], 0, 0)
    assert p.DEEP_DIVE_MODEL_BUDGET.budget == 4


def test_install_is_idempotent(monkeypatch):
    monkeypatch.delenv("GEMINI_BACKLOG_RESERVED_REQUESTS", raising=False)
    p, _ = make_pipeline(total=12)
    run346.install(p)
    wrapped = p.process_article_backlog
    run346.install(p)
    assert p.process_article_backlog is wrapped
    assert p.DEEP_DIVE_MODEL_BUDGET.budget == 9
