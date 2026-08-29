import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import daily_portfolio_review as dpr


NOW = datetime(2026, 8, 29, 12, 0, tzinfo=timezone.utc)


def assessed(**overrides):
    state = {
        "assessment_state": "ASSESSED",
        "tracking_eligibility": True,
        "tracking_status": "ACTIVE",
        "canonical_entity_id": "entity-default",
        "adoption_score": 70,
        "adoption_status": "TEST",
        "evidence_confidence": "MEDIUM",
        "production_readiness": "MEDIUM",
        "last_reviewed": (NOW - timedelta(days=10)).isoformat(),
        "last_evidence_update": (NOW - timedelta(days=11)).isoformat(),
        "next_review": None,
    }
    state.update(overrides)
    return state


class Run162ScalableChangeDrivenReviewTests(unittest.TestCase):
    def test_persisted_last_evidence_update_is_wired_into_review_state(self):
        page = {
            "id": "page-1",
            "properties": {
                dpr.decision_intelligence.TECH_PROP_LAST_EVIDENCE_UPDATE: {
                    "date": {"start": NOW.isoformat()}
                }
            },
        }
        with patch.object(
            dpr.decision_intelligence,
            "technology_page_to_state",
            return_value={"canonical_entity_id": "entity-1", "last_reviewed": (NOW - timedelta(days=1)).isoformat()},
        ):
            state = dpr.technology_page_to_review_state(page)
        self.assertEqual(state["last_evidence_update"], NOW.isoformat())
        self.assertTrue(dpr.has_fresh_evidence(state))

    def test_priority_tiers_are_deterministic_and_zero_schema(self):
        high = assessed(adoption_status="ADOPT", adoption_score=80)
        normal = assessed(adoption_status="WATCH", adoption_score=70)
        low = assessed(adoption_status="AVOID", adoption_score=40)
        self.assertEqual(dpr.review_priority_tier(high), "HIGH")
        self.assertEqual(dpr.review_priority_tier(normal), "NORMAL")
        self.assertEqual(dpr.review_priority_tier(low), "LOW")
        self.assertNotIn("Review Tier", decision_schema_names())

    def test_fresh_evidence_bypasses_future_schedule_even_for_low_tier(self):
        state = assessed(
            adoption_status="AVOID",
            adoption_score=20,
            last_reviewed=(NOW - timedelta(days=1)).isoformat(),
            last_evidence_update=NOW.isoformat(),
            next_review=(NOW + timedelta(days=90)).isoformat(),
        )
        self.assertEqual(dpr.review_priority_tier(state), "LOW")
        self.assertEqual(dpr.daily_review_reason(state, now=NOW), "FRESH_EVIDENCE")

    def test_unchanged_normal_entity_does_not_consume_14_day_cycle(self):
        state = assessed(
            adoption_status="WATCH",
            adoption_score=70,
            last_reviewed=(NOW - timedelta(days=20)).isoformat(),
            last_evidence_update=(NOW - timedelta(days=21)).isoformat(),
        )
        self.assertEqual(dpr.review_priority_tier(state), "NORMAL")
        self.assertIsNone(dpr.daily_review_reason(state, now=NOW))
        state["last_reviewed"] = (NOW - timedelta(days=31)).isoformat()
        state["last_evidence_update"] = (NOW - timedelta(days=32)).isoformat()
        self.assertEqual(dpr.daily_review_reason(state, now=NOW), "TIER_DUE")

    def test_unchanged_low_entity_waits_60_days_but_is_not_abandoned(self):
        state = assessed(
            adoption_status="AVOID",
            adoption_score=30,
            last_reviewed=(NOW - timedelta(days=40)).isoformat(),
            last_evidence_update=(NOW - timedelta(days=41)).isoformat(),
        )
        self.assertIsNone(dpr.daily_review_reason(state, now=NOW))
        state["last_reviewed"] = (NOW - timedelta(days=61)).isoformat()
        state["last_evidence_update"] = (NOW - timedelta(days=62)).isoformat()
        self.assertEqual(dpr.daily_review_reason(state, now=NOW), "TIER_DUE")

    def test_high_value_entity_keeps_existing_14_day_default(self):
        state = assessed(
            adoption_status="ADOPT",
            adoption_score=92,
            last_reviewed=(NOW - timedelta(days=15)).isoformat(),
            last_evidence_update=(NOW - timedelta(days=16)).isoformat(),
        )
        self.assertEqual(dpr.review_interval_days(state), dpr.REVIEW_TIER_HIGH_DAYS)
        self.assertEqual(dpr.daily_review_reason(state, now=NOW), "TIER_DUE")

    def test_archived_or_ineligible_entities_never_reenter_on_fresh_timestamp(self):
        archived = assessed(
            tracking_status="ARCHIVED",
            last_reviewed=(NOW - timedelta(days=1)).isoformat(),
            last_evidence_update=NOW.isoformat(),
        )
        ineligible = assessed(
            tracking_eligibility=False,
            last_reviewed=(NOW - timedelta(days=1)).isoformat(),
            last_evidence_update=NOW.isoformat(),
        )
        self.assertIsNone(dpr.daily_review_reason(archived, now=NOW))
        self.assertIsNone(dpr.daily_review_reason(ineligible, now=NOW))

    def test_malformed_or_missing_evidence_timestamp_fails_closed(self):
        state = assessed(
            adoption_status="AVOID",
            adoption_score=10,
            last_reviewed=(NOW - timedelta(days=2)).isoformat(),
            last_evidence_update="not-a-date",
        )
        self.assertFalse(dpr.has_fresh_evidence(state))
        self.assertIsNone(dpr.daily_review_reason(state, now=NOW))

    def test_history_then_fresh_then_periodic_priority_is_preserved(self):
        history = assessed(
            canonical_entity_id="history",
            assessment_state="HISTORY_PENDING",
            last_reviewed=(NOW - timedelta(days=100)).isoformat(),
        )
        fresh = assessed(
            canonical_entity_id="fresh",
            last_reviewed=(NOW - timedelta(days=1)).isoformat(),
            last_evidence_update=NOW.isoformat(),
        )
        periodic = assessed(
            canonical_entity_id="periodic",
            adoption_status="ADOPT",
            adoption_score=95,
            last_reviewed=(NOW - timedelta(days=20)).isoformat(),
            last_evidence_update=(NOW - timedelta(days=21)).isoformat(),
        )
        with patch.object(dpr, "_rank_states", side_effect=lambda states, limit, now: [x["canonical_entity_id"] for x in states][:limit]):
            planned = dpr.plan_daily_review_allowlist([periodic, fresh, history], scan_limit=3, now=NOW)
        self.assertEqual(planned, ["history", "fresh", "periodic"])

    def test_large_long_tail_does_not_become_due_merely_because_inventory_is_large(self):
        states = [
            assessed(
                canonical_entity_id=f"low-{i}",
                adoption_status="AVOID",
                adoption_score=20,
                last_reviewed=(NOW - timedelta(days=20)).isoformat(),
                last_evidence_update=(NOW - timedelta(days=21)).isoformat(),
            )
            for i in range(10000)
        ]
        self.assertEqual(sum(dpr.daily_review_reason(x, now=NOW) is not None for x in states), 0)

    def test_existing_hard_caps_remain_small(self):
        self.assertEqual(dpr.DEFAULT_MAX_REVIEWS, max(0, int(os.environ.get("DAILY_PORTFOLIO_REVIEW_MAX", "2"))))
        self.assertEqual(dpr.DEFAULT_REQUEST_BUDGET, max(0, int(os.environ.get("DAILY_PORTFOLIO_REQUEST_BUDGET", "3"))))
        self.assertLessEqual(dpr.DEFAULT_MAX_REVIEWS, dpr.DEFAULT_REQUEST_BUDGET)


def decision_schema_names():
    return set(dpr.decision_intelligence.TECH_REQUIRED_PROPERTY_TYPES)


if __name__ == "__main__":
    unittest.main()
