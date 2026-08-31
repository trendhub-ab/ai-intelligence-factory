import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ONE_SHOT = ROOT / ".github" / "workflows" / "daily-one-shot.yml"
PAUSED_DAILY = ROOT / ".github" / "workflows" / "daily.yml"
INTEGRATION_CI = ROOT / ".github" / "workflows" / "integration-reconciliation-ci.yml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _has_trigger(text: str, name: str) -> bool:
    return bool(re.search(rf"^\s+{re.escape(name)}:\s*$", text, re.MULTILINE))


class Run177ZeroApiProductionContractTests(unittest.TestCase):
    def test_one_shot_cannot_self_retrigger(self):
        text = _read(ONE_SHOT)
        self.assertIn("workflow_dispatch:", text)
        self.assertFalse(_has_trigger(text, "push"), "ONE-SHOT must never gain a push trigger")
        self.assertFalse(_has_trigger(text, "schedule"), "ONE-SHOT must never gain a schedule trigger")
        self.assertIn("inputs.confirm == 'RUN_ONCE'", text)
        self.assertIn("ref: main", text)

    def test_paused_daily_remains_hard_disabled(self):
        text = _read(PAUSED_DAILY)
        self.assertFalse(_has_trigger(text, "schedule"), "PAUSED Daily must not have a schedule")
        self.assertIn("if: ${{ false }}", text)
        self.assertIn("contents: read", text)
        self.assertIn("MINIMUM SAFETY CONTRACT", text)

    def test_one_shot_and_paused_daily_share_gemini_budget_lock(self):
        one_shot = _read(ONE_SHOT)
        paused = _read(PAUSED_DAILY)
        lock = "group: ai-intelligence-gemini-budget"
        self.assertIn(lock, one_shot)
        self.assertIn(lock, paused)

    def test_article_validation_mode_preserves_article_pipeline_but_skips_product_review(self):
        text = _read(ONE_SHOT)
        self.assertIn("- article_validation", text)
        self.assertIn("default: 'full'", text, "default behavior must remain the full production one-shot")
        article_step = text.index("- name: 通常Pipelineを1回だけ実行")
        review_step = text.index("- name: Portfolio-aware Product Review")
        guard_step = text.index("- name: Article validation API-saving guard")
        self.assertLess(article_step, review_step)
        self.assertLess(review_step, guard_step)
        self.assertIn("if: ${{ inputs.mode == 'full' }}", text[review_step:guard_step])
        self.assertIn("if: ${{ inputs.mode == 'article_validation' }}", text[guard_step:])
        self.assertNotIn("inputs.mode == 'article_validation'", text[article_step:review_step])

    def test_article_validation_saves_only_bounded_separate_review_budget(self):
        text = _read(ONE_SHOT)
        review_step = text.index("- name: Portfolio-aware Product Review")
        guard_step = text.index("- name: Article validation API-saving guard")
        review_block = text[review_step:guard_step]
        self.assertIn('DAILY_PORTFOLIO_REQUEST_BUDGET: "3"', review_block)
        self.assertIn('DAILY_PORTFOLIO_REVIEW_MAX: "2"', review_block)
        self.assertIn("if: ${{ inputs.mode == 'full' }}", review_block)

    def test_integration_ci_watches_production_contract_surface(self):
        text = _read(INTEGRATION_CI)
        for required in (
            "'production_pipeline.py'",
            "'daily_portfolio_review.py'",
            "'run*.py'",
            "'.github/workflows/daily.yml'",
            "'.github/workflows/daily-one-shot.yml'",
            "'tests/**'",
        ):
            self.assertIn(required, text)
        for module in (
            "production_pipeline.py",
            "daily_portfolio_review.py",
            "run175_semantic_fact_precision.py",
            "run176_scope_fidelity.py",
        ):
            self.assertIn(module, text)


if __name__ == "__main__":
    unittest.main()
