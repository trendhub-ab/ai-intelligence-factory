import inspect
import unittest
from datetime import datetime, timezone
from pathlib import Path

import inventory_bootstrap as ib
import paid_db_launch_readiness as lr


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 8, 29, tzinfo=timezone.utc)


def rec(i=0, **overrides):
    base = dict(
        page_id=f"p{i}",
        name=f"AI Tool {i}",
        canonical_entity_id=f"entity:{i}",
        primary_url=f"https://github.com/org/tool-{i}",
        source=("GitHub",) if i % 2 else ("ArXiv",),
        category=lr.REQUIRED_LAUNCH_CATEGORIES[i % len(lr.REQUIRED_LAUNCH_CATEGORIES)],
        screening_score=85,
        source_summary="AI LLM agent machine learning platform with a concrete production implementation.",
        published_at="2026-08-25T00:00:00Z",
        analyzed_at="2026-08-28T00:00:00Z",
        next_review=None,
        assessment_state="ASSESSED",
        entity_resolution_status="RESOLVED",
        tracking_status="ACTIVE",
        tracking_eligibility=True,
        adoption_score=80,
        adoption_status=("ADOPT", "TEST", "WATCH", "AVOID")[i % 4],
        evidence_confidence="HIGH",
        production_readiness="MEDIUM",
        main_risk="Requires controlled credentials and production monitoring before broad deployment.",
        best_for="Teams evaluating an AI capability with measurable operational requirements.",
        avoid_for="Teams that cannot validate model behavior or isolate production credentials.",
        short_rationale="Primary evidence supports a bounded AI deployment decision with explicit operating constraints.",
        primary_evidence_urls=f"https://github.com/org/tool-{i}",
        last_reviewed=NOW.isoformat(),
    )
    base.update(overrides)
    return ib.TechnologyRecord(**base)


def balanced_rows(n=50, **overrides):
    return [rec(i, **overrides) for i in range(n)]


class Run152PaidDBLaunchReadinessTests(unittest.TestCase):
    def test_current_like_26_record_inventory_is_not_launch_ready(self):
        categories = ["DEVTOOLS"] * 9 + ["OTHER"] * 9 + ["SECURITY"] * 4 + ["DATA"] * 3 + ["MULTIMODAL"]
        rows = [rec(i, category=category, adoption_status="ADOPT") for i, category in enumerate(categories)]
        result = lr.evaluate_launch_quality(rows)
        self.assertFalse(result["ready"])
        self.assertIn("launch_sellable<50 (26)", result["blockers"])
        self.assertTrue(any("required_category_count" in x for x in result["blockers"]))

    def test_balanced_50_record_catalog_passes_commercial_launch_quality(self):
        rows = balanced_rows(50)
        result = lr.evaluate_launch_quality(rows)
        self.assertTrue(result["ready"], result)
        self.assertGreaterEqual(result["front_shelf_count"], 15)
        self.assertTrue(all(count >= 2 for count in result["required_category_counts"].values()))
        self.assertLessEqual(result["dominant_category_share"], 0.35)

    def test_each_required_category_must_have_real_core_inventory(self):
        allowed = [c for c in lr.REQUIRED_LAUNCH_CATEGORIES if c != "PRODUCT"]
        rows = [rec(i, category=allowed[i % len(allowed)], adoption_status="ADOPT") for i in range(50)]
        result = lr.evaluate_launch_quality(rows)
        self.assertFalse(result["ready"])
        self.assertEqual(0, result["required_category_counts"]["PRODUCT"])
        self.assertTrue(any("PRODUCT" in x for x in result["blockers"]))

    def test_single_category_cannot_dominate_launch_catalog(self):
        rows = []
        for i in range(18):
            rows.append(rec(i, category="DEVTOOLS", adoption_status="ADOPT"))
        other_categories = [c for c in lr.REQUIRED_LAUNCH_CATEGORIES if c != "DEVTOOLS"]
        for i in range(18, 50):
            rows.append(rec(i, category=other_categories[(i - 18) % len(other_categories)], adoption_status="ADOPT"))
        result = lr.evaluate_launch_quality(rows)
        self.assertFalse(result["ready"])
        self.assertEqual("DEVTOOLS", result["dominant_category"])
        self.assertGreater(result["dominant_category_share"], 0.35)
        self.assertTrue(any("category_share" in x for x in result["blockers"]))

    def test_reference_material_does_not_make_front_shelf_look_deeper(self):
        rows = balanced_rows(50, adoption_status="ADOPT")
        for i in range(11):
            rows[i] = rec(
                i,
                name=f"awesome-ai-resource-list-{i}",
                adoption_status="ADOPT",
                source_summary="Curated list of AI learning resources and links.",
            )
        result = lr.evaluate_launch_quality(rows)
        self.assertFalse(result["ready"])
        self.assertEqual(11, result["reference_only_count"])
        self.assertGreater(result["reference_share"], 0.20)
        self.assertTrue(any("reference_share" in x for x in result["blockers"]))

    def test_non_ai_general_library_is_not_front_shelf_even_if_adopt_high(self):
        taffy_like = rec(
            999,
            name="dioxuslabs/taffy",
            category="DEVTOOLS",
            adoption_status="ADOPT",
            production_readiness="HIGH",
            source_summary="Rust layout library implementing Flexbox and CSS Grid for application interfaces.",
            short_rationale="Mature cross-platform layout library with production adoption.",
            best_for="Rust applications needing layout calculations.",
            avoid_for="Teams needing built-in text layout or complete browser rendering.",
        )
        self.assertFalse(lr.is_ai_relevant(taffy_like))
        self.assertFalse(lr.is_front_shelf(taffy_like))

    def test_agent_research_is_ai_relevant_even_when_authoritative_category_is_other(self):
        agent_paper = rec(
            1000,
            name="When Agents Coordinate: Measuring Coordination in Multi-Agent AI Coding",
            category="OTHER",
            adoption_status="WATCH",
            production_readiness="LOW",
            source_summary="Empirical study of multi-agent LLM coding teams and their coordination behavior.",
        )
        self.assertTrue(lr.is_ai_relevant(agent_paper))
        self.assertFalse(lr.is_front_shelf(agent_paper))

    def test_paid_product_utility_remains_diagnostic_not_a_run152_blocker(self):
        rows = balanced_rows(
            50,
            main_risk="導入には注意が必要です",
            best_for="AIを活用したい企業",
            avoid_for="慎重な企業",
            short_rationale="検討が必要です",
        )
        old_evaluate = ib.evaluate_readiness
        old_target = ib.DEFAULT_TARGET
        old_min = ib.DEFAULT_MIN_SELLABLE
        old_flag = getattr(ib, "_run152_launch_readiness_installed", False)
        try:
            if old_flag:
                delattr(ib, "_run152_launch_readiness_installed")
            lr.install_on(ib)
            result = ib.evaluate_readiness(rows, subscriber_visible_count=50, now=NOW)
            self.assertTrue(result["launch_ready"], result)
            self.assertEqual("NEEDS_STRENGTHENING", result["paid_product_value"]["status"])
            self.assertTrue(result["paid_product_value"]["diagnostic_only"])
            self.assertFalse(any("paid_product_value" in x for x in result["launch_blockers"]))
        finally:
            ib.evaluate_readiness = old_evaluate
            ib.DEFAULT_TARGET = old_target
            ib.DEFAULT_MIN_SELLABLE = old_min
            if old_flag:
                ib._run152_launch_readiness_installed = True
            elif hasattr(ib, "_run152_launch_readiness_installed"):
                delattr(ib, "_run152_launch_readiness_installed")

    def test_operational_overlay_blocks_26_even_if_legacy_gate_would_pass(self):
        rows = balanced_rows(26)
        old_evaluate = ib.evaluate_readiness
        old_target = ib.DEFAULT_TARGET
        old_min = ib.DEFAULT_MIN_SELLABLE
        old_flag = getattr(ib, "_run152_launch_readiness_installed", False)
        try:
            if old_flag:
                delattr(ib, "_run152_launch_readiness_installed")
            lr.install_on(ib)
            result = ib.evaluate_readiness(rows, subscriber_visible_count=26, now=NOW)
            self.assertFalse(result["launch_ready"])
            self.assertEqual(lr.POLICY_VERSION, result["launch_policy_version"])
            self.assertTrue(any("launch_sellable<50" in x for x in result["launch_blockers"]))
            self.assertTrue(any("subscriber_visible_launch_floor<50" in x for x in result["launch_blockers"]))
            self.assertEqual(60, ib.DEFAULT_TARGET)
            self.assertEqual(50, ib.DEFAULT_MIN_SELLABLE)
        finally:
            ib.evaluate_readiness = old_evaluate
            ib.DEFAULT_TARGET = old_target
            ib.DEFAULT_MIN_SELLABLE = old_min
            if old_flag:
                ib._run152_launch_readiness_installed = True
            elif hasattr(ib, "_run152_launch_readiness_installed"):
                delattr(ib, "_run152_launch_readiness_installed")

    def test_workflow_defaults_match_new_commercial_gate(self):
        workflow = (ROOT / ".github" / "workflows" / "inventory-bootstrap.yml").read_text(encoding="utf-8")
        self.assertIn('target_inventory:', workflow)
        self.assertIn('default: "60"', workflow)
        self.assertIn('min_sellable:', workflow)
        self.assertIn('default: "50"', workflow)
        self.assertIn('python portfolio_inventory_bootstrap.py', workflow)

    def test_run152_adds_no_model_call_site(self):
        source = inspect.getsource(lr)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("call_gemini", source)
        self.assertNotIn("google.genai", source)
        self.assertNotIn("GEMINI_API_KEY", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
