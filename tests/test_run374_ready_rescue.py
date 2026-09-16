import types

import article_revalidation
import run374_ready_rescue as run374


class Budget:
    def __init__(self, budget, used=0):
        self.budget = budget
        self.used = used

    def can_request(self):
        return self.used < self.budget


def test_run58_antigravity_vague_days_is_subtracted_without_replacement():
    article = (
        "# Boost deep reasoning\n\n"
        "この変更は数日で利用できるようになります。導入判断は一次情報を確認してから行います。\n\n"
        "## 出典\nhttps://example.com/source\n"
    )
    reasons = [{"message": "unsupported vague quantified claim: 数日"}]
    repaired, changes = run374.remove_unsupported_vague_quantities(article, reasons)
    assert "数日" not in repaired
    assert "短期間" not in repaired
    assert "すぐ" not in repaired
    assert "導入判断は一次情報を確認してから行います" in repaired
    assert "https://example.com/source" in repaired
    assert changes == ["remove_unsupported_vague_quantity:数日"]


def test_vague_rescue_does_not_touch_code_heading_or_url():
    article = "# 数日で試す\n\n```text\n数日で\n```\n\nhttps://example.com/数日\n"
    reasons = ["unsupported vague quantified claim: 数日"]
    repaired, changes = run374.remove_unsupported_vague_quantities(article, reasons)
    assert repaired == article
    assert changes == []


def test_unsafe_bare_vague_phrase_declines_instead_of_damaging_grammar():
    article = "提供まで数日かかる可能性があります。"
    repaired, changes = run374.remove_unsupported_vague_quantities(
        article, ["unsupported vague quantified claim: 数日"]
    )
    assert repaired == article
    assert changes == []


def test_unrelated_fact_failure_never_triggers_vague_rescue():
    article = "数日で利用できます。"
    repaired, changes = run374.remove_unsupported_vague_quantities(
        article, ["unsupported numeric claim: 42%"]
    )
    assert repaired == article
    assert changes == []


def test_rescue_wrapper_reuses_full_gate_revalidation_path():
    p = types.SimpleNamespace()

    def base(parsed, reason_rows):
        return dict(parsed), ["base"]

    p._apply_deterministic_publication_rescue = base
    p.process_article_backlog = lambda items, generated, rank: (generated, rank)
    p.TOP_N_FOR_DEEP_DIVE = 0
    p.DEEP_DIVE_MODEL_BUDGET = Budget(12)
    p._run346_original_deep_dive_budget = 12
    p.logger = None
    run374.install(p)
    repaired, changes = p._apply_deterministic_publication_rescue(
        {"note_draft": "提供条件は数日で変わる可能性があります。"},
        [{"message": "unsupported vague quantified claim: 数日"}],
    )
    assert "数日" not in repaired["note_draft"]
    assert "base" in changes
    assert "remove_unsupported_vague_quantity:数日" in changes


def test_two_removed_numeric_sentences_revalidate_without_forcing_model_retry():
    p = types.SimpleNamespace()

    def base(parsed, reason_rows):
        out = dict(parsed)
        out["_rescue_loss"] = {
            "removed_sentences": 2,
            "important_numeric_removed": True,
            "loss_exceeded": True,
        }
        return out, ["remove_unsupported_sentence:68.6%", "remove_unsupported_sentence:97.7%"]

    p._apply_deterministic_publication_rescue = base
    p.process_article_backlog = lambda items, generated, rank: (generated, rank)
    p.TOP_N_FOR_DEEP_DIVE = 0
    p.DEEP_DIVE_MODEL_BUDGET = Budget(12)
    p._run346_original_deep_dive_budget = 12
    p.logger = None
    run374.install(p)
    repaired, _ = p._apply_deterministic_publication_rescue({"note_draft": "本文"}, [])
    assert repaired["_rescue_loss"]["removed_sentences"] == 2
    assert repaired["_rescue_loss"]["important_numeric_removed"] is True
    assert repaired["_rescue_loss"]["loss_exceeded"] is False


def test_three_removed_sentences_remain_fail_closed():
    p = types.SimpleNamespace()

    def base(parsed, reason_rows):
        out = dict(parsed)
        out["_rescue_loss"] = {
            "removed_sentences": 3,
            "important_numeric_removed": True,
            "loss_exceeded": False,
        }
        return out, ["base"]

    p._apply_deterministic_publication_rescue = base
    p.process_article_backlog = lambda items, generated, rank: (generated, rank)
    p.TOP_N_FOR_DEEP_DIVE = 0
    p.DEEP_DIVE_MODEL_BUDGET = Budget(12)
    p._run346_original_deep_dive_budget = 12
    p.logger = None
    run374.install(p)
    repaired, _ = p._apply_deterministic_publication_rescue({"note_draft": "本文"}, [])
    assert repaired["_rescue_loss"]["loss_exceeded"] is True


def test_reserved_ready_rescue_spends_at_most_one_existing_request(monkeypatch):
    calls = []

    def fake_recovery(pipeline, generated_count, next_candidate_rank, limit=1):
        calls.append((pipeline.DEEP_DIVE_MODEL_BUDGET.budget, pipeline._READY_RESCUE_ACTIVE, limit))
        # Simulate exactly one provider reservation.
        pipeline.DEEP_DIVE_MODEL_BUDGET.used += 1
        return generated_count, next_candidate_rank

    monkeypatch.setattr(article_revalidation, "run_existing_editorial_recovery", fake_recovery)
    p = types.SimpleNamespace(
        TOP_N_FOR_DEEP_DIVE=3,
        DEEP_DIVE_MODEL_BUDGET=Budget(12, used=11),
        _run346_original_deep_dive_budget=12,
        logger=None,
    )
    result = run374.run_reserved_ready_rescue(p, 0, 5)
    assert result == (0, 5)
    assert calls == [(12, True, 1)]
    assert p.DEEP_DIVE_MODEL_BUDGET.used == 12
    assert p.DEEP_DIVE_MODEL_BUDGET.budget == 12
    assert p._READY_RESCUE_ACTIVE is False
    assert p._run374_ready_rescue_slot_consumed is True


def test_reserved_ready_rescue_never_increases_total_cap(monkeypatch):
    calls = []
    monkeypatch.setattr(
        article_revalidation,
        "run_existing_editorial_recovery",
        lambda *args, **kwargs: calls.append(1) or (0, 0),
    )
    p = types.SimpleNamespace(
        TOP_N_FOR_DEEP_DIVE=3,
        DEEP_DIVE_MODEL_BUDGET=Budget(12, used=12),
        _run346_original_deep_dive_budget=12,
        logger=None,
    )
    assert run374.run_reserved_ready_rescue(p, 0, 0) == (0, 0)
    assert calls == []
    assert p.DEEP_DIVE_MODEL_BUDGET.budget == 12


def test_preflight_rescue_runs_before_main_and_preserves_eight_fresh_requests(monkeypatch):
    calls = []
    seen = {}

    def fake_recovery(pipeline, generated_count, next_candidate_rank, limit=1):
        calls.append((pipeline.DEEP_DIVE_MODEL_BUDGET.budget, limit))
        pipeline.DEEP_DIVE_MODEL_BUDGET.used += 1
        return generated_count + 1, next_candidate_rank

    monkeypatch.setattr(article_revalidation, "run_existing_editorial_recovery", fake_recovery)
    p = types.SimpleNamespace(
        TOP_N_FOR_DEEP_DIVE=3,
        DEEP_DIVE_MODEL_BUDGET=Budget(8, used=0),
        _run346_original_deep_dive_budget=12,
        _run374_ready_rescue_reserved_requests=1,
        PUBLIC_DB_SYNC_MODE=False,
        SYNTHETIC_REGRESSION_MODE=False,
        logger=None,
    )
    p._apply_deterministic_publication_rescue = lambda parsed, reasons: (dict(parsed), [])
    p.process_article_backlog = lambda items, generated, rank: (generated, rank)

    def original_main():
        seen["budget"] = p.DEEP_DIVE_MODEL_BUDGET.budget
        seen["used"] = p.DEEP_DIVE_MODEL_BUDGET.used
        seen["target"] = p.TOP_N_FOR_DEEP_DIVE

    p.main = original_main
    run374.install(p)
    p.main()

    assert calls == [(1, 1)]
    assert seen == {"budget": 9, "used": 1, "target": 2}
    assert p.TOP_N_FOR_DEEP_DIVE == 3
    assert p._run374_ready_rescue_slot_consumed is True
    assert p._run374_ready_rescue_preflight_generated == 1


def test_preflight_without_provider_send_keeps_original_fresh_partition(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        article_revalidation,
        "run_existing_editorial_recovery",
        lambda pipeline, generated, rank, limit=1: (generated, rank),
    )
    p = types.SimpleNamespace(
        TOP_N_FOR_DEEP_DIVE=3,
        DEEP_DIVE_MODEL_BUDGET=Budget(8, used=0),
        _run346_original_deep_dive_budget=12,
        _run374_ready_rescue_reserved_requests=1,
        PUBLIC_DB_SYNC_MODE=False,
        SYNTHETIC_REGRESSION_MODE=False,
        logger=None,
    )
    p._apply_deterministic_publication_rescue = lambda parsed, reasons: (dict(parsed), [])
    p.process_article_backlog = lambda items, generated, rank: (generated, rank)
    p.main = lambda: seen.update(
        budget=p.DEEP_DIVE_MODEL_BUDGET.budget,
        target=p.TOP_N_FOR_DEEP_DIVE,
    )
    run374.install(p)
    p.main()

    assert seen == {"budget": 8, "target": 3}
    assert p.DEEP_DIVE_MODEL_BUDGET.used == 0
    assert p._run374_ready_rescue_slot_consumed is False
