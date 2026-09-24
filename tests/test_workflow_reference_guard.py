from pathlib import Path
import tempfile
import textwrap
import unittest

import workflow_reference_guard as guard


ROOT = Path(__file__).resolve().parents[1]


class WorkflowReferenceGuardTests(unittest.TestCase):
    def _write(self, root: Path, path: str, content: str = "") -> None:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")

    def _base_repo(self, root: Path) -> None:
        self._write(
            root,
            ".github/workflows/upstream.yml",
            """
            name: Upstream Workflow
            on:
              workflow_dispatch:
            jobs:
              noop:
                runs-on: ubuntu-latest
                steps:
                  - run: echo ok
            """,
        )
        self._write(root, "scripts/ok.py", "print('ok')\n")
        self._write(root, "tests/test_ok.py", "def test_ok():\n    assert True\n")
        self._write(root, ".github/actions/local/action.yml", "name: local\nruns:\n  using: composite\n  steps: []\n")

    def test_valid_static_references_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_repo(root)
            self._write(
                root,
                ".github/workflows/consumer.yml",
                """
                name: Consumer Workflow
                on:
                  workflow_run:
                    workflows:
                      - Upstream Workflow
                    types: [completed]
                jobs:
                  check:
                    runs-on: ubuntu-latest
                    steps:
                      - uses: ./.github/actions/local
                      - run: |
                          python scripts/ok.py
                          python -m unittest tests.test_ok -v
                          gh workflow run "Upstream Workflow" --ref main
                """,
            )
            self.assertEqual([], guard.validate(root))

    def test_unittest_discover_pattern_is_selector_not_root_file_reference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_repo(root)
            self._write(
                root,
                ".github/workflows/discover.yml",
                """
                name: Discover Tests
                jobs:
                  check:
                    runs-on: ubuntu-latest
                    steps:
                      - run: python -m unittest discover -s tests -p 'test_ok.py' -v
                """,
            )
            self.assertEqual([], guard.validate(root))

    def test_schedule_trigger_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_repo(root)
            self._write(
                root,
                ".github/workflows/scheduled.yml",
                """
                name: Scheduled Workflow
                on:
                  schedule:
                    - cron: '20 3 * * *'
                jobs:
                  noop:
                    runs-on: ubuntu-latest
                    steps:
                      - run: echo no
                """,
            )
            errors = guard.validate(root)
            self.assertTrue(any("fixed schedule trigger is forbidden" in error for error in errors), errors)

    def test_operational_writer_push_trigger_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_repo(root)
            self._write(
                root,
                ".github/workflows/note-ready-sync.yml",
                """
                name: Note Ready Article Sync
                on:
                  workflow_dispatch:
                  push:
                    branches: [main]
                jobs:
                  noop:
                    runs-on: ubuntu-latest
                    steps:
                      - run: echo no
                """,
            )
            errors = guard.validate(root)
            self.assertTrue(any("disallowed automatic trigger(s): push" in error for error in errors), errors)

    def test_missing_script_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_repo(root)
            self._write(
                root,
                ".github/workflows/bad.yml",
                """
                name: Bad Script
                jobs:
                  check:
                    runs-on: ubuntu-latest
                    steps:
                      - run: python scripts/missing.py
                """,
            )
            errors = guard.validate(root)
            self.assertTrue(any("scripts/missing.py" in error for error in errors), errors)

    def test_missing_unittest_module_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_repo(root)
            self._write(
                root,
                ".github/workflows/bad.yml",
                """
                name: Bad Test
                jobs:
                  check:
                    runs-on: ubuntu-latest
                    steps:
                      - run: python -m unittest tests.test_missing -v
                """,
            )
            errors = guard.validate(root)
            self.assertTrue(any("tests.test_missing" in error for error in errors), errors)

    def test_missing_workflow_run_upstream_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_repo(root)
            self._write(
                root,
                ".github/workflows/bad.yml",
                """
                name: Bad Upstream
                on:
                  workflow_run:
                    workflows: [Deleted Workflow]
                    types: [completed]
                jobs:
                  check:
                    runs-on: ubuntu-latest
                    steps:
                      - run: echo no
                """,
            )
            errors = guard.validate(root)
            self.assertTrue(any("Deleted Workflow" in error for error in errors), errors)

    def test_missing_local_action_and_gh_target_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_repo(root)
            self._write(
                root,
                ".github/workflows/bad.yml",
                """
                name: Bad Local References
                jobs:
                  check:
                    runs-on: ubuntu-latest
                    steps:
                      - uses: ./.github/actions/deleted
                      - run: gh workflow run "Deleted Workflow" --ref main
                """,
            )
            errors = guard.validate(root)
            self.assertTrue(any(".github/actions/deleted" in error for error in errors), errors)
            self.assertTrue(any("gh workflow run" in error and "Deleted Workflow" in error for error in errors), errors)

    def test_literal_backslash_n_in_choice_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_repo(root)
            bad = "name: Bad Choice\non:\n  workflow_dispatch:\n    inputs:\n      mode:\n        type: choice\n        options:\n          - full" + chr(92) + "n          - stale_ready_batch_revalidation\njobs:\n  noop:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo ok\n"
            self._write(root, ".github/workflows/bad-choice.yml", bad)
            errors = guard.validate(root)
            self.assertTrue(any("literal backslash-n" in error for error in errors), errors)

    def test_literal_backslash_n_in_artifact_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_repo(root)
            bad = "name: Bad Artifact Path\njobs:\n  noop:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/upload-artifact@v4\n        with:\n          path: article_audit/a.json" + chr(92) + "n          article_audit/b.json\n"
            self._write(root, ".github/workflows/bad-path.yml", bad)
            errors = guard.validate(root)
            self.assertTrue(any("literal backslash-n" in error for error in errors), errors)

    def test_literal_backslash_n_is_allowed_inside_run_block_scalar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._base_repo(root)
            good = "name: Good Shell Newline\njobs:\n  noop:\n    runs-on: ubuntu-latest\n    steps:\n      - run: |\n          printf '%s" + chr(92) + "n' ok\n"
            self._write(root, ".github/workflows/good-shell.yml", good)
            self.assertEqual([], guard.validate(root))

    def test_current_repository_has_no_dangling_static_workflow_references(self):
        self.assertEqual([], guard.validate(ROOT))

    def test_required_repository_falsification_executes_reference_guard(self):
        workflow = (ROOT / ".github" / "workflows" / "repository-falsification.yml").read_text(encoding="utf-8")
        self.assertIn("falsify-all-tracked-surfaces:", workflow)
        self.assertIn("python workflow_reference_guard.py", workflow)
        self.assertIn("python -m unittest tests.test_workflow_reference_guard -v", workflow)


if __name__ == "__main__":
    unittest.main()


def test_one_shot_run_scoped_model_exclusion_is_strict_and_forwarded():
    one_shot = (ROOT / ".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    reserved = (ROOT / ".github/workflows/reserved-one-shot-trigger.yml").read_text(encoding="utf-8")
    assert "excluded_models:" in one_shot
    assert "AIIF_GEMINI_TEMP_EXCLUDED_MODELS: ${{ inputs.excluded_models }}" in one_shot
    assert '""|gemini-3.5-flash|gemini-3.6-flash|gemini-3.7-flash|gemini-3.8-flash' in one_shot
    assert "excluded_models=" in reserved
    assert '-f excluded_models="$EXCLUDED_MODELS"' in reserved
