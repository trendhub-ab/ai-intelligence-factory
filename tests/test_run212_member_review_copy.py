import unittest

import member_human_language_ux as base
import member_ux_guard as guard
import run212_member_review_copy as run212


class Run212ArchiveReviewCopyTests(unittest.TestCase):
    def base_state(self):
        state = {
            "sync_id": "github:example/tool",
            "name": "example/tool",
            "plain_summary": "",
            "status": "TEST",
            "score": 84,
            "judgment_reason": "現在の実装を小規模に検証する価値がある。",
            "topic": "example/toolの現在の機能・保守状況を確認しています。",
            "next_action": "実際の業務を1つ選び、小さく試して品質・費用・運用負荷を確認する。",
            "main_risk": "権限設計と運用負荷を確認する必要がある。",
            "best_for": "AI業務を小規模に試したいチーム。",
            "avoid_for": "運用担当を置けないケース。",
            "confidence": "高",
            "readiness": "高",
            "category": "開発ツール",
            "classification": "実務判断",
            "change_reason": "",
            "evidence": "https://example.com/evidence",
            "primary_url": "https://example.com/tool",
            "related_article": "",
        }
        state["plain_summary"] = guard.fallback_summary(state)
        return state

    def archive_copy(self):
        return {
            "plain_summary": "業務AIを小さく試すための開発・運用ツールです。",
            "topic_trigger": "個別開発を増やす前に、共通基盤として比較する価値があります。",
            # These deliberately dangerous historical fields must never win.
            "short_rationale": "古い判断理由。",
            "main_risk": "古いリスク。",
            "best_for": "古い用途。",
            "avoid_for": "古い不適用途。",
            "_source_kind": run212.ARCHIVE_COPY_KIND,
        }

    def test_default_loader_reads_archive_as_copy_only(self):
        index = run212.load_combined_review_copy_index()
        copy = index["by_url"]["https://github.com/deepseek-ai/deepseek-r1"]
        self.assertEqual(copy["_source_kind"], run212.ARCHIVE_COPY_KIND)
        self.assertTrue(copy["plain_summary"])
        self.assertTrue(copy["topic_trigger"])
        self.assertEqual(copy["short_rationale"], "")
        self.assertEqual(copy["main_risk"], "")
        self.assertEqual(copy["best_for"], "")
        self.assertEqual(copy["avoid_for"], "")

    def test_time_sensitive_archive_copy_is_rejected(self):
        run212.reset_runtime_stats()
        self.assertEqual(
            run212._safe_archive_fragment(
                "公式GitHubは2026年8月時点でも継続的に更新されています。",
                stat_key="archive_topic_filtered_stale",
            ),
            "",
        )
        self.assertEqual(run212._RUNTIME_STATS["archive_topic_filtered_stale"], 1)

    def test_archive_can_replace_only_guard_fallback_and_generic_topic(self):
        state = self.base_state()
        original = dict(state)
        out = run212.safe_humanize_state(state, self.archive_copy())

        self.assertEqual(out["plain_summary"], self.archive_copy()["plain_summary"])
        self.assertEqual(out["topic"], self.archive_copy()["topic_trigger"])
        for key in (
            "status",
            "score",
            "judgment_reason",
            "main_risk",
            "best_for",
            "avoid_for",
            "evidence",
            "primary_url",
        ):
            self.assertEqual(out[key], original[key], key)

    def test_current_nonfallback_summary_remains_authoritative(self):
        state = self.base_state()
        state["plain_summary"] = "現在DBにある固有の説明文。"
        out = run212.safe_humanize_state(state, self.archive_copy())
        self.assertEqual(out["plain_summary"], "現在DBにある固有の説明文。")
        self.assertEqual(out["topic"], self.archive_copy()["topic_trigger"])

    def test_active_review_keeps_existing_run170_behavior(self):
        state = self.base_state()
        state["plain_summary"] = "現在DBの説明。"
        active = self.archive_copy()
        active["_source_kind"] = run212.ACTIVE_COPY_KIND
        active["plain_summary"] = "新しい現行レビューの説明。"
        out = run212.safe_humanize_state(state, active)
        self.assertEqual(out["plain_summary"], "新しい現行レビューの説明。")
        self.assertEqual(out["topic"], active["topic_trigger"])

    def test_module_contains_no_model_provider_path(self):
        source = open("run212_member_review_copy.py", encoding="utf-8").read()
        self.assertNotIn("GEMINI_API_KEY", source)
        self.assertNotIn("google.genai", source)
        self.assertNotIn("generate_content", source)


if __name__ == "__main__":
    unittest.main()
