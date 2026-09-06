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

    def test_all_direct_one_shot_fanout_targets_are_explicit_and_not_passive(self) -> None:
        one_shot = (ROOT / ".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
        self.assertIn("GH_TOKEN: ${{ secrets.GH_PAT }}", one_shot)
        self.assertIn("if: ${{ success() }}", one_shot)

        for name in guard.DIRECT_ONE_SHOT_FANOUT_TARGETS:
            source = (ROOT / ".github/workflows" / name).read_text(encoding="utf-8")
            self.assertIn(name, one_shot, name)
            self.assertIn("workflow_dispatch:", source, name)
            self.assertNotIn(
                "Daily Intelligence & Content Pipeline [ONE-SHOT]",
                guard._workflow_run_block(source),
                name,
            )
            self.assertIn("cancel-in-progress: false", source, name)


if __name__ == "__main__":
    unittest.main()
