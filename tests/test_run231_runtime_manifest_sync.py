from __future__ import annotations

import ast
import unittest
from pathlib import Path

import runtime_layers


ROOT = Path(__file__).resolve().parents[1]


def _canonical_module_names() -> tuple[str, ...]:
    return tuple(spec.rsplit(".", 1)[0] for spec in runtime_layers.RUNTIME_LAYER_ORDER)


class Run231RuntimeManifestSyncTests(unittest.TestCase):
    def test_documentation_manifest_matches_canonical_runtime_modules_exactly(self):
        source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "install_runtime_layers"
        )
        imports = tuple(
            alias.name
            for node in function.body
            if isinstance(node, ast.Import)
            for alias in node.names
        )
        self.assertEqual(imports, _canonical_module_names())

    def test_manifest_contains_no_install_calls_and_delegates_once(self):
        source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        function = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "install_runtime_layers"
        )
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertIsInstance(call.func, ast.Name)
        self.assertEqual(call.func.id, "_canonical_install_runtime_layers")


if __name__ == "__main__":
    unittest.main()
