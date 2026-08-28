import unittest
from unittest.mock import Mock, patch

import decision_intelligence as di


class Run134MonthlyDecisionBriefReconciliationTests(unittest.TestCase):
    def test_status_change_outranks_large_score_only_move(self):
        events = [
            {
                "technology_name": "ScoreOnly",
                "adoption_status": "AVOID",
                "previous_status": "AVOID",
                "score_delta": 20,
                "status_changed": False,
                "snapshot_type": "UPDATE",
            },
            {
                "technology_name": "ChangedToWatch",
                "adoption_status": "WATCH",
                "previous_status": "TEST",
                "score_delta": -4,
                "status_changed": True,
                "snapshot_type": "UPDATE",
            },
            {
                "technology_name": "ChangedToTest",
                "adoption_status": "TEST",
                "previous_status": "WATCH",
                "score_delta": 3,
                "status_changed": True,
                "snapshot_type": "UPDATE",
            },
        ]

        brief = di.build_monthly_decision_brief(events, limit=2)

        self.assertEqual(2, len(brief))
        self.assertTrue(all(row["status_changed"] for row in brief))
        self.assertNotEqual("ScoreOnly", brief[0]["technology_name"])

    def test_action_label_only_maps_existing_adoption_status(self):
        cases = {
            "ADOPT": "導入判断を前へ進める候補",
            "TEST": "限定検証を検討する候補",
            "WATCH": "今は待ち、監視を続ける候補",
            "AVOID": "導入を見送る／再確認する候補",
        }
        for status, expected in cases.items():
            event = {
                "technology_name": status,
                "adoption_status": status,
                "previous_status": status,
                "score_delta": 6,
                "status_changed": False,
                "snapshot_type": "UPDATE",
            }
            with self.subTest(status=status):
                brief = di.build_monthly_decision_brief([event], limit=1)
                self.assertEqual(expected, brief[0]["decision_label"])
                self.assertEqual(status, brief[0]["adoption_status"])

    def test_non_meaningful_update_is_not_promoted(self):
        events = [
            {
                "technology_name": "Noise",
                "adoption_status": "WATCH",
                "previous_status": "WATCH",
                "score_delta": di.MEANINGFUL_SCORE_DELTA - 1,
                "status_changed": False,
                "snapshot_type": "UPDATE",
            }
        ]
        self.assertEqual([], di.build_monthly_decision_brief(events, limit=3))

    def test_monthly_digest_adds_brief_without_schema_change_and_keeps_legacy_sections(self):
        event = {
            "technology_name": "Tool A",
            "canonical_entity_id": "github:org/tool-a",
            "adoption_status": "TEST",
            "previous_status": "WATCH",
            "score_delta": 7,
            "status_changed": True,
            "snapshot_type": "CHANGE",
            "change_reason": "公式Evidence更新で限定検証の条件が整った",
            "main_risk": "",
        }
        fake = Mock(status_code=200)
        fake.json.return_value = {"id": "m1"}

        with patch.object(di, "ENABLE_DECISION_MONTHLY_DIGEST", True), \
             patch.object(di, "_monthly_exists", return_value=False), \
             patch.object(di, "query_history_records", return_value=[event]), \
             patch.object(di, "history_page_to_state", side_effect=lambda x: x), \
             patch.object(di.requests, "post", return_value=fake) as post:
            out = di.create_history_monthly_digest(
                "2026-08", generated_at="2026-09-01T00:00:00Z"
            )

        payload = post.call_args.kwargs["json"]
        props = payload["properties"]
        self.assertEqual(set(di.MONTHLY_REQUIRED_PROPERTY_TYPES), set(props))
        title = props[di.MONTHLY_PROP_TITLE]["title"][0]["text"]["content"]
        self.assertIn("何を再判断", title)
        body = "".join(
            block["paragraph"]["rich_text"][0]["text"]["content"]
            for block in payload["children"]
        )
        self.assertIn("まず確認したい3件", body)
        self.assertIn("Tool A", body)
        self.assertIn("Statusが変わったもの", body)
        self.assertIn("評価が上がったもの", body)
        self.assertIn("評価が下がったもの", body)
        self.assertIn("新規で評価したもの", body)
        self.assertEqual(1, out["decision_brief_count"])

    def test_no_gemini_or_schema_surface_added_by_monthly_brief(self):
        self.assertFalse(hasattr(di, "genai"))
        self.assertEqual(
            {
                di.MONTHLY_PROP_TITLE,
                di.MONTHLY_PROP_PERIOD_ID,
                di.MONTHLY_PROP_GENERATED_AT,
                di.MONTHLY_PROP_CHANGE_COUNT,
                di.MONTHLY_PROP_SUMMARY,
            },
            set(di.MONTHLY_REQUIRED_PROPERTY_TYPES),
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
