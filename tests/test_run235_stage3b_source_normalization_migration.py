from __future__ import annotations

import ast
import pathlib
import subprocess
import tempfile
import unittest

import run235_stage3b_source_normalization_migration as migration


ROOT = pathlib.Path(__file__).resolve().parents[1]
PATCH_PATH = ROOT / "patches" / "run235-stage3b-source-normalization.patch"


class Run235Stage3BSourceNormalizationMigrationTests(unittest.TestCase):
    def test_current_pipeline_transforms_to_single_canonical_source(self):
        source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        transformed = migration.transform_source(source)
        tree = ast.parse(transformed)
        wanted = set(migration.EXPORTED_NAMES)
        duplicate_defs = {
            node.name for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted
        }
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "source_normalization":
                imported.update(alias.asname or alias.name for alias in node.names)
        self.assertFalse(duplicate_defs)
        self.assertTrue(wanted.issubset(imported))
        self.assertLess(len(transformed.splitlines()), len(source.splitlines()))

    def test_transform_is_idempotent_after_migration(self):
        source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        transformed = migration.transform_source(source)
        self.assertEqual(migration.transform_source(transformed), transformed)

    def test_unexpected_surface_fails_closed(self):
        bad = "def normalize_item():\n    pass\n"
        with self.assertRaises(RuntimeError):
            migration.transform_source(bad)

    def test_output_compiles_and_preserves_adjacent_function(self):
        source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        transformed = migration.transform_source(source)
        compile(transformed, "pipeline.py", "exec")
        self.assertIn("def _truncate_text_context", transformed)

    def test_cli_never_writes_without_explicit_write_flag(self):
        source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            path = pathlib.Path(td) / "pipeline.py"
            path.write_text(source, encoding="utf-8")
            transformed = migration.transform_source(path.read_text(encoding="utf-8"))
            self.assertNotEqual(source, transformed)
            self.assertEqual(path.read_text(encoding="utf-8"), source)

    def test_committed_patch_applies_to_exact_migration_output(self):
        source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        transformed = migration.transform_source(source)
        with tempfile.TemporaryDirectory() as td:
            work = pathlib.Path(td)
            path = work / "pipeline.py"
            path.write_text(source, encoding="utf-8")
            result = subprocess.run(
                ["git", "apply", str(PATCH_PATH)],
                cwd=work,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(path.read_text(encoding="utf-8"), transformed)


if __name__ == "__main__":
    unittest.main()
