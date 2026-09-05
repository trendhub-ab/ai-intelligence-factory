from __future__ import annotations

import ast
import pathlib
import unittest

import evidence_context


ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "pipeline.py"


def _top_level_defs(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _assert_return_call(
    testcase: unittest.TestCase,
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    callee: str,
    arg_names: list[str],
) -> None:
    testcase.assertEqual(len(fn.body), 1)
    ret = fn.body[0]
    testcase.assertIsInstance(ret, ast.Return)
    call = ret.value
    testcase.assertIsInstance(call, ast.Call)
    testcase.assertIsInstance(call.func, ast.Name)
    testcase.assertEqual(call.func.id, callee)
    testcase.assertEqual(len(call.args), len(arg_names))
    actual_args: list[str] = []
    for arg in call.args:
        testcase.assertIsInstance(arg, ast.Name)
        actual_args.append(arg.id)
    testcase.assertEqual(actual_args, arg_names)
    testcase.assertFalse(call.keywords)


class Run236EvidenceContextModuleTests(unittest.TestCase):
    def test_module_is_provider_environment_and_persistence_free(self):
        source = pathlib.Path(evidence_context.__file__).read_text(encoding="utf-8")
        forbidden = (
            "requests.",
            "genai",
            "GEMINI_API_KEY",
            "NOTION_API_KEY",
            "save_to_notion",
            "github.com/",
            "api.notion.com",
            "os.environ",
            "os.getenv",
        )
        for token in forbidden:
            self.assertNotIn(token, source)

    def test_evidence_context_is_canonical_owner_of_pure_algorithms(self):
        module_source = pathlib.Path(evidence_context.__file__).read_text(encoding="utf-8")
        module_defs = _top_level_defs(ast.parse(module_source))
        self.assertTrue(
            {
                "truncate_text_context",
                "verification_excerpt",
                "merge_verification_context",
            }.issubset(module_defs)
        )

        pipeline_source = PIPELINE_PATH.read_text(encoding="utf-8")
        pipeline_tree = ast.parse(pipeline_source)
        pipeline_defs = _top_level_defs(pipeline_tree)
        self.assertNotIn("_truncate_text_context", pipeline_defs)
        self.assertNotIn("_verification_excerpt", pipeline_defs)
        self.assertIn("_truncate_source_context", pipeline_defs)
        self.assertIn("_truncate_verification_context", pipeline_defs)
        self.assertIn("_merge_verification_context", pipeline_defs)

        imported_aliases = set()
        for node in pipeline_tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "evidence_context":
                imported_aliases.update(alias.asname or alias.name for alias in node.names)
        self.assertTrue(
            {
                "_truncate_text_context",
                "_verification_excerpt",
                "_merge_verification_context_impl",
            }.issubset(imported_aliases)
        )

    def test_truncate_text_context_contract(self):
        samples = [
            ("", 10, ""),
            ("  alpha\n\n\n\nbeta  ", 100, "alpha\n\nbeta"),
            ("abcdef", 3, "abc"),
            ("abcdef", 0, ""),
            ("abcdef", -5, ""),
        ]
        for text, limit, expected in samples:
            self.assertEqual(evidence_context.truncate_text_context(text, limit), expected)

    def test_verification_excerpt_contract_keeps_head_tail_and_small_limit_behavior(self):
        text = "HEAD-" + ("a" * 180) + "\n\n\n\n" + ("z" * 180) + "-TAIL"
        normalized = text.replace("\n\n\n\n", "\n\n")
        self.assertEqual(evidence_context.verification_excerpt(text, 0), "")
        self.assertEqual(evidence_context.verification_excerpt(text, 32), normalized[:32])
        self.assertEqual(evidence_context.verification_excerpt(text, 64), normalized[:64])

        limit = 120
        marker = "\n\n[...verification context omitted...]\n\n"
        payload = limit - len(marker)
        head = int(payload * 0.68)
        tail = payload - head
        expected = normalized[:head] + marker + normalized[-tail:]
        self.assertEqual(evidence_context.verification_excerpt(text, limit), expected)
        self.assertEqual(len(expected), limit)
        self.assertEqual(evidence_context.verification_excerpt(text, 1000), normalized)

    def test_merge_verification_context_contract_prioritizes_new_evidence(self):
        old = "OLD-" + ("a" * 100)
        new = "NEW-" + ("b" * 100)
        self.assertEqual(
            evidence_context.merge_verification_context("", new, 40),
            evidence_context.verification_excerpt(new, 40),
        )
        self.assertEqual(
            evidence_context.merge_verification_context(old, "", 40),
            evidence_context.verification_excerpt(old, 40),
        )
        self.assertEqual(
            evidence_context.merge_verification_context("old", "new", 100),
            "old\n\nnew",
        )

        limit = 80
        merged = evidence_context.merge_verification_context(old, new, limit)
        payload = limit - 2
        new_budget = min(len(new), int(payload * 0.60))
        old_budget = payload - new_budget
        expected = (
            evidence_context.verification_excerpt(old, old_budget)
            + "\n\n"
            + evidence_context.verification_excerpt(new, new_budget)
        )
        self.assertEqual(merged, expected)
        self.assertEqual(len(merged), limit)

    def test_pipeline_wrappers_are_exact_dynamic_limit_bindings(self):
        source = PIPELINE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        defs = _top_level_defs(tree)
        _assert_return_call(
            self,
            defs["_truncate_source_context"],
            "_truncate_text_context",
            ["text", "SOURCE_CONTEXT_MAX_CHARS"],
        )
        _assert_return_call(
            self,
            defs["_truncate_verification_context"],
            "_truncate_text_context",
            ["text", "VERIFICATION_CONTEXT_MAX_CHARS"],
        )
        _assert_return_call(
            self,
            defs["_merge_verification_context"],
            "_merge_verification_context_impl",
            ["existing", "new_evidence", "VERIFICATION_CONTEXT_MAX_CHARS"],
        )

    def test_pipeline_contains_no_moved_heavy_algorithm(self):
        source = PIPELINE_PATH.read_text(encoding="utf-8")
        self.assertIn("from evidence_context import (", source)
        self.assertIn("merge_verification_context as _merge_verification_context_impl", source)
        self.assertNotIn("[...verification context omitted...]", source)
        self.assertNotIn("new_budget = min(len(new), int(payload * 0.60))", source)


if __name__ == "__main__":
    unittest.main()
