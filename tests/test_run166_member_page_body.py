import unittest

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
            "evidence": "https://github.com/example/tool\nhttps://docs.example.com/",
            "primary_url": "https://github.com/example/tool",
            "related_article": "https://note.com/example/n/abc",
        }

    def test_body_is_visible_callout_not_collapsed_toggle(self):
        block = body._new_callout_block(self._state())
        self.assertEqual(block["type"], "callout")
        self.assertIn("children", block)
        self.assertGreater(len(block["children"]), 8)
        child_types = [item["type"] for item in block["children"]]
        self.assertNotIn("toggle", child_types)
        headings = [
            "".join(x["text"]["content"] for x in item["heading_3"]["rich_text"])
            for item in block["children"]
            if item["type"] == "heading_3"
        ]
        self.assertEqual(headings[:3], ["結論", "次にやること", "これは何？"])
        self.assertIn("主なリスク", headings)
        self.assertIn("確認する一次情報", headings)

    def test_summary_puts_judgment_before_details(self):
        state = self._state()
        self.assertEqual(body._status_summary(state), "TEST 78/100｜実用度 中｜根拠 高")
        block = body._new_callout_block(state)
        first_text = block["children"][0]["paragraph"]["rich_text"][0]["text"]["content"]
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


if __name__ == "__main__":
    unittest.main()
