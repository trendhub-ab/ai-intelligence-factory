import ast
from pathlib import Path
import symtable
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import content_generation_protocol as protocol


class Run243ContentGenerationProtocolModuleTests(unittest.TestCase):
    def test_module_import_surface_is_stdlib_only(self):
        source = (ROOT / "content_generation_protocol.py").read_text()
        tree = ast.parse(source)
        imports = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        self.assertEqual(set(imports), {"__future__", "re"})
        forbidden_calls = {"open", "urlopen", "get", "post", "put", "patch", "delete", "request"}
        calls = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue(forbidden_calls.isdisjoint(calls))

    def test_source_fact_discipline_is_source_specific_without_external_state(self):
        github = protocol._source_fact_discipline("GitHub")
        arxiv = protocol._source_fact_discipline("ArXiv")
        self.assertIn("全ソース共通 Fact Discipline", github)
        self.assertIn("GitHub専用 Fact Discipline", github)
        self.assertNotIn("arXiv専用 Fact Discipline", github)
        self.assertIn("arXiv専用 Fact Discipline", arxiv)

    def test_human_editorial_style_contract_remains_present(self):
        rules = protocol._human_editorial_style_rules()
        self.assertIn("Human Editorial Style｜最重要", rules)
        self.assertIn("Reader Experience｜知的エンタメ × Decision Intelligence", rules)
        self.assertIn("架空の経験", rules)

    def test_plaintext_heading_repair_is_conservative_for_short_text(self):
        body = "短い本文です。\n\n見出し候補\n\nまだ短い本文です。"
        repaired, promoted = protocol._promote_plaintext_section_titles(body)
        self.assertEqual(repaired, body)
        self.assertEqual(promoted, [])

    def test_empty_monthly_digest_keeps_month_and_zero_item_contract(self):
        class D:
            year = 2026
            month = 9
        text = protocol.build_monthly_digest_markdown(
            D(), [], STATUS_DEEP_DIVE="Deep Dive", ARTICLE_STATUS_READY="Ready", STATUS_STOCKED="Stocked"
        )
        self.assertIn("2026年9月", text)
        self.assertIsInstance(text, str)

    def test_moved_function_sizes_remain_substantive_canonical_owners(self):
        source = (ROOT / "content_generation_protocol.py").read_text()
        tree = ast.parse(source)
        funcs = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        expected_minimums = {
            "build_monthly_digest_markdown": 60,
            "_source_fact_discipline": 55,
            "_human_editorial_style_rules": 65,
            "_parse_gemini_response": 90,
            "_promote_plaintext_section_titles": 55,
        }
        for name, minimum in expected_minimums.items():
            self.assertIn(name, funcs)
            size = funcs[name].end_lineno - funcs[name].lineno + 1
            self.assertGreaterEqual(size, minimum, name)

    def test_self_contained_prompt_functions_have_no_runtime_globals(self):
        source = (ROOT / "content_generation_protocol.py").read_text()
        table = symtable.symtable(source, "content_generation_protocol.py", "exec")
        children = {c.get_name(): c for c in table.get_children() if c.get_type() == "function"}
        for name in ("_source_fact_discipline", "_human_editorial_style_rules"):
            globals_used = {
                s.get_name() for s in children[name].get_symbols()
                if s.is_global() and s.is_referenced()
            }
            globals_used -= set(dir(__builtins__))
            self.assertEqual(globals_used, set(), name)


if __name__ == "__main__":
    unittest.main()
