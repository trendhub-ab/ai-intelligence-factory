import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import context_first_enrichment as cfe


def event(entity, reviewed, delta, *, reason="score changed", snapshot="CHANGE"):
    return {
        "canonical_entity_id": entity,
        "reviewed_at": reviewed,
        "score_delta": delta,
        "snapshot_type": snapshot,
        "change_reason": reason,
    }


class MemberChangeSelectionTests(unittest.TestCase):
    def test_current_month_largest_change_survives_later_smaller_change(self):
        events = [
            event("tech-1", "2026-08-10T00:00:00+00:00", 25, reason="big"),
            event("tech-1", "2026-08-20T00:00:00+00:00", 6, reason="small"),
        ]
        selected = cfe._member_change_highlights(
            events, now=datetime(2026, 8, 29, tzinfo=timezone.utc)
        )
        self.assertEqual(25, selected["tech-1"]["score_delta"])
        self.assertEqual("big", selected["tech-1"]["change_reason"])

    def test_no_change_and_subthreshold_events_cannot_erase_meaningful_change(self):
        events = [
            event("tech-1", "2026-08-10T00:00:00+00:00", -25),
            event("tech-1", "2026-08-20T00:00:00+00:00", 0),
            event("tech-1", "2026-08-25T00:00:00+00:00", 2),
        ]
        selected = cfe._member_change_highlights(
            events, now=datetime(2026, 8, 29, tzinfo=timezone.utc)
        )
        self.assertEqual(-25, selected["tech-1"]["score_delta"])

    def test_without_current_month_change_latest_historical_meaningful_change_is_retained(self):
        events = [
            event("tech-1", "2026-06-10T00:00:00+00:00", 10),
            event("tech-1", "2026-07-20T00:00:00+00:00", -8),
        ]
        selected = cfe._member_change_highlights(
            events, now=datetime(2026, 8, 29, tzinfo=timezone.utc)
        )
        self.assertEqual(-8, selected["tech-1"]["score_delta"])
        self.assertEqual("2026-07-20T00:00:00+00:00", selected["tech-1"]["reviewed_at"])

    def test_initial_snapshot_is_not_presented_as_a_change(self):
        events = [event("tech-1", "2026-08-10T00:00:00+00:00", 30, snapshot="INITIAL")]
        self.assertEqual({}, cfe._member_change_highlights(
            events, now=datetime(2026, 8, 29, tzinfo=timezone.utc)
        ))

    def test_current_review_uses_natural_topic_as_change_reason(self):
        change = event("tech-1", "2026-08-20T00:00:00+00:00", 25, reason="Adoption Score 60→85")
        desired = {
            "last_reviewed": "2026-08-20T09:00:00+09:00",
            "topic_trigger": "公式に保守終了が明示されたため、新規採用を見送る判断へ変わりました。",
        }
        self.assertEqual(
            desired["topic_trigger"],
            cfe._member_change_reason(change, desired),
        )

    def test_older_change_uses_history_reason_not_current_topic(self):
        change = event("tech-1", "2026-08-10T00:00:00+00:00", 25, reason="Adoption Score 60→85")
        desired = {
            "last_reviewed": "2026-08-20T00:00:00+00:00",
            "topic_trigger": "後日の無変化レビューの話題。",
        }
        self.assertEqual("Adoption Score 60→85", cfe._member_change_reason(change, desired))


class MemberChangeSchemaTests(unittest.TestCase):
    def test_member_change_columns_are_required_with_exact_types(self):
        schema = {
            cfe.SUB_PROP_MEMBER_SCORE_CHANGE: {"type": "number"},
            cfe.SUB_PROP_MEMBER_CHANGE_AT: {"type": "date"},
            cfe.SUB_PROP_MEMBER_CHANGE_REASON: {"type": "rich_text"},
        }
        cfe._require_member_change_columns(schema, "Subscriber")
        bad = dict(schema)
        bad[cfe.SUB_PROP_MEMBER_CHANGE_AT] = {"type": "rich_text"}
        with self.assertRaisesRegex(ValueError, "Member Change At"):
            cfe._require_member_change_columns(bad, "Subscriber")


if __name__ == "__main__":
    unittest.main()
