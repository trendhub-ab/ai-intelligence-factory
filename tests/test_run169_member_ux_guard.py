import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import member_presentation_body_sync as body
import member_presentation_sync as mps
import member_ux_guard as guard


class ReviewSummaryRecoveryTests(unittest.TestCase):
    def test_external_review_summary_is_preferred_over_generic_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = {
                "reviews": [
                    {
                        "name": "example/tool",
                        "primary_url": "https://github.com/example/tool",
                        "decision_context": {
                            "plain_summary": "非エンジニアでも用途を理解できる、証拠確認済みの説明です。"
                        },
                    }
                ]
            }
            Path(tmp, "batch.json").write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
            index = guard.load_review_summary_index(tmp)
        state = {
            "name": "example/tool",
            "primary_url": "https://github.com/example/tool/",
        }
        self.assertEqual(
            "非エンジニアでも用途を理解できる、証拠確認済みの説明です。",
            guard.review_summary_for_state(state, index),
        )

    def test_fallback_is_never_empty_and_does_not_invent_new_capabilities(self):
        state = {
            "name": "paper title",
            "category": "AIモデル",
            "classification": "Deep Tech",
            "judgment_reason": "Chain-of-Thoughtを監査根拠として扱う際の注意点を示している。",
            "topic": "paper titleの現在の機能・保守状況を確認しています。",
            "best_for": "",
        }
        summary = guard.fallback_summary(state)
        self.assertTrue(summary)
        self.assertIn("Chain-of-Thought", summary)
        self.assertIn("研究・技術", summary)

    def test_presentation_guard_sets_three_item_contract_and_repairs_blank(self):
        original_source_state = mps._source_state
        original_home_max = mps.MEMBER_HOME_MAX
        try:
            fake_state = {
                "sync_id": "github:example/tool",
                "name": "example/tool",
                "plain_summary": "",
                "primary_url": "https://github.com/example/tool",
                "category": "開発ツール",
                "classification": "実務判断",
                "judgment_reason": "AI開発の比較対象として扱う。",
                "topic": "",
                "best_for": "AI開発チーム",
            }
            mps._source_state = lambda page: dict(fake_state)
            with mock.patch.object(
                guard,
                "load_review_summary_index",
                return_value={
                    "by_url": {
                        "https://github.com/example/tool": "AI開発を支援するツールです。"
                    },
                    "by_name": {},
                },
            ):
                stats = guard.install_presentation_guard()
                repaired = mps._source_state({})
            self.assertEqual(guard.HOME_SHORTLIST_SIZE, mps.MEMBER_HOME_MAX)
            self.assertEqual("AI開発を支援するツールです。", repaired["plain_summary"])
            self.assertEqual(1, stats["review_recovered"])
            self.assertEqual(0, stats["missing"])
        finally:
            mps._source_state = original_source_state
            mps.MEMBER_HOME_MAX = original_home_max


class CustomerSafeCalloutTests(unittest.TestCase):
    def _heading(self, text):
        return {
            "type": "heading_3",
            "heading_3": {"rich_text": [{"plain_text": text}]},
        }

    def test_legacy_auto_hash_is_recognized_for_one_time_migration(self):
        block = {
            "id": "legacy",
            "type": "callout",
            "callout": {"rich_text": [{"plain_text": body.AUTO_PREFIX + "｜abc123"}]},
        }
        self.assertEqual(
            [block], guard._generated_blocks([block], {})
        )

    def test_clean_generated_callout_is_detected_by_structure(self):
        block = {
            "id": "clean",
            "type": "callout",
            "callout": {"rich_text": [{"plain_text": guard.VISIBLE_CALLOUT_LABEL}]},
        }
        children = [
            self._heading("結論"),
            self._heading("次にやること"),
            self._heading("判断理由"),
        ]
        with mock.patch.object(body, "_children", return_value=children):
            self.assertTrue(guard._looks_like_generated_visible_callout(block, {}))

    def test_manual_callout_with_same_title_but_no_generated_structure_is_preserved(self):
        block = {
            "id": "manual",
            "type": "callout",
            "callout": {"rich_text": [{"plain_text": guard.VISIBLE_CALLOUT_LABEL}]},
        }
        children = [self._heading("自分用メモ")]
        with mock.patch.object(body, "_children", return_value=children):
            self.assertFalse(guard._looks_like_generated_visible_callout(block, {}))

    def test_customer_visible_label_contains_no_internal_marker_or_hash(self):
        self.assertEqual("🧭 判断サマリー", guard.VISIBLE_CALLOUT_LABEL)
        self.assertNotIn("AUTO", guard.VISIBLE_CALLOUT_LABEL)
        self.assertNotRegex(guard.VISIBLE_CALLOUT_LABEL, r"[0-9a-f]{8,}")


if __name__ == "__main__":
    unittest.main()
