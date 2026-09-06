from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
ONE_SHOT = ROOT / ".github" / "workflows" / "daily-one-shot.yml"
NOTE_READY = ROOT / ".github" / "workflows" / "note-ready-sync.yml"
SUBSCRIBER = ROOT / ".github" / "workflows" / "subscriber-decision-brief.yml"
CROSS_DB = ROOT / ".github" / "workflows" / "cross-db-contract-guard.yml"


class Run261LiveRoutingFanoutTests(unittest.TestCase):
    def test_one_shot_uses_canonical_run260_article_pool(self):
        text = ONE_SHOT.read_text(encoding="utf-8")
        canonical = 'GEMINI_DEEP_DIVE_MODEL_CANDIDATES: "gemini-3.7-flash,gemini-3.8-flash,gemini-3.6-flash,gemini-3.5-flash"'
        self.assertGreaterEqual(text.count(canonical), 2)
        self.assertGreaterEqual(text.count('GEMINI_38_FLASH_DAILY_BUDGET: "18"'), 2)
        self.assertIn('GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET: "12"', text)

    def test_one_shot_explicitly_dispatches_all_direct_downstream_targets_with_gh_pat(self):
        text = ONE_SHOT.read_text(encoding="utf-8")
        self.assertIn('GH_TOKEN: ${{ secrets.GH_PAT }}', text)
        self.assertIn('GH_PAT is required for authoritative ONE-SHOT downstream fan-out', text)
        for target in (
            "note-ready-sync.yml",
            "subscriber-decision-brief.yml",
            "cross-db-contract-guard.yml",
        ):
            self.assertRegex(text, rf'gh workflow run .*\$\{{target\}}|for target in .*{re.escape(target)}')
        self.assertIn('if: ${{ success() }}', text)

    def test_direct_downstream_workflows_accept_workflow_dispatch(self):
        for path in (NOTE_READY, SUBSCRIBER, CROSS_DB):
            text = path.read_text(encoding="utf-8")
            self.assertRegex(text, r'(?m)^\s*workflow_dispatch:\s*$')

    def test_no_direct_downstream_passively_subscribes_to_one_shot(self):
        upstream = "Daily Intelligence & Content Pipeline [ONE-SHOT]"
        for path in (NOTE_READY, SUBSCRIBER, CROSS_DB):
            text = path.read_text(encoding="utf-8")
            workflow_run_match = re.search(
                r'(?ms)^\s*workflow_run:\s*\n(?P<body>.*?)(?=^\s{2}[A-Za-z_][A-Za-z0-9_-]*:|^permissions:|^concurrency:|^jobs:|\Z)',
                text,
            )
            if workflow_run_match:
                self.assertNotIn(upstream, workflow_run_match.group("body"), path.name)

    def test_scheduled_daily_and_public_release_are_not_enabled_by_run261(self):
        daily = (ROOT / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
        self.assertNotIn("schedule:", daily)
        self.assertIn('if: ${{ false }}', daily)
        one_shot = ONE_SHOT.read_text(encoding="utf-8")
        self.assertNotIn("note.com", one_shot)


if __name__ == "__main__":
    unittest.main()
