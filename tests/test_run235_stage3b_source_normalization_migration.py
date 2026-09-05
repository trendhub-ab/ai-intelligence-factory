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


def _reverse_patch_to_preimage(postimage: str) -> str:
    """Reconstruct the exact Stage3A preimage from the committed Stage3B postimage."""
    with tempfile.TemporaryDirectory() as td:
        work = pathlib.Path(td)
        path = work / "pipeline.py"
        path.write_text(postimage, encoding="utf-8")
        result = subprocess.run(
            ["git", "apply", "--reverse", str(PATCH_PATH)],
            cwd=work,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return path.read_text(encoding="utf-8")


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

    def test_output_compiles_and_preserves_adjacent_function(self):
        source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        compile(source, "pipeline.py", "exec")
        self.assertIn("def _truncate_text_context", source)

        preimage = _reverse_patch_to_preimage(source)
        transformed = migration.transform_source(preimage)
        self.assertEqual(transformed, source)
        compile(transformed, "pipeline.py", "exec")
        self.assertIn("def _truncate_text_context", transformed)

    def test_cli_never_writes_without_explicit_write_flag(self):
        postimage = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        preimage = _reverse_patch_to_preimage(postimage)
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

    def test_committed_patch_round_trips_and_matches_exact_migration_output(self):
        postimage = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        preimage = _reverse_patch_to_preimage(postimage)
        self.assertEqual(migration.transform_source(preimage), postimage)

        with tempfile.TemporaryDirectory() as td:
            work = pathlib.Path(td)
            path = work / "pipeline.py"
            path.write_text(preimage, encoding="utf-8")
            result = subprocess.run(
                ["git", "apply", str(PATCH_PATH)],
                cwd=work,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), postimage)


if __name__ == "__main__":
    unittest.main()
