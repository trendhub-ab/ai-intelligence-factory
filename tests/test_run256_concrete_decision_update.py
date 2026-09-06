import unittest
from unittest.mock import Mock, patch

import decision_intelligence as di


class Run256ConcreteDecisionUpdateTests(unittest.TestCase):
    def _event(self, **overrides):
        event = {
            "technology_name": "Tool A",
            "canonical_entity_id": "github:org/tool-a",
            "adoption_status": "TEST",
            "previous_status": "WATCH",
            "score_delta": 7,
            "status_changed": True,
            "snapshot_type": "CHANGE",
            "change_reason": "公式情報の更新で限定検証の条件が変わった。",
            "main_risk": "権限条件を再確認する必要がある。",
            "evidence_added": "公式リポジトリの運用方針が更新された。",
        }
        event.update(overrides)
        return event

    def _render(self, events):
        brief = di.build_monthly_decision_brief(events, limit=3)
        return "\n".join(di._run256_compose_monthly_lines(events, brief, "2026-09"))

    def test_material_status_change_surfaces_concrete_fields(self):
        body = self._render([self._event()])
        for marker in ("変更:", "現在の判断:", "理由:", "根拠:", "次のAction:"):
            self.assertIn(marker, body)
        self.assertIn("WATCH → TEST", body)
        self.assertIn("公式リポジトリ", body)

    def test_material_score_move_without_status_change_is_concrete(self):
        event = self._event(status_changed=False, previous_status="TEST", score_delta=9)
        body = self._render([event])
        self.assertIn("TEST → TEST (+9)", body)
        self.assertIn("根拠:", body)

    def test_material_avoid_change_produces_hold_action(self):
        event = self._event(adoption_status="AVOID", previous_status="TEST", score_delta=-11)
        body = self._render([event])
        self.assertIn("新規導入は見送り", body)
        self.assertIn("TEST → AVOID", body)

    def test_initial_assessment_preserves_existing_meaningful_contract(self):
        event = self._event(previous_status="", status_changed=False, score_delta=0, snapshot_type="INITIAL")
        body = self._render([event])
        self.assertIn("NEW → TEST", body)
        self.assertNotIn("重要な判断変更なし", body)

    def test_no_material_change_is_explicit(self):
        event = self._event(status_changed=False, previous_status="TEST", score_delta=di.MEANINGFUL_SCORE_DELTA - 1, snapshot_type="PERIODIC")
        body = self._render([event])
        self.assertIn("重要な判断変更なし", body)
        self.assertIn("観測点", body)

    def test_no_change_monitor_names_latest_observed_item(self):
        event = self._event(technology_name="Monitor Me", status_changed=False, previous_status="TEST", score_delta=0, snapshot_type="PERIODIC")
        body = self._render([event])
        self.assertIn("Monitor Me は現在 TEST", body)
        self.assertIn(f"±{di.MEANINGFUL_SCORE_DELTA}", body)

    def test_no_event_month_still_has_one_concrete_monitor_condition(self):
        body = self._render([])
        self.assertIn("重要な判断変更なし", body)
        self.assertIn("今月の履歴イベントはありません", body)
        self.assertIn("Status変更", body)

    def test_below_threshold_does_not_manufacture_change(self):
        event = self._event(status_changed=False, previous_status="TEST", score_delta=di.MEANINGFUL_SCORE_DELTA - 1, snapshot_type="PERIODIC")
        brief = di.build_monthly_decision_brief([event], limit=3)
        self.assertEqual([], brief)

    def test_monthly_schema_is_unchanged(self):
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

    def test_existing_priority_contract_is_unchanged(self):
        status_change = self._event(technology_name="Status", adoption_status="WATCH", previous_status="TEST", score_delta=-2, status_changed=True)
        score_only = self._event(technology_name="Score", adoption_status="AVOID", previous_status="AVOID", score_delta=20, status_changed=False)
        brief = di.build_monthly_decision_brief([score_only, status_change], limit=1)
        self.assertEqual("Status", brief[0]["technology_name"])

    def test_legacy_monthly_sections_remain_visible(self):
        body = self._render([self._event()])
        for heading in ("Statusが変わったもの", "評価が上がったもの", "評価が下がったもの", "新規で評価したもの"):
            self.assertIn(heading, body)

    def test_create_digest_uses_existing_schema_and_evidence_without_provider_calls(self):
        event = self._event()
        fake = Mock(status_code=200)
        fake.json.return_value = {"id": "monthly-1"}
        with patch.object(di, "ENABLE_DECISION_MONTHLY_DIGEST", True), \
             patch.object(di, "_monthly_exists", return_value=False), \
             patch.object(di, "query_history_records", return_value=[event]), \
             patch.object(di, "history_page_to_state", side_effect=lambda row: row), \
             patch.object(di.requests, "post", return_value=fake) as post:
            result = di.create_history_monthly_digest("2026-09", generated_at="2026-10-01T00:00:00Z")
        payload = post.call_args.kwargs["json"]
        self.assertEqual(set(di.MONTHLY_REQUIRED_PROPERTY_TYPES), set(payload["properties"]))
        body = "".join(block["paragraph"]["rich_text"][0]["text"]["content"] for block in payload["children"])
        self.assertIn("公式リポジトリ", body)
        self.assertEqual(1, result["decision_brief_count"])
        self.assertFalse(hasattr(di, "genai"))


if __name__ == "__main__":
    unittest.main()
