from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ONE_SHOT = ROOT / ".github" / "workflows" / "daily-one-shot.yml"
EXPECTED_MODELS = "gemini-3.6-flash,gemini-3.5-flash,gemini-3.7-flash,gemini-3.8-flash"


class P0BDailyReadyOnlyWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = ONE_SHOT.read_text(encoding="utf-8")

    def test_ready_only_input_is_explicit_boolean_and_defaults_off(self) -> None:
        self.assertIn("p0b_ready_only:", self.source)
        block = self.source.split("p0b_ready_only:", 1)[1].split("confirm:", 1)[0]
        self.assertIn("default: false", block)
        self.assertIn("type: boolean", block)

    def test_ready_only_is_full_mode_only(self) -> None:
        self.assertIn("p0b_ready_only is full-mode-only", self.source)
        self.assertIn("inputs.p0b_ready_only", self.source)
        self.assertIn('inputs.mode }}" != "full"', self.source)

    def test_ready_only_keeps_exact_ready_sync_but_suppresses_private_draft(self) -> None:
        self.assertIn("P0B_READY_ONLY: ${{ inputs.p0b_ready_only }}", self.source)
        self.assertIn('effective_create_private_draft="$create_private_draft"', self.source)
        self.assertIn('effective_create_private_draft=false', self.source)
        self.assertGreaterEqual(
            self.source.count('-f create_private_draft="$effective_create_private_draft"'),
            2,
        )
        self.assertIn('-f target_source_url="${target_source_urls[0]}"', self.source)
        self.assertIn('-f target_source_url="$target_source_url"', self.source)
        self.assertIn("DELIVERY_CREATE_PRIVATE_DRAFT", self.source)

    def test_daily_production_models_are_non_lite_in_required_fallback_order(self) -> None:
        self.assertNotIn("flash-lite", self.source)
        self.assertEqual(self.source.count(EXPECTED_MODELS), 2)
        self.assertIn(f'GEMINI_SCREENING_MODEL_CANDIDATES: "{EXPECTED_MODELS}"', self.source)
        self.assertIn(f'GEMINI_DEEP_DIVE_MODEL_CANDIDATES: "{EXPECTED_MODELS}"', self.source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
