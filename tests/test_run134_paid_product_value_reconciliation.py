import unittest
from datetime import datetime, timezone

import inventory_bootstrap as ib


NOW = datetime(2026, 8, 25, tzinfo=timezone.utc)


def rec(**overrides):
    base = dict(
        page_id="p",
        name="Tool",
        canonical_entity_id="github:org/tool",
        primary_url="https://github.com/org/tool",
        source=("GitHub",),
        category="DEVTOOLS",
        screening_score=80,
        source_summary="Useful tool",
        published_at=None,
        analyzed_at=None,
        next_review=None,
        assessment_state="ASSESSED",
        entity_resolution_status="RESOLVED",
        tracking_status="ACTIVE",
        tracking_eligibility=True,
        adoption_score=80,
        adoption_status="TEST",
        evidence_confidence="HIGH",
        production_readiness="MEDIUM",
        main_risk="Requires outbound network access and a dedicated service account in production.",
        best_for="Teams automating repeatable repository maintenance with controlled credentials.",
        avoid_for="Teams that cannot isolate credentials or audit automated repository changes.",
        short_rationale="Evidence supports a bounded production trial, but credential isolation remains mandatory.",
        primary_evidence_urls="https://github.com/org/tool",
        last_reviewed=NOW.isoformat(),
    )
    base.update(overrides)
    return ib.TechnologyRecord(**base)


class Run134PaidProductValueReconciliationTests(unittest.TestCase):
    def test_specific_decision_information_scores_above_generic_copy(self):
        strong = ib.paid_product_utility(rec())
        weak = ib.paid_product_utility(rec(
            main_risk="導入には注意が必要です",
            best_for="AIを活用したい企業",
            avoid_for="慎重な企業",
            short_rationale="検討が必要です",
        ))

        self.assertEqual("HIGH", strong["band"])
        self.assertGreater(strong["score"], weak["score"])
        self.assertIn(weak["band"], {"LOW", "MEDIUM"})

    def test_paid_product_value_is_diagnostic_and_never_launch_blocker(self):
        rows = []
        statuses = ["ADOPT", "TEST", "WATCH", "AVOID"]
        categories = ["MODEL", "AGENT", "DEVTOOLS", "SECURITY"]
        for i in range(24):
            rows.append(rec(
                page_id=str(i),
                canonical_entity_id=f"e:{i}",
                adoption_status=statuses[i % 4],
                category=categories[i % 4],
                source=("GitHub",) if i % 2 else ("ArXiv",),
                main_risk="導入には注意が必要です",
                best_for="AIを活用したい企業",
                avoid_for="慎重な企業",
                short_rationale="検討が必要です",
            ))

        result = ib.evaluate_readiness(rows, subscriber_visible_count=24, now=NOW)

        self.assertTrue(result["launch_ready"])
        self.assertEqual("NEEDS_STRENGTHENING", result["paid_product_value"]["status"])
        self.assertTrue(result["paid_product_value"]["diagnostic_only"])
        self.assertNotIn("paid_product_value", " ".join(result["launch_blockers"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
