import ast
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", "0")

import content_generation_protocol as protocol
import pipeline


class Run243ContentGenerationProtocolIntegrationTests(unittest.TestCase):
    def _module_parse(self, full_text: str) -> dict:
        return protocol._parse_gemini_response(
            full_text,
            SECTION_SPLIT_TOKEN=pipeline.SECTION_SPLIT_TOKEN,
            _display_heading_aliases=pipeline._display_heading_aliases,
            _extract_any_markdown_section=pipeline._extract_any_markdown_section,
            _extract_note_title=pipeline._extract_note_title,
            _is_meaningful_field=pipeline._is_meaningful_field,
            _normalize_decision=pipeline._normalize_decision,
            _strip_internal_note_control_lines=pipeline._strip_internal_note_control_lines,
        )

    def test_direct_aliases_are_exact_canonical_functions(self):
        self.assertIs(pipeline._source_fact_discipline, protocol._source_fact_discipline)
        self.assertIs(pipeline._human_editorial_style_rules, protocol._human_editorial_style_rules)
        self.assertIs(pipeline._promote_plaintext_section_titles, protocol._promote_plaintext_section_titles)

    def test_parser_wrapper_matches_canonical_module(self):
        text = "・Decision Score：合計: 0/100\n"
        self.assertEqual(pipeline._parse_gemini_response(text), self._module_parse(text))

    def test_parser_wrapper_reads_live_title_callback(self):
        marker = "\n__RUN243_SPLIT__\n"
        with patch.object(pipeline, "SECTION_SPLIT_TOKEN", marker), \
             patch.object(pipeline, "_extract_note_title", return_value=("LIVE TITLE", "本文です。")) as title_fn, \
             patch.object(pipeline, "_strip_internal_note_control_lines", side_effect=lambda body: (body, [])):
            pipeline._parse_gemini_response("・Decision Score：合計: 0/100" + marker + "ignored")
        title_fn.assert_called_once()

    def test_monthly_digest_wrapper_reads_live_status_constants(self):
        class D:
            year = 2026
            month = 9
        items = [{
            "status": "LIVE_DEEP",
            "article_status": "NOT_READY",
            "source": "GitHub",
            "score": 77,
            "name": "Example",
            "url": "https://example.com",
        }]
        with patch.object(pipeline, "STATUS_DEEP_DIVE", "LIVE_DEEP"), \
             patch.object(pipeline, "ARTICLE_STATUS_READY", "LIVE_READY"), \
             patch.object(pipeline, "STATUS_STOCKED", "LIVE_STOCK"):
            wrapped = pipeline.build_monthly_digest_markdown(D(), items)
            direct = protocol.build_monthly_digest_markdown(
                D(), items,
                STATUS_DEEP_DIVE="LIVE_DEEP",
                ARTICLE_STATUS_READY="LIVE_READY",
                STATUS_STOCKED="LIVE_STOCK",
            )
        self.assertEqual(wrapped, direct)
        self.assertIn("LIVE_STOCK 1件", wrapped)

    def test_pipeline_physically_relinquishes_run243_heavy_bodies(self):
        source = (ROOT / "pipeline.py").read_text()
        tree = ast.parse(source)
        funcs = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        for moved in ("_source_fact_discipline", "_human_editorial_style_rules", "_promote_plaintext_section_titles"):
            self.assertNotIn(moved, funcs)
        self.assertLessEqual(funcs["_parse_gemini_response"].end_lineno - funcs["_parse_gemini_response"].lineno + 1, 13)
        self.assertLessEqual(funcs["build_monthly_digest_markdown"].end_lineno - funcs["build_monthly_digest_markdown"].lineno + 1, 9)
        self.assertNotIn("【GitHub専用 Fact Discipline】", source)
        self.assertNotIn("【Human Editorial Style｜最重要】", source)
        self.assertLess(len(source.splitlines()), 10900)

    def test_canonical_module_has_no_provider_or_persistence_imports(self):
        source = (ROOT / "content_generation_protocol.py").read_text()
        tree = ast.parse(source)
        imported = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.append(node.module or "")
        forbidden = ("google", "genai", "requests", "notion", "github", "decision_intelligence")
        self.assertFalse(any(any(token in name.lower() for token in forbidden) for name in imported))


if __name__ == "__main__":
    unittest.main()
