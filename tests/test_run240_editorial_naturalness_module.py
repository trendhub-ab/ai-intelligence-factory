import ast
import pathlib
import unittest

import editorial_naturalness as en


ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline.py"
MODULE = ROOT / "editorial_naturalness.py"


class Run240EditorialNaturalnessModuleTests(unittest.TestCase):
    def test_module_is_stdlib_only_and_provider_free(self):
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
        self.assertTrue(imports <= {"__future__", "re", "difflib", "typing"}, imports)
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        self.assertFalse(names & {"requests", "genai", "client", "NOTION_API_KEY", "GH_PAT"})

    def test_claim_classification_contract(self):
        parsed = {
            "note_draft": "原資料で仕様を確認できる。一方で課題もある。私なら比較テストをしたい。",
            "action_text": "小さく検証したい。",
        }
        result = en.classify_article_claims(parsed)
        self.assertGreaterEqual(result["fact"], 1)
        self.assertGreaterEqual(result["observation"], 1)
        self.assertGreaterEqual(result["decision"], 1)

    def test_fabricated_persona_contract(self):
        self.assertTrue(en.find_fabricated_personal_experience("私はこの製品を使ってみた。"))
        self.assertEqual(en.find_fabricated_personal_experience("私なら小さく検証します。"), [])

    def test_ai_style_requires_composite_not_single_phrase(self):
        variants = [{k: f"h-{k}" for k in ("intro", "conclusion", "why", "what", "key", "decision", "final")}]
        weak = en.ai_style_composite_signals("興味深い機能です。", variants)
        self.assertFalse(weak["high"])
        self.assertEqual(weak["score"], 0)

    def test_shingles_and_jaccard_contract(self):
        a = en.sentence_shingles("これは自然な日本語の文章です。", 5)
        b = en.sentence_shingles("これは自然な日本語の文章です。", 5)
        self.assertTrue(a)
        self.assertEqual(en.jaccard(a, b), 1.0)
        self.assertEqual(en.jaccard(set(), b), 0.0)

    def test_depth_detector_keeps_high_threshold(self):
        text = "そのため、同じ説明を何度も繰り返すことになります。" * 10
        result = en.human_editorial_depth_signals(text)
        self.assertIn("score", result)
        self.assertEqual(result["high"], result["score"] >= 4)

    def test_cross_article_high_threshold_remains_four(self):
        source = MODULE.read_text(encoding="utf-8")
        self.assertIn('best["high"] = best["score"] >= 4', source)

    def test_pipeline_keeps_only_thin_live_binding_wrappers(self):
        source = PIPELINE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        targets = {
            "_classify_article_claims", "_find_fabricated_personal_experience",
            "_ai_style_composite_signals", "_sentence_shingles", "_jaccard",
            "_human_editorial_depth_signals", "_style_sequence",
            "_rhetorical_template_phrases", "_cross_article_naturalness_signals",
        }
        functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
        self.assertTrue(targets <= functions.keys())
        for name in targets:
            node = functions[name]
            self.assertLessEqual(node.end_lineno - node.lineno + 1, 5, name)
        self.assertIn("from editorial_naturalness import (", source)
        for marker in ("editorial_register_patterns =", "near_duplicate_pairs = 0", "SequenceMatcher(None, seq"):
            self.assertNotIn(marker, source)


if __name__ == "__main__":
    unittest.main()
