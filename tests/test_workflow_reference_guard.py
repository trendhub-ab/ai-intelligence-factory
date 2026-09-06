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

    def test_current_repository_has_no_dangling_static_workflow_references(self):
        self.assertEqual([], guard.validate(ROOT))

    def test_required_repository_falsification_executes_reference_guard(self):
        workflow = (ROOT / ".github" / "workflows" / "repository-falsification.yml").read_text(encoding="utf-8")
        self.assertIn("falsify-all-tracked-surfaces:", workflow)
        self.assertIn("python workflow_reference_guard.py", workflow)
        self.assertIn("python -m unittest tests.test_workflow_reference_guard -v", workflow)


if __name__ == "__main__":
    unittest.main()
