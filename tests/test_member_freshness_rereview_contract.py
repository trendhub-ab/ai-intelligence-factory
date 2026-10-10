from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import decision_intelligence as di
import member_verified_rereview_apply as apply


def _rt(value: str) -> dict:
    return {"rich_text": [{"plain_text": value}] if value else []}


def _title(value: str) -> dict:
    return {"title": [{"plain_text": value}] if value else []}


def _select(value: str) -> dict:
    return {"select": {"name": value} if value else None}


def _date(value: str) -> dict:
    return {"date": {"start": value} if value else None}


def _member_source_page(*, reviewed_at: str, source: str = "OfficialVendor") -> dict:
    return {
        "properties": {
            di.TECH_PROP_NAME: _title("Example AI"),
            di.TECH_PROP_SOURCE: {"multi_select": [{"name": source}]},
            di.TECH_PROP_ENTITY_ID: _rt("example:ai"),
            di.TECH_PROP_ASSESSMENT_STATE: _select("ASSESSED"),
            di.TECH_PROP_TRACKING_ELIGIBILITY: {"checkbox": True},
            di.TECH_PROP_TRACKING_STATUS: _select("ACTIVE"),
            di.TECH_PROP_LAST_REVIEWED: _date(reviewed_at),
            di.TECH_PROP_PUBLISHED_AT: _date(reviewed_at),
            di.TECH_PROP_ANALYZED_AT: _date(reviewed_at),
            di.TECH_PROP_SOURCE_SUMMARY: _rt("Current product information"),
        }
    }


class MemberFreshnessReReviewContractTests(unittest.TestCase):
    def test_verified_but_unchanged_evidence_never_enters_model_allowlist(self):
        selected = [{"sync_id": "same", "last_reviewed": "2026-01-01", "score": 80, "status": "TEST"}]

        result = apply.build_verified_allowlist(
            selected,
            lambda _: {
                "retrieved": True,
                "gate_pass": True,
                "result": "PASS",
                "material_change": False,
            },
            limit=1,
        )

        self.assertEqual(result["allowlist"], [])
        self.assertEqual(result["unchanged"], 1)

    def test_stale_member_record_is_withheld_but_fresh_review_restores_eligibility(self):
        now = datetime.now(timezone.utc)
        stale = (now - timedelta(days=120)).isoformat()
        fresh = (now - timedelta(days=1)).isoformat()

        stale_values = di._subscriber_values_from_internal(
            _member_source_page(reviewed_at=stale)
        )
        fresh_values = di._subscriber_values_from_internal(
            _member_source_page(reviewed_at=fresh)
        )

        self.assertFalse(stale_values["tracking_eligibility"])
        self.assertTrue(fresh_values["tracking_eligibility"])


if __name__ == "__main__":
    unittest.main()
