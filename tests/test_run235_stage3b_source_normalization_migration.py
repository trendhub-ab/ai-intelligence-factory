from __future__ import annotations

import ast
import pathlib
import subprocess
import sys
import tempfile
import unittest

import run235_stage3b_source_normalization_migration as migration


ROOT = pathlib.Path(__file__).resolve().parents[1]
PATCH_PATH = ROOT / "patches" / "run235-stage3b-source-normalization.patch"
MIGRATION_PATH = ROOT / "run235_stage3b_source_normalization_migration.py"
PREIMAGE_FIXTURE_PATH = ROOT / "tests" / "fixtures" / "run235_stage3b_pipeline_preimage.py.txt"
HISTORICAL_PATCH_RETURN_LINE = 3144


def _historical_preimage() -> str:
    """Return the frozen Run235 Stage3A preimage at the patch's original line offset.

    The fixture intentionally contains only the historical surgical neighborhood.  Padding
    restores the original hunk line so the committed patch can be validated without making
    any later pipeline.py layout part of Run235's contract.
    """
    fixture = PREIMAGE_FIXTURE_PATH.read_text(encoding="utf-8")
    lines = fixture.splitlines(keepends=True)
    return_index = next(
        i for i, line in enumerate(lines, start=1)
        if line == "    return datetime.now(JST).isoformat()\n"
    )
    if return_index > HISTORICAL_PATCH_RETURN_LINE:
        raise AssertionError("Run235 fixture no longer fits its historical patch offset")
    return ("\n" * (HISTORICAL_PATCH_RETURN_LINE - return_index)) + fixture


class Run235Stage3BSourceNormalizationMigrationTests(unittest.TestCase):
    def test_current_pipeline_is_single_canonical_source_and_idempotent(self):
        source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        transformed = migration.transform_source(source)
        tree = ast.parse(source)
        wanted = set(migration.EXPORTED_NAMES)
        duplicate_defs = {
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted
        }
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "source_normalization":
                imported.update(alias.asname or alias.name for alias in node.names)
        self.assertEqual(transformed, source)
        self.assertFalse(duplicate_defs)
        self.assertTrue(wanted.issubset(imported))

    def test_transform_is_idempotent_after_migration(self):
        source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        self.assertEqual(migration.transform_source(source), source)

    def test_unexpected_surface_fails_closed(self):
        bad = "def normalize_item():\n    pass\n"
        with self.assertRaises(RuntimeError):
            migration.transform_source(bad)

    def test_historical_fixture_compiles_and_preserves_adjacent_function(self):
        preimage = _historical_preimage()
        transformed = migration.transform_source(preimage)
        compile(preimage, "run235_stage3a_preimage.py", "exec")
        compile(transformed, "run235_stage3b_postimage.py", "exec")
        self.assertIn("def _truncate_text_context", preimage)
        self.assertIn("def _truncate_text_context", transformed)

    def test_cli_never_writes_without_explicit_write_flag(self):
        preimage = _historical_preimage()
        postimage = migration.transform_source(preimage)
        self.assertNotEqual(preimage, postimage)

        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "pipeline.py"
            path.write_text(preimage, encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(MIGRATION_PATH), str(path)],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("changed=true", result.stdout)
            self.assertEqual(path.read_text(encoding="utf-8"), preimage)

    def test_committed_patch_round_trips_against_frozen_run235_fixture(self):
        preimage = _historical_preimage()
        postimage = migration.transform_source(preimage)

        with tempfile.TemporaryDirectory() as td:
            work = pathlib.Path(td)
            path = work / "pipeline.py"
            path.write_text(preimage, encoding="utf-8")

            forward = subprocess.run(
                ["git", "apply", str(PATCH_PATH)],
                cwd=work,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(forward.returncode, 0, msg=forward.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), postimage)

            reverse = subprocess.run(
                ["git", "apply", "--reverse", str(PATCH_PATH)],
                cwd=work,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(reverse.returncode, 0, msg=reverse.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), preimage)


if __name__ == "__main__":
    unittest.main()
