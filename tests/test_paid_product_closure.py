from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PaidProductClosureContractTests(unittest.TestCase):
    def test_full_daily_keeps_product_review_in_one_dedicated_portfolio_pass(self):
        text = (ROOT / ".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
        self.assertIn('PRODUCT_REVIEW_MAX_PER_RUN: "0"', text)
        self.assertIn('LEGACY_BOOTSTRAP_MAX_PER_RUN: "0"', text)
        self.assertIn("- name: Portfolio-aware Product Review", text)
        self.assertIn('DAILY_PORTFOLIO_REVIEW_MAX: "2"', text)
        self.assertIn('DAILY_PORTFOLIO_REQUEST_BUDGET: "3"', text)
        self.assertIn("run: python daily_portfolio_review.py", text)

    def test_full_daily_reconciles_prior_human_publication_without_publishing(self):
        text = (ROOT / ".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
        self.assertIn("Reconcile prior human-published note articles into Notion", text)
        self.assertIn("python note_publication_reconcile.py", text)
        self.assertIn("publication action remains human-only", text)
        self.assertIn("inputs.mode == 'full'", text)

    def test_member_sync_refreshes_exact_paid_monthly_brief(self):
        text = (ROOT / ".github/workflows/member-presentation-sync.yml").read_text(encoding="utf-8")
        self.assertIn("python member_monthly_decision_brief_sync.py", text)
        self.assertIn("MEMBER_MONTHLY_BRIEF_PAGE_ID: '3d0479ff-dca9-81de-b614-fef528d2f32c'", text)
        self.assertIn("tests/test_member_monthly_decision_brief_sync.py", text)

    def test_monthly_brief_has_no_model_or_note_write_surface(self):
        text = (ROOT / "member_monthly_decision_brief_sync.py").read_text(encoding="utf-8").lower()
        for token in ("gemini_api_key", "genai.", "note.com/", "playwright"):
            self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
