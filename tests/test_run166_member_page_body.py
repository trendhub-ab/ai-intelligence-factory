import unittest
from unittest import mock

import member_presentation_body_sync as body


class Run166MemberPageBodyTests(unittest.TestCase):
    def _state(self):
        return {
            "sync_id": "github:example/tool",
            "name": "example/tool",
            "plain_summary": "AI Agentの運用を支援するツールです。",
            "status": "TEST",
            "score": 78,
            "judgment_reason": "機能は有望ですが、本番条件での確認が必要です。",
            "topic": "最近、運用機能が強化されています。",
            "next_action": "代表業務を1つ選び、小さく試して効果と運用負荷を確認する。",
            "main_risk": "権限設定を誤ると意図しない操作につながります。",
            "best_for": "小規模PoCから始めたいチーム。",
            "avoid_for": "人間の承認を置けない高リスク業務。",
            "confidence": "高",
            "readiness": "中",
            "category": "エージェント",
            "classification": "実務判断",
            "change_reason": "前回より評価が上がったのは、運用機能が増えたためです。",
            "important_at": "2026-08-29",
            "last_reviewed": "2026-08-29",
            "evidence": "[https://github.com/example/tool](https://github.com/example/tool)\nhttps://docs.example.com/guide",
            "primary_url": "https://github.com/example/tool",
            "related_article": "https://note.com/example/n/abc",
        }

    def test_parent_callout_has_no_nested_children_for_notion_api(self):
        block = body._new_callout_block(self._state())
        self.assertEqual(block["type"], "callout")
        self.assertNotIn("children", block)
        self.assertTrue(block["callout"]["rich_text"])

    def test_visible_body_is_not_collapsed_toggle(self):
        children = body._build_children(self._state())
        self.assertGreater(len(children), 8)
        child_types = [item["type"] for item in children]
        self.assertNotIn("toggle", child_types)
        headings = [
            "".join(x["text"]["content"] for x in item["heading_3"]["rich_text"])
            for item in children
            if item["type"] == "heading_3"
        ]
        self.assertEqual(headings[:3], ["結論", "次にやること", "これは何？"])
        self.assertIn("主なリスク", headings)
        self.assertIn("確認する一次情報", headings)

    def test_summary_puts_judgment_before_details(self):
        state = self._state()
        self.assertEqual(body._status_summary(state), "TEST 78/100｜実用度 中｜根拠 高")
        first_text = body._build_children(state)[0]["paragraph"]["rich_text"][0]["text"]["content"]
        self.assertIn("TEST 78/100", first_text)

    def test_signature_changes_when_customer_decision_changes(self):
        state = self._state()
        original = body._signature(state)
        changed = dict(state)
        changed["next_action"] = "本番導入へ進む前に権限設定を検証する。"
        self.assertNotEqual(original, body._signature(changed))

    def test_status_color_is_customer_readable(self):
        state = self._state()
        expected = {
            "ADOPT": "green_background",
            "TEST": "blue_background",
            "WATCH": "yellow_background",
            "AVOID": "red_background",
        }
        for status, color in expected.items():
            state["status"] = status
            self.assertEqual(body._callout_data(state)["color"], color)

    def test_auto_marker_is_stable_and_detectable(self):
        state = self._state()
        label = body._auto_label(state)
        self.assertTrue(label.startswith(body.AUTO_PREFIX + "｜"))
        block = body._new_callout_block(state)
        rich = block["callout"]["rich_text"]
        fake_api_block = {
            "type": "callout",
            "callout": {"rich_text": [{"plain_text": rich[0]["text"]["content"]}]},
        }
        self.assertEqual(body._block_text(fake_api_block), label)

    def test_markdown_evidence_urls_are_extracted_cleanly(self):
        urls = body._extract_urls(self._state()["evidence"], self._state()["primary_url"])
        self.assertEqual(
            urls,
            ["https://github.com/example/tool", "https://docs.example.com/guide"],
        )

    def test_body_match_detects_partial_interrupted_write(self):
        state = self._state()
        expected = body._build_children(state)
        api_like = []
        for item in expected:
            kind = item["type"]
            text = item[kind]["rich_text"][0]["text"]["content"] if item[kind]["rich_text"] else ""
            api_like.append({"type": kind, kind: {"rich_text": [{"plain_text": text}]}})
        self.assertTrue(body._body_matches(api_like, state))
        self.assertFalse(body._body_matches(api_like[:-1], state))

    def test_creation_is_two_step_parent_then_children(self):
        state = self._state()
        calls = []

        def fake_append(block_id, children):
            calls.append((block_id, children))
            if len(calls) == 1:
                self.assertNotIn("children", children[0])
                return [{"id": "callout-123", "type": "callout"}]
            return [{"id": "child-1"}]

        with mock.patch.object(body, "_append_children", side_effect=fake_append):
            body._create_auto_callout("page-123", state)

        self.assertEqual(calls[0][0], "page-123")
        self.assertEqual(calls[1][0], "callout-123")
        self.assertGreater(len(calls[1][1]), 8)


if __name__ == "__main__":
    unittest.main()
