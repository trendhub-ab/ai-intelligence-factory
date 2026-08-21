import inspect
import json
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")
os.environ.setdefault("GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", "0")

try:
    from google import genai  # noqa: F401
except ImportError:
    google_mod = types.ModuleType("google")
    google_mod.__path__ = []
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class APIError(Exception):
        pass
    class Client:
        def __init__(self, **_kwargs):
            self.models = types.SimpleNamespace()
    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.update({"google": google_mod, "google.genai": genai_mod, "google.genai.errors": errors_mod})

import pipeline  # noqa: E402


def minimal_parsed(article: str | None = None, *, score: int = 68, title: str = "限定検証から判断する。"):
    article = article or """## はじめに
一次情報で確認できた範囲を整理します。

## まず、結論から
現時点では本番導入を急がず、限定環境で比較するのが妥当です。

## 何が起きた？
原資料では新しい方式が公開されています。

### 私ならこの範囲で試す。
限定PoCで比較テストし、既存方式との差を計測します。

### 最後に、判断をまとめる。
結果が確認できるまでは全面導入を見送ります。
"""
    return {
        "note_draft": article,
        "title_text": title,
        "decision_text": "TRY",
        "score": score,
        "score_breakdown_text": "Business Impact 15/25; Technical Impact 18/25; Urgency 10/20; Market Impact 10/15; Reliability 15/15; 合計 68/100",
        "source_summary_text": "一次情報で方式と制約を確認した。",
        "what_text": "新しい方式が公開された。",
        "why_important_text": "限定検証の価値がある。",
        "decision_reason_text": "一次情報で方式は確認できるが、本番一般化には追加検証が必要。",
        "action_text": "限定PoCで比較テストし、既存方式との差を計測します。",
        "article_value": 75,
        "paradigm_shift_text": "",
        "alternative_comparison_text": "",
        "migration_cost_text": "",
        "why_not_important_text": "",
        "who_should_use_text": "",
        "who_should_not_use_text": "",
        "future_scenario_text": "",
        "adoption_score": 0,
        "adoption_status": "",
    }


class TestFreeArticlePromptSeparation(unittest.TestCase):
    def test_prompt_requests_only_minimal_management_fields(self):
        prompt = pipeline.build_decision_prompt(
            "example/repo", "https://github.com/example/repo", 100, "example",
            source_context="一次情報です。", source="GitHub",
        )
        mgmt = prompt.split("最初に必ず次の見出しをそのまま出す。", 1)[1]
        self.assertIn("以下の8項目だけ", mgmt)
        requested = [
            "Source Summary", "What", "Why Important", "Decision", "Decision Reason",
            "Decision Score", "Action", "Article Value",
        ]
        for field in requested:
            self.assertIn(f"・{field}:", mgmt)
        forbidden_requests = [
            "・Adoption Score:", "・Adoption Status:", "・Evidence Confidence:",
            "・Production Readiness:", "・Main Risk:", "・Best For:", "・Avoid For:",
        ]
        for field in forbidden_requests:
            self.assertNotIn(field, mgmt)

    def test_parser_keeps_legacy_adoption_fields_backward_compatible(self):
        old = """=== MANAGEMENT DATA ===
・Source Summary: 一次情報。
・What: 公開された。
・Why Important: 検証価値。
・Decision: TRY
・Decision Reason: 比較する価値。
・Decision Score: Business Impact 15/25; Technical Impact 15/25; Urgency 10/20; Market Impact 10/15; Reliability 10/15; 合計 60/100
・Adoption Score: Evidence Quality 20/25; Production Maturity 15/25; Use-case Utility / Fit 15/20; Reliability / Security Risk 10/15; Integration / Migration Feasibility 7/10; Ecosystem / Support Durability 4/5; 合計 71/100
・Adoption Status: TEST
・Action: 限定PoCする。
・Article Value: 70
===NOTE_DRAFT_START===
旧形式も読める。

## はじめに
本文。
## まず、結論から
限定PoC。
### 最後に、判断をまとめる。
本番導入は待つ。
"""
        parsed = pipeline._parse_gemini_response(old)
        self.assertEqual(71, parsed["adoption_score"])
        self.assertEqual("TEST", parsed["adoption_status"])


class TestArticleGatePrecision(unittest.TestCase):
    def test_fact_gate_does_not_require_product_completeness_fields(self):
        parsed = minimal_parsed()
        ok, failures = pipeline.validate_fact_gate(
            parsed, "example", source_context=parsed["note_draft"], source="GitHub",
            evidence_metadata={}, source_info={"sufficient": True}, freshness={},
        )
        self.assertTrue(ok, failures)
        self.assertFalse(any("Alternative" in x or "Migration" in x or "Future" in x for x in failures))

    def test_year_month_is_not_treated_as_duration_numeric_claim(self):
        draft = "原資料は2026年8月に公開された。限定PoCで比較する。"
        failures = pipeline._find_unsupported_numeric_claims(draft, "原資料は2026年8月に公開された。", {})
        self.assertEqual([], failures)

    def test_negated_urgency_does_not_create_score_mismatch(self):
        parsed = minimal_parsed(score=50)
        parsed["note_draft"] += "\n現時点で今すぐ導入を推奨しません。"
        state, issues = pipeline.validate_publication_readiness_gate(parsed, parsed["note_draft"], {"sufficient": True})
        self.assertNotIn("score_narrative_mismatch", issues)
        self.assertEqual("PASS", state)

    def test_unnegated_urgency_still_creates_score_mismatch(self):
        parsed = minimal_parsed(score=50)
        parsed["action_text"] = "今すぐ本番導入する。"
        parsed["note_draft"] = "## はじめに\n一次情報を確認した。\n## まず、結論から\n今すぐ導入すべきです。\n### 最後に、判断をまとめる。\n導入を進める。"
        state, issues = pipeline.validate_publication_readiness_gate(parsed, parsed["note_draft"], {"sufficient": True})
        self.assertEqual("REVIEW", state)
        self.assertIn("score_narrative_mismatch", issues)


class TestDeterministicPublicationRescue(unittest.TestCase):
    def test_isolated_hype_is_removed_without_new_fact(self):
        parsed = minimal_parsed(article=minimal_parsed()["note_draft"] + "\nこれは唯一の選択肢です。")
        rows = pipeline.map_gate_reasons("fact", ["unsupported exclusivity/hype: 唯一"])
        rescued, changes = pipeline._apply_deterministic_publication_rescue(parsed, rows)
        self.assertIn("remove_unsupported_hype:唯一", changes)
        self.assertNotIn("唯一", rescued["note_draft"])
        self.assertIn("限定PoC", rescued["note_draft"])

    def test_unsupported_numeric_sentence_is_deleted(self):
        parsed = minimal_parsed(article=minimal_parsed()["note_draft"] + "\n8月には性能が倍増します。")
        rows = pipeline.map_gate_reasons("fact", ["unsupported numeric claim: 8月"])
        rescued, changes = pipeline._apply_deterministic_publication_rescue(parsed, rows)
        self.assertTrue(any(x.endswith(":8月") for x in changes))
        self.assertNotIn("8月", rescued["note_draft"])
        self.assertNotIn("性能が倍増", rescued["note_draft"])

    def test_unsupported_named_fact_sentence_is_deleted(self):
        parsed = minimal_parsed(article=minimal_parsed()["note_draft"] + "\nLlamaでの採用も確認されています。")
        rows = pipeline.map_gate_reasons("fact", ["source-boundary unsupported named fact: Llama"])
        rescued, changes = pipeline._apply_deterministic_publication_rescue(parsed, rows)
        self.assertTrue(any(x.endswith(":Llama") for x in changes))
        self.assertNotIn("Llama", rescued["note_draft"])

    def test_generic_unsupported_claim_is_not_auto_rewritten(self):
        parsed = minimal_parsed(article=minimal_parsed()["note_draft"] + "\n市場を支配します。")
        rows = pipeline.map_gate_reasons("fact", ["unsupported claim: 市場を支配する"])
        rescued, changes = pipeline._apply_deterministic_publication_rescue(parsed, rows)
        self.assertEqual([], changes)
        self.assertEqual(parsed["note_draft"], rescued["note_draft"])

    def test_risky_numeric_token_in_title_is_not_deleted(self):
        parsed = minimal_parsed(title="8月に変わる技術。", article=minimal_parsed()["note_draft"] + "\n8月に変わります。")
        rows = pipeline.map_gate_reasons("fact", ["unsupported numeric claim: 8月"])
        rescued, changes = pipeline._apply_deterministic_publication_rescue(parsed, rows)
        self.assertEqual([], changes)
        self.assertEqual("8月に変わる技術。", rescued["title_text"])


class TestPublicationReliabilitySelection(unittest.TestCase):
    def _item(self, name, source, score, url, desc="説明" * 40, priority=80):
        return {
            "repo": {"nameWithOwner": name, "source": source, "url": url, "primaryUrl": url, "description": desc,
                     "publishedAt": "2026-08-22T00:00:00Z", "licenseInfo": {"spdxId": "MIT"}},
            "score": score, "deep_dive_priority_score": priority, "notion_page_id": "page-" + name,
        }

    def test_direct_primary_sources_score_above_discovery_only(self):
        arxiv = self._item("paper", "ArXiv", 70, "https://arxiv.org/abs/2608.12345")
        hn = self._item("hn", "HackerNews", 70, "https://news.ycombinator.com/item?id=1")
        self.assertGreater(pipeline.publication_probability_score(arxiv), pipeline.publication_probability_score(hn))

    def test_reliability_slot_promotes_finishable_candidate(self):
        items = [
            self._item("hn1", "HackerNews", 90, "https://news.ycombinator.com/item?id=1", priority=95),
            self._item("hn2", "HackerNews", 88, "https://news.ycombinator.com/item?id=2", priority=94),
            self._item("hn3", "HackerNews", 86, "https://news.ycombinator.com/item?id=3", priority=93),
            self._item("paper", "ArXiv", 75, "https://arxiv.org/abs/2608.12345", priority=80),
        ]
        with patch.object(pipeline, "ENABLE_PUBLICATION_RELIABILITY_SLOT", True), \
             patch.object(pipeline, "PUBLICATION_RELIABILITY_MIN_DECISION_SCORE", 65), \
             patch.object(pipeline, "PUBLICATION_RELIABILITY_MIN_ADVANTAGE", 8):
            out = pipeline._apply_publication_reliability_slot(list(items), 3)
        self.assertEqual("paper", out[2]["repo"]["nameWithOwner"])

    def test_low_decision_candidate_is_never_promoted(self):
        items = [
            self._item("hn1", "HackerNews", 90, "https://news.ycombinator.com/item?id=1", priority=95),
            self._item("hn2", "HackerNews", 88, "https://news.ycombinator.com/item?id=2", priority=94),
            self._item("hn3", "HackerNews", 86, "https://news.ycombinator.com/item?id=3", priority=93),
            self._item("paper", "ArXiv", 59, "https://arxiv.org/abs/2608.12345", priority=80),
        ]
        with patch.object(pipeline, "ENABLE_PUBLICATION_RELIABILITY_SLOT", True), \
             patch.object(pipeline, "PUBLICATION_RELIABILITY_MIN_DECISION_SCORE", 65), \
             patch.object(pipeline, "PUBLICATION_RELIABILITY_MIN_ADVANTAGE", 8):
            out = pipeline._apply_publication_reliability_slot(list(items), 3)
        self.assertNotEqual("paper", out[2]["repo"]["nameWithOwner"])


class TestRun97Regression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((ROOT / "tests" / "fixtures" / "run97_quality_failures.json").read_text(encoding="utf-8"))

    def test_run97_negated_urgency_no_longer_false_positive(self):
        for case in self.cases:
            parsed = minimal_parsed(article=case["article"], score=int(case["decision_score"]), title=case["title"])
            parsed["action_text"] = case["action"]
            _, issues = pipeline.validate_publication_readiness_gate(parsed, case["article"], {"sufficient": True})
            self.assertNotIn("score_narrative_mismatch", issues, case["name"])

    def test_run97_known_local_defects_are_subtractively_rescuable(self):
        for idx, case in enumerate(self.cases):
            expected_tokens = ["唯一"] if idx == 0 else ["8月", "Llama", "デファクトスタンダード"]
            parsed = minimal_parsed(article=case["article"], score=int(case["decision_score"]), title=case["title"])
            parsed["action_text"] = case["action"]
            rows = []
            for msg in case["reason_codes"]:
                rows.append({"reason_code": msg["reason_code"], "message": msg["message"]})
            rescued, changes = pipeline._apply_deterministic_publication_rescue(parsed, rows)
            for token in expected_tokens:
                self.assertNotIn(token, rescued["note_draft"], f"{case['name']} changes={changes}")

    def test_run97_replay_known_blockers_reach_rescue_ready(self):
        # Run 97 already proved all other claims against its real evidence context; this replay
        # verifies that the final recorded blockers themselves no longer force rejection.
        ready_count = 0
        for case in self.cases:
            parsed = minimal_parsed(article=case["article"], score=int(case["decision_score"]), title=case["title"])
            parsed["action_text"] = case["action"]
            rescued, changes = pipeline._apply_deterministic_publication_rescue(parsed, case["reason_codes"])
            ready, diag = pipeline._publication_rescue_can_be_ready(
                rescued, case["article"], "ArXiv", {},
                {"sufficient": True, "primary_source_resolved": True, "deep_source_scanned": True, "decision_scope_safe": True},
                {}, False,
            )
            self.assertTrue(changes, case["name"])
            self.assertTrue(ready, f"{case['name']}: {diag}")
            ready_count += 1
        self.assertEqual(2, ready_count)


class TestProfitAwareScheduling(unittest.TestCase):
    def test_source_order_is_fresh_then_backlog_then_product_review(self):
        src = inspect.getsource(pipeline.main)
        fresh_marker = 'for candidate_index, candidate in enumerate(candidates):'
        backlog_marker = 'process_article_backlog('
        product_marker = 'run_product_reviews('
        self.assertIn(fresh_marker, src)
        self.assertIn(backlog_marker, src)
        self.assertIn(product_marker, src)
        self.assertLess(src.index(fresh_marker), src.rindex(backlog_marker))
        self.assertLess(src.rindex(backlog_marker), src.rindex(product_marker))

    def test_no_new_candidate_path_still_attempts_backlog(self):
        src = inspect.getsource(pipeline.main)
        no_candidate = src.index("候補が0件")
        following = src[no_candidate:no_candidate + 3500]
        self.assertIn("process_article_backlog", following)


if __name__ == "__main__":
    unittest.main()
