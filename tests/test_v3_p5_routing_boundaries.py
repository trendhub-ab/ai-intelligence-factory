"""P5 counterexample tests: deliberately try unsafe routes without Gemini API."""
import json
from types import SimpleNamespace

import pytest

import a_plus_editorial_orchestration as a_plus
from local_skills.v3_p5_contract import EDITORIAL_STAGES
from local_skills.v3_p5_rate_contract import (
    P5SendGuard, P5SendLimitError, P5_MODELS, ordered_p5_pool,
)


def runtime(*, style="v3_p5", boundary="original", with_native_send=False):
    first_calls = []
    pure_calls = []
    original_calls = []
    response = (
        "=== MANAGEMENT DATA ===\n"
        "・Decision: TRY\n"
        "・Action: 限定検証する。\n"
        "===NOTE_DRAFT_START===\n"
        "元の説明。\n前の原稿。"
    )
    final = (
        "# 新しい発見\n\n"
        "これは不思議だ。なぜ同じデータなのに違う結果になるのか。\n\n"
        "## 条件を追う\n\n"
        "数値に付く制約から、比較の仕組みが見えてくる。\n\n"
        "## 残る疑問\n\n"
        "ここは追加の実験が必要で、結論を急ぐべきではない。"
    )
    bundle = json.dumps({
        stage: (final if stage in ("Persona Article Generation", "Fact-Safe Review")
                else f"{stage}: 情報源から分かった事実と疑問")
        for stage in EDITORIAL_STAGES
    }, ensure_ascii=False)
    source = {
        "evidence_sufficient": True,
        "evidence_result": {"state": "SUFFICIENT"},
        "verification_context": (
            "The official technical source describes an experimental comparison. "
            "The results apply to a specific dataset and require more experiments."
        ),
        "primary_url": "https://example.org/primary",
        "evidence_metadata": {"required_qualifiers": ["実験の限定条件"]},
    }
    repo = {"name": "A new source article", "url": source["primary_url"]}

    def parse(text):
        if "===NOTE_DRAFT_START===" not in text:
            return {}
        tail = text.split("===NOTE_DRAFT_START===", 1)[1].strip()
        lines = tail.split("\n", 1)
        return {
            "title_text": lines[0], "note_draft": lines[-1],
            "source_summary_text": "一次情報の概要",
            "decision_text": "TRY", "decision_reason_text": "小さく検証",
            "action_text": "限定検証する",
        }

    p = SimpleNamespace(
        AIIF_EDITORIAL_STYLE=style,
        AIIF_P5_WRITER_BOUNDARY=boundary,
        DEEP_DIVE_MODEL_POOL=["gemini-3.6-flash", "gemini-3.8-flash"],
        SECTION_SPLIT_TOKEN="===NOTE_DRAFT_START===",
        EVIDENCE_SUFFICIENT="SUFFICIENT",
        build_decision_prompt=lambda **kw: "【Output Contract｜完成稿のみ】\nFirst pass",
        _parse_gemini_response=parse,
        should_attempt_dynamic_retry=lambda *args, **kwargs: (True, "ordinary_retry"),
        logger=None,
    )

    def normal_call(prompt, item, ctx, **kw):
        first_calls.append((prompt, dict(kw)))
        return SimpleNamespace(text=response), {"grounding_status": "Source Native"}

    def original_generate(*args, **kwargs):
        original_calls.append(dict(kwargs))
        return p.call_gemini_grounded_deep_dive(
            p.build_decision_prompt(evidence_result={"state": "SUFFICIENT"}),
            repo, source, request_kind="deep_dive", request_origin="new",
        )

    def pure_provider(prompt, item, ctx, **kw):
        assert p._P5_NONPERSISTING_VALIDATION_ACTIVE is True
        assert "1. Writer Reaction" in prompt
        assert "5. Fact-Safe Review" in prompt
        assert "Production A+ LocalSkills" not in prompt
        pure_calls.append(dict(kw))
        return SimpleNamespace(text=bundle), {"grounding_status": "Source Native"}

    p.call_gemini_grounded_deep_dive = normal_call
    p.generate_intelligence_report = original_generate
    p.call_p5_baseline_pure_writer = pure_provider
    if with_native_send:
        class BudgetStop(RuntimeError):
            pass
        p.DeepDiveRunBudgetExceededError = BudgetStop
        p._generate_via_chat = lambda model, prompt, **kw: "mock_sent"
    a_plus.install(p)
    return p, source, repo, first_calls, pure_calls, original_calls


def test_p5_original_new_source_runs_only_in_private_unpersisted_validation():
    p, source, repo, first, pure, calls = runtime()
    with pytest.raises(RuntimeError, match="persist_results=False"):
        p.generate_intelligence_report(repo)
    assert first == [] and pure == []
    response, _ = p.generate_intelligence_report(repo, persist_results=False)
    assert len(first) == len(pure) == len(calls) == 1
    assert pure[0]["request_origin"] == "new"
    assert "新しい発見" in response.text
    assert not p._P5_NONPERSISTING_VALIDATION_ACTIVE
    assert p.DEEP_DIVE_MODEL_POOL == ["gemini-3.6-flash", "gemini-3.8-flash"]


def test_p5_managed_is_also_never_allowed_to_persist_without_human_quality_review():
    p, _, repo, first, pure, _ = runtime(boundary="managed")
    with pytest.raises(RuntimeError, match="persist_results=False"):
        p.generate_intelligence_report(repo, persist_results=True)
    assert first == pure == []


def test_p5_dynamic_retry_and_direct_quality_retry_cannot_rescue_as_classic():
    p, source, repo, first, pure, _ = runtime()
    answer = p.should_attempt_dynamic_retry([], {"state": "SUFFICIENT"})
    assert answer == (False, "p5_human_editorial_review_required")
    with pytest.raises(RuntimeError, match="quality_retry is disabled"):
        p.call_gemini_grounded_deep_dive(
            "P5 retry", repo, source,
            request_kind="quality_retry", request_origin="new",
        )
    assert first == pure == []


def test_p5_new_source_outside_nonpersisting_context_cannot_call_original():
    p, source, repo, first, pure, _ = runtime()
    with pytest.raises(Exception, match="nonpersisting new-article validation"):
        p.call_gemini_grounded_deep_dive(
            p.build_decision_prompt(evidence_result={"state": "SUFFICIENT"}),
            repo, source, request_kind="deep_dive", request_origin="new",
        )
    assert len(first) == 1 and pure == []


def test_rate_guard_refuses_fourth_36_before_any_mock_provider_send():
    p, _, _, _, _, _ = runtime(with_native_send=True)
    for _ in range(3):
        assert p._generate_via_chat(
            "gemini-3.6-flash", "prompt", count_as_deep_dive=True
        ) == "mock_sent"
    with pytest.raises(p.DeepDiveRunBudgetExceededError, match="three-send cap"):
        p._generate_via_chat("gemini-3.6-flash", "4th", count_as_deep_dive=True)
    assert p._P5_SEND_GUARD.receipt()["by_model"]["gemini-3.6-flash"] == 3
    assert p._generate_via_chat("gemini-3.8-flash", "fallback",
                                count_as_deep_dive=True) == "mock_sent"
    with pytest.raises(p.DeepDiveRunBudgetExceededError, match="forbids"):
        p._generate_via_chat("gemini-3-flash-preview", "preview",
                             count_as_deep_dive=True)
    assert p._P5_SEND_GUARD.receipt()["by_model"]["gemini-3.8-flash"] == 1


def test_rate_guard_does_not_interfere_with_classic_or_screening():
    p, _, _, _, _, _ = runtime(style="classic", with_native_send=True)
    for _ in range(5):
        assert p._generate_via_chat(
            "gemini-3.6-flash", "classic", count_as_deep_dive=True
        ) == "mock_sent"
    assert p._P5_SEND_GUARD.receipt()["by_model"]["gemini-3.6-flash"] == 0
    p.AIIF_EDITORIAL_STYLE = "v3_p5"
    assert p._generate_via_chat("gemini-3.5-flash-lite", "screen",
                                count_as_deep_dive=False) == "mock_sent"
    assert p._P5_SEND_GUARD.receipt()["by_model"]["gemini-3.6-flash"] == 0


def test_model_pool_is_always_38_then_36():
    assert ordered_p5_pool(["gemini-3.6-flash", "gemini-3.8-flash"]) == list(P5_MODELS)
    assert ordered_p5_pool(["gemini-3.6-flash", "gemini-3-flash-preview"]) == [
        "gemini-3.6-flash"
    ]
    assert ordered_p5_pool(["gemini-3.7-flash", "gemini-3.5-flash-lite"]) == []
    guard = P5SendGuard()
    guard.pre_send("gemini-3.6-flash", p5_active=True)
    assert guard.counts["gemini-3.6-flash"] == 1
