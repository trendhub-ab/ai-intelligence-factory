from pathlib import Path
import unittest

import run327_documentation_sync as run327

ROOT = Path(__file__).resolve().parents[1]


class Run327DocumentationSyncTests(unittest.TestCase):
    def test_readme_render_adds_current_note_onboarding_contract_idempotently(self):
        original = (ROOT / "README.md").read_text(encoding="utf-8")
        rendered = run327.render_readme(original)
        self.assertIn(run327.README_BASELINE, rendered)
        self.assertIn("### Run325 / Run326b — note member onboarding publication + customer-facing verification", rendered)
        self.assertIn(run327.REFERENCE, rendered)
        self.assertIn("/aiif note onboarding public-audit", rendered)
        self.assertEqual(run327.render_readme(rendered), rendered)

    def test_spec_render_updates_date_baseline_and_section_idempotently(self):
        original = (ROOT / "AI_Intelligence_Factory_最終仕様書.md").read_text(encoding="utf-8")
        rendered = run327.render_spec(original)
        self.assertIn("最終更新: 2026-09-10", rendered)
        self.assertIn(run327.SPEC_BASELINE, rendered)
        self.assertIn("### 2.8 note Member Onboarding Publication / Public Verification — Run325 / Run326b", rendered)
        self.assertIn("34388876334", rendered)
        self.assertIn("34416681984", rendered)
        self.assertIn(run327.REFERENCE, rendered)
        self.assertEqual(run327.render_spec(rendered), rendered)

    def test_current_contract_preserves_members_only_and_zero_model_invariants(self):
        readme, spec = run327.render()
        combined = readme + "\n" + spec
        for marker in (
            "trial-read line",
            "AI Decision Intelligence",
            "すべてのプラン（全員に公開）",
            "logged-out",
            "zero-click",
            "Gemini/model call 0",
            "Notion write 0",
        ):
            self.assertIn(marker, combined)

    def test_sync_is_documentation_only(self):
        source = (ROOT / "run327_documentation_sync.py").read_text(encoding="utf-8")
        self.assertNotIn("requests", source)
        self.assertNotIn("playwright", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("GEMINI", source)
        self.assertNotIn("NOTION", source)
        self.assertIn("README.md", source)
        self.assertIn("AI_Intelligence_Factory_最終仕様書.md", source)


if __name__ == "__main__":
    unittest.main()
