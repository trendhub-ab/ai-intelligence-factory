from pathlib import Path
import unittest
from unittest.mock import patch

import member_presentation_body_sync as body
import run219_member_human_language_ui as run219


ROOT = Path(__file__).resolve().parents[1]


def _heading_texts(blocks):
    return [body._block_text(block) for block in blocks if block.get("type") == "heading_3"]


def _callout(label: str):
    return {
        "id": "callout-1",
        "type": "callout",
        "callout": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": label},
                }
            ]
        },
    }


class Run219MemberHumanLanguageUiTests(unittest.TestCase):
    def _state(self, status="ADOPT"):
        return {
            "status": status,
            "score": 91,
            "readiness": "高",
            "confidence": "高",
            "plain_summary": "社内向けのAIを作るための仕組みです。",
            "topic": "社内でAI活用を広げたいときに確認します。",
            "next_action": "まず1つの業務で小さく試す。",
            "judgment_reason": "少人数で試しやすく、本番運用へつなげやすいためです。",
            "main_risk": "社内データの扱いを事前に決める必要があります。",
            "best_for": "社内問い合わせや文書検索。",
            "avoid_for": "単機能だけを細かく自社開発したい場合。",
            "change_reason": "保守状況が改善しました。",
            "evidence": "https://example.com/docs",
            "primary_url": "https://example.com",
            "related_article": "",
        }

    def test_detail_headings_are_non_engineer_first(self):
        headings = _heading_texts(run219._build_children(self._state()))
        self.assertEqual(
            headings,
            [
                "これは何？",
                "いま、どうする？",
                "なぜ今見る？",
                "次にやること",
                "そう判断した理由",
                "気をつけたいこと",
                "こんな使い方に向いています",
                "こんな使い方には向きません",
                "前と判断が変わった理由",
                "確認に使った公式・一次情報",
            ],
        )
        for old in ("判断理由", "主なリスク", "向いている用途", "向いていない用途", "判断サマリー"):
            self.assertNotIn(old, headings)

    def test_status_summary_hides_internal_english_code(self):
        expected = {
            "ADOPT": "導入を考えてよい",
            "TEST": "まず小さく試す",
            "WATCH": "もう少し様子を見る",
            "AVOID": "今は選ばない",
        }
        for code, label in expected.items():
            with self.subTest(code=code):
                summary = run219._status_summary(self._state(code))
                self.assertIn(label, summary)
                self.assertNotIn(code, summary)
                self.assertIn("参考スコア：91点", summary)
                self.assertIn("情報の確かさ：高", summary)

    def test_previous_clean_callout_is_still_recognized_for_safe_migration(self):
        children = [
            body._heading("これは何？"),
            body._heading("いまの判断"),
            body._heading("次にやること"),
            body._heading("判断理由"),
        ]
        cache = {"callout-1": children}
        self.assertTrue(
            run219._looks_like_generated_member_callout(
                _callout(run219.PREVIOUS_VISIBLE_CALLOUT_LABEL), cache
            )
        )

    def test_new_callout_is_recognized_but_manual_callout_is_not(self):
        children = run219._build_children(self._state())
        cache = {"callout-1": children}
        self.assertTrue(
            run219._looks_like_generated_member_callout(
                _callout(run219.NEW_VISIBLE_CALLOUT_LABEL), cache
            )
        )
        self.assertFalse(
            run219._looks_like_generated_member_callout(
                _callout("手動メモ"), cache
            )
        )

    def test_cached_callout_recognition_never_fetches_notion_children(self):
        children = run219._build_children(self._state())
        cache = {"callout-1": children}
        with patch.object(body, "_children", side_effect=AssertionError("network access")) as fetch_children:
            self.assertTrue(
                run219._looks_like_generated_member_callout(
                    _callout(run219.NEW_VISIBLE_CALLOUT_LABEL), cache
                )
            )
        fetch_children.assert_not_called()

    def test_run219_has_no_model_or_provider_path(self):
        source = (ROOT / "run219_member_human_language_ui.py").read_text(encoding="utf-8")
        for forbidden in (
            "GEMINI_API_KEY",
            "google.generativeai",
            "google.genai",
            "generate_content(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("ZERO Gemini/model requests", source)

    def test_run219_does_not_modify_decision_values(self):
        state = self._state("TEST")
        before = dict(state)
        run219._build_children(state)
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
