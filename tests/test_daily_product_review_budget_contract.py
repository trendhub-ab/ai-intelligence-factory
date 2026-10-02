import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "daily-one-shot.yml"


class DailyProductReviewBudgetContractTests(unittest.TestCase):
    def test_daily_portfolio_review_budget_covers_all_four_upper_flash_fallbacks(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        marker = "- name: Portfolio-aware Product Review"
        self.assertIn(marker, text)
        section = text.split(marker, 1)[1].split("- name: API-saving mode guard", 1)[0]
        self.assertIn('DAILY_PORTFOLIO_REQUEST_BUDGET: "4"', section)
        self.assertNotIn('DAILY_PORTFOLIO_REQUEST_BUDGET: "3"', section)
        self.assertIn(
            'GEMINI_DEEP_DIVE_MODEL_CANDIDATES: "gemini-3.6-flash,gemini-3.7-flash,gemini-3.8-flash,gemini-3.5-flash"',
            section,
        )


if __name__ == "__main__":
    unittest.main()
