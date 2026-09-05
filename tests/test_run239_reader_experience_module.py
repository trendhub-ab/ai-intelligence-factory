from __future__ import annotations

import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline.py"
MODULE = ROOT / "reader_experience_signals.py"


class Run239ReaderExperienceModuleTests(unittest.TestCase):
    def _tree(self, path: pathlib.Path) -> ast.Module:
        return ast.parse(path.read_text(encoding="utf-8"))

    def _function(self, tree: ast.Module, name: str) -> ast.FunctionDef:
        matches = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
        self.assertEqual(len(matches), 1, name)
        return matches[0]

    def test_canonical_module_is_stdlib_only_and_provider_free(self):
        tree = self._tree(MODULE)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        self.assertEqual(set(imported), {"__future__", "re"})
        forbidden_names = {
            "requests", "notion", "google", "genai", "client", "os", "Path",
            "GEMINI_API_KEY", "NOTION_API_KEY", "GH_PAT",
        }
        referenced = {
            node.id for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }
        self.assertFalse(referenced & forbidden_names)

    def test_pipeline_keeps_only_exact_live_binding_wrapper(self):
        tree = self._tree(PIPELINE)
        fn = self._function(tree, "_reader_experience_signals")
        executable = list(fn.body)
        if executable and isinstance(executable[0], ast.Expr) and isinstance(executable[0].value, ast.Constant) and isinstance(executable[0].value.value, str):
            executable = executable[1:]
        self.assertEqual(len(executable), 1)
        self.assertIsInstance(executable[0], ast.Return)
        call = executable[0].value
        self.assertIsInstance(call, ast.Call)
        self.assertIsInstance(call.func, ast.Name)
        self.assertEqual(call.func.id, "_reader_experience_signals_impl")
        self.assertEqual([a.id for a in call.args if isinstance(a, ast.Name)], ["article", "_article_opening_excerpt"])
        self.assertLessEqual((fn.end_lineno or fn.lineno) - fn.lineno + 1, 4)

    def test_pipeline_import_alias_is_canonical(self):
        tree = self._tree(PIPELINE)
        matches = []
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "reader_experience_signals":
                matches.extend((a.name, a.asname) for a in node.names)
        self.assertEqual(matches, [("reader_experience_signals", "_reader_experience_signals_impl")])

    def test_heavy_algorithm_physically_left_pipeline(self):
        pipeline_source = PIPELINE.read_text(encoding="utf-8")
        module_source = MODULE.read_text(encoding="utf-8")
        self.assertNotIn("narrative_progression_hits = len(re.findall", pipeline_source)
        self.assertNotIn("reader_delight_positive_signals", pipeline_source)
        self.assertIn("narrative_progression_hits = len(re.findall", module_source)
        self.assertIn('"reader_delight_positive_signals"', module_source)
        fn = self._function(self._tree(MODULE), "reader_experience_signals")
        self.assertGreaterEqual((fn.end_lineno or fn.lineno) - fn.lineno + 1, 350)

    def test_module_has_no_hidden_pipeline_global_dependency(self):
        tree = self._tree(MODULE)
        fn = self._function(tree, "reader_experience_signals")
        assigned = {a.arg for a in fn.args.args}
        for node in ast.walk(fn):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
                assigned.add(node.id)
        allowed = {
            "re", "any", "bool", "dict", "enumerate", "len", "list", "max", "range", "round",
            "set", "sorted", "str", "sum", "tuple",
        }
        loaded = {
            node.id for node in ast.walk(fn)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in assigned
        }
        self.assertEqual(loaded - allowed, set())

    def test_reader_diagnostics_remain_soft_only(self):
        namespace = {}
        exec(MODULE.read_text(encoding="utf-8"), namespace)
        fn = namespace["reader_experience_signals"]
        article = "## テスト\n\nこれはAPIの話です。まず小さく試して比較します。ただし保証ではありません。"
        result = fn(article, lambda text, max_chars=700: text[:max_chars])
        self.assertIs(result["soft_only"], True)
        self.assertIn(result["reader_delight"], {"GOOD", "REVIEW"})
        self.assertIn("information_budget", result)
        self.assertIn("non_engineer_core_clarity", result)


if __name__ == "__main__":
    unittest.main()
