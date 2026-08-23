import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import redirect_stdout
import io
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import inventory_bootstrap as ib

NOW = datetime(2026, 8, 23, tzinfo=timezone.utc)


def rec(**kw):
    base = dict(
        page_id="p", name="Tool", canonical_entity_id="github:org/tool",
        primary_url="https://github.com/org/tool", source=("GitHub",), category="DEVTOOLS",
        screening_score=80, source_summary="A durable developer tool with official documentation and a concrete implementation.",
        published_at="2026-08-20T00:00:00Z", analyzed_at="2026-08-22T00:00:00Z", next_review=None,
        assessment_state="LEGACY_PENDING", entity_resolution_status="RESOLVED", tracking_status="ACTIVE",
        tracking_eligibility=False, adoption_score=None, adoption_status="", evidence_confidence="",
        production_readiness="", main_risk="Main operational risk.", best_for="Teams that need this capability.",
        avoid_for="Teams that cannot accept the dependency.", short_rationale="Evidence-backed adoption rationale.",
        primary_evidence_urls="https://github.com/org/tool", last_reviewed=None,
    )
    base.update(kw)
    return ib.TechnologyRecord(**base)


class InventoryBootstrapTests(unittest.TestCase):
    def test_screening_score_is_not_adoption_score(self):
        r = rec(screening_score=95)
        score, _ = ib.bootstrap_priority(r, now=NOW)
        self.assertNotEqual(95, score)
        self.assertIsNone(r.adoption_score)

    def test_legacy_resolved_due_is_eligible(self):
        self.assertTrue(ib.is_bootstrap_eligible(rec(), now=NOW))

    def test_ambiguous_archived_and_future_review_are_excluded(self):
        self.assertFalse(ib.is_bootstrap_eligible(rec(entity_resolution_status="AMBIGUOUS"), now=NOW))
        self.assertFalse(ib.is_bootstrap_eligible(rec(tracking_status="ARCHIVED"), now=NOW))
        future = (NOW + timedelta(days=7)).isoformat()
        self.assertFalse(ib.is_bootstrap_eligible(rec(next_review=future), now=NOW))

    def test_incident_news_is_penalized_vs_durable_repo(self):
        durable = rec(name="wandb/wandb", screening_score=90)
        incident = rec(
            name="Incident with Github.com", source=("HackerNews",),
            primary_url="https://www.githubstatus.com/incidents/example", screening_score=90,
            source_summary="Incident with Github.com",
        )
        self.assertGreater(ib.bootstrap_priority(durable, NOW)[0], ib.bootstrap_priority(incident, NOW)[0])

    def test_balanced_selection_limits_source_domination_when_alternatives_exist(self):
        rows = []
        for i in range(10):
            rows.append(rec(page_id=f"g{i}", name=f"G{i}", canonical_entity_id=f"github:o/g{i}", screening_score=100-i))
        for i in range(5):
            rows.append(rec(page_id=f"a{i}", name=f"A{i}", canonical_entity_id=f"arxiv:{i}", source=("ArXiv",),
                            primary_url=f"https://arxiv.org/abs/2608.{10000+i}", screening_score=85-i))
        planned = ib.plan_candidates(rows, limit=10, max_source_share=.60, now=NOW)
        counts = {}
        for p in planned:
            bucket = p.source[0]
            counts[bucket] = counts.get(bucket, 0) + 1
        self.assertLessEqual(counts.get("GitHub", 0), 6)
        self.assertGreaterEqual(counts.get("ArXiv", 0), 4)

    def test_launch_readiness_false_with_one_record(self):
        r = rec(assessment_state="ASSESSED", tracking_eligibility=True, adoption_score=81,
                adoption_status="ADOPT", evidence_confidence="HIGH", production_readiness="HIGH",
                last_reviewed=NOW.isoformat())
        result = ib.evaluate_readiness([r], subscriber_visible_count=1, now=NOW)
        self.assertFalse(result["launch_ready"])
        self.assertEqual(1, result["sellable_count"])

    def test_launch_readiness_true_with_quality_diversity(self):
        rows = []
        statuses = ["ADOPT", "TEST", "WATCH", "AVOID"]
        categories = ["MODEL", "AGENT", "DEVTOOLS", "SECURITY", "DATA"]
        sources = [("GitHub",), ("ArXiv",), ("HackerNews",)]
        for i in range(24):
            rows.append(rec(
                page_id=f"p{i}", canonical_entity_id=f"entity:{i}", name=f"T{i}",
                assessment_state="ASSESSED", tracking_eligibility=True, adoption_score=60+i%30,
                adoption_status=statuses[i % len(statuses)], category=categories[i % len(categories)],
                source=sources[i % len(sources)], evidence_confidence="HIGH" if i % 3 else "MEDIUM",
                production_readiness="MEDIUM", last_reviewed=(NOW-timedelta(days=i%20)).isoformat(),
            ))
        result = ib.evaluate_readiness(rows, subscriber_visible_count=24, now=NOW)
        self.assertTrue(result["inventory_ready"], result)
        self.assertTrue(result["launch_ready"], result)

    def test_one_status_only_is_not_ready_even_with_30(self):
        rows = [rec(page_id=str(i), canonical_entity_id=f"e:{i}", assessment_state="ASSESSED",
                    tracking_eligibility=True, adoption_score=80, adoption_status="TEST",
                    category=["MODEL","AGENT","DEVTOOLS","DATA"][i%4],
                    source=("GitHub",) if i%2 else ("ArXiv",), evidence_confidence="HIGH",
                    production_readiness="MEDIUM", last_reviewed=NOW.isoformat()) for i in range(30)]
        result = ib.evaluate_readiness(rows, subscriber_visible_count=30, now=NOW)
        self.assertFalse(result["inventory_ready"])
        self.assertTrue(any("status_diversity" in x for x in result["inventory_blockers"]))

    def test_assessed_but_incomplete_product_record_is_not_sellable(self):
        r = rec(assessment_state="ASSESSED", tracking_eligibility=True, adoption_score=81,
                adoption_status="ADOPT", evidence_confidence="HIGH", production_readiness="HIGH",
                short_rationale="", last_reviewed=NOW.isoformat())
        self.assertFalse(ib.is_sellable(r))

    def test_subscriber_visible_count_ignores_blank_or_incomplete_rows(self):
        complete = rec(assessment_state="ASSESSED", tracking_eligibility=True, adoption_score=81,
                       adoption_status="ADOPT", evidence_confidence="HIGH", production_readiness="HIGH",
                       last_reviewed=NOW.isoformat())
        incomplete = rec(page_id="bad", canonical_entity_id="entity:bad", assessment_state="ASSESSED",
                         tracking_eligibility=True, adoption_score=80, adoption_status="TEST",
                         evidence_confidence="HIGH", production_readiness="HIGH", main_risk="")
        class FakeClient:
            def query_data_source(self, _ds):
                return [{}, flat_page(complete), flat_page(incomplete)]
        self.assertEqual(1, ib.subscriber_visible_count(FakeClient(), "sub"))

    def test_apply_does_not_skip_when_target_count_is_reached_but_launch_is_not_ready(self):
        self.assertFalse(ib.should_skip_apply({"target_reached": True, "launch_ready": False}))
        self.assertTrue(ib.should_skip_apply({"target_reached": True, "launch_ready": True}))
        self.assertFalse(ib.should_skip_apply({"target_reached": False, "launch_ready": True}))

    def test_apply_requires_explicit_confirmation(self):
        class A:
            confirm="no"; pipeline="pipeline.py"; target=30; min_sellable=24; max_reviews=4; product_request_budget=6; timeout=10
        with self.assertRaisesRegex(RuntimeError, "CONFIRM_BOOTSTRAP"):
            ib.run_apply(A())

    def test_apply_stops_when_target_already_reached(self):
        rows = []
        statuses = ["ADOPT","TEST","WATCH","AVOID"]
        cats = ["MODEL","AGENT","DEVTOOLS","DATA"]
        for i in range(30):
            rows.append(rec(page_id=str(i), canonical_entity_id=f"e:{i}", assessment_state="ASSESSED",
                            tracking_eligibility=True, adoption_score=80, adoption_status=statuses[i%4],
                            category=cats[i%4], source=("GitHub",) if i%2 else ("ArXiv",),
                            evidence_confidence="HIGH", production_readiness="HIGH", last_reviewed=NOW.isoformat()))
        class FakeClient:
            def __init__(self, *a, **k): pass
            def query_data_source(self, ds):
                if ds == "tech":
                    return [flat_page(x) for x in rows]
                return [flat_page(x) for x in rows]
        class A:
            confirm=ib.CONFIRM_TEXT; pipeline=__file__; target=30; min_sellable=24; max_reviews=4; product_request_budget=6; timeout=10
        env = {"NOTION_DECISION_INTELLIGENCE_API_KEY":"x","NOTION_TECH_DATA_SOURCE_ID":"tech","NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID":"sub"}
        with patch.dict(os.environ, env, clear=False), patch.object(ib, "NotionClient", FakeClient), tempfile.TemporaryDirectory() as td, patch.object(ib, "ARTIFACT_DIR", Path(td)), redirect_stdout(io.StringIO()):
            out = ib.run_apply(A())
        self.assertTrue(out["skipped"])

    def test_product_only_environment_disables_acquisition_and_sets_product_caps(self):
        env = ib.product_only_environment(4, 6)
        self.assertEqual("0", env["MAX_SCREENING_CANDIDATES"])
        self.assertEqual("false", env["ENABLE_GLOBAL_CALIBRATION"])
        self.assertEqual("0", env["GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET"])
        self.assertEqual("false", env["ENABLE_DECISION_MONTHLY_DIGEST"])
        self.assertEqual("false", env["ENABLE_MONTHLY_DIGEST"])
        self.assertEqual("false", env["ENABLE_OBSERVED_HISTORY"])
        self.assertEqual("4", env["PRODUCT_REVIEW_MAX_PER_RUN"])
        self.assertEqual("4", env["LEGACY_BOOTSTRAP_MAX_PER_RUN"])
        self.assertEqual("6", env["GEMINI_PRODUCT_REVIEW_PER_RUN_REQUEST_BUDGET"])

    def test_notion_query_falls_back_from_data_source_to_database_id(self):
        first = Mock(status_code=404, text="not a data source")
        second = Mock(status_code=200, text="ok")
        second.json.return_value = {"results": [{"id": "p1"}], "has_more": False}
        client = ib.NotionClient("token")
        with patch.object(ib.requests, "post", side_effect=[first, second]) as post:
            rows = client.query_data_source("collection://abc")
        self.assertEqual([{"id": "p1"}], rows)
        self.assertIn("/v1/data_sources/abc/query", post.call_args_list[0].args[0])
        self.assertIn("/v1/databases/abc/query", post.call_args_list[1].args[0])

    def test_manual_workflow_has_no_schedule_and_no_second_counter_commit(self):
        workflow = (ROOT / ".github" / "workflows" / "inventory-bootstrap.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertIn("group: ai-intelligence-gemini-budget", workflow)
        self.assertIn("actions/checkout@v6", workflow)
        self.assertIn("actions/setup-python@v6", workflow)
        self.assertIn('python-version: "3.11"', workflow)
        self.assertNotIn("git commit", workflow)
        self.assertNotIn("git push", workflow)

    def test_log_safety_detects_unexpected_acquisition_calls(self):
        bad = "[GEMINI DEEP DIVE CALL] kind=deep_dive\nGemini Requests Used: screening_batch=1"
        problems = ib.detect_unsafe_pipeline_activity(bad)
        self.assertIn("deep_dive_gemini_call", problems)
        self.assertIn("screening_gemini_call", problems)
        self.assertEqual([], ib.detect_unsafe_pipeline_activity("[PRODUCT REVIEW] saved=2\nproduct_review=2"))


def flat_page(r):
    # Normalized flat dictionaries are accepted by normalize_technology_page via _prop fallback.
    return {
        "id": r.page_id,
        "Technology / Project Name": r.name,
        "Canonical Entity ID": r.canonical_entity_id,
        "Primary URL": r.primary_url,
        "Source": list(r.source),
        "Category": r.category,
        "Screening Score": r.screening_score,
        "Source Summary": r.source_summary,
        "Published At": r.published_at,
        "Analyzed At": r.analyzed_at,
        "Next Review": r.next_review,
        "Assessment State": r.assessment_state,
        "Entity Resolution Status": r.entity_resolution_status,
        "Tracking Status": r.tracking_status,
        "Tracking Eligibility": r.tracking_eligibility,
        "Adoption Score": r.adoption_score,
        "Adoption Status": r.adoption_status,
        "Evidence Confidence": r.evidence_confidence,
        "Production Readiness": r.production_readiness,
        "Main Risk": r.main_risk,
        "Best For": r.best_for,
        "Avoid For": r.avoid_for,
        "Short Rationale": r.short_rationale,
        "Primary Evidence URLs": r.primary_evidence_urls,
        "Last Reviewed": r.last_reviewed,
    }


if __name__ == "__main__":
    unittest.main()
