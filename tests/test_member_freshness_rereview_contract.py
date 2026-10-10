from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

import member_verified_rereview_apply as apply
import run225_member_lifecycle_ui as member_lifecycle


class MemberFreshnessReReviewContractTests(unittest.TestCase):
    def test_verified_but_unchanged_evidence_never_enters_model_allowlist(self):
        selected = [
            {
                "sync_id": "same",
                "last_reviewed": "2026-01-01",
                "score": 80,
                "status": "TEST",
            }
        ]

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

    def test_stale_member_record_is_withheld_but_fresh_review_restores_visibility(self):
        now = datetime.now(timezone.utc)
        stale = (now - timedelta(days=120)).isoformat()
        fresh = (now - timedelta(days=1)).isoformat()

        base = {
            "sync_id": "example:ai",
            "name": "Example AI",
            "sources": ["OfficialVendor"],
            "first_seen": stale,
            "topic": "Current product information",
        }
        stale_state = dict(base, last_reviewed=stale)
        fresh_state = dict(base, last_reviewed=fresh)

        self.assertIsNone(member_lifecycle.member_visible_state(stale_state))
        self.assertIs(member_lifecycle.member_visible_state(fresh_state), fresh_state)

    def test_old_durable_evergreen_asset_remains_member_visible(self):
        old = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        state = {
            "sync_id": "github:example/evergreen",
            "name": "Evergreen OSS",
            "sources": ["GitHub"],
            "first_seen": old,
            "last_reviewed": old,
            "topic": "Maintained open-source AI tooling",
        }

        self.assertIs(member_lifecycle.member_visible_state(state), state)


if __name__ == "__main__":
    unittest.main()
