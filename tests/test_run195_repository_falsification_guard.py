from __future__ import annotations

import unittest
from pathlib import Path

import publication_contract
import repository_falsification_guard as guard


ROOT = Path(__file__).resolve().parents[1]


class Run195RepositoryFalsificationGuardTests(unittest.TestCase):
    def test_repository_wide_guard_is_clean(self) -> None:
        self.assertEqual([], guard.audit())

    def test_publication_manifest_is_content_addressed_not_manual_run_only(self) -> None:
        body = "本文" * 150
        caption = publication_contract.current_ready_caption(body)
        self.assertIn("policy_sha256=", caption)
        self.assertIn("manuscript_sha256=", caption)
        self.assertTrue(publication_contract.is_current_ready_block(body, caption))
        self.assertFalse(publication_contract.is_current_ready_block(body + "改変", caption))

    def test_real_article_regression_uses_production_entrypoint(self) -> None:
        source = (ROOT / ".github/workflows/regression-test.yml").read_text(encoding="utf-8")
        self.assertIn("REGEN_TEST_MODE: \"true\"", source)
        self.assertIn("run: python production_pipeline.py", source)
        self.assertNotIn("run: python reader_value_review_bridge.py", source)

    def test_all_daily_derived_views_follow_one_shot(self) -> None:
        for name in guard.DERIVED_DAILY_WORKFLOWS:
            source = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn("Daily Intelligence & Content Pipeline [ONE-SHOT]", source, name)
            self.assertIn("github.event.workflow_run.head_branch == 'main'", source, name)
            self.assertIn("cancel-in-progress: false", source, name)


if __name__ == "__main__":
    unittest.main()
