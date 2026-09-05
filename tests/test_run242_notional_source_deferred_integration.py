import ast
import os
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", "0")

import deferred_queue_policy as dq
import notion_payloads as np
import source_document_parsing as sd
import pipeline


class Run242IntegrationTests(unittest.TestCase):
    def test_direct_delegate_aliases_are_canonical(self):
        self.assertIs(pipeline._notion_date_property, np.notion_date_property)
        self.assertIs(pipeline._github_repo_name_from_url, sd.github_repo_name_from_url)
        self.assertIs(pipeline._is_github_global_navigation_url, sd.is_github_global_navigation_url)
        self.assertIs(pipeline._ReadableHTMLTextParser, sd.ReadableHTMLTextParser)
        self.assertIs(pipeline._ResearchLinkParser, sd.ResearchLinkParser)
        self.assertIs(pipeline._build_evidence_metadata, sd.build_evidence_metadata)

    def test_notion_properties_wrapper_reads_live_pipeline_names_and_status(self):
        with patch.object(pipeline, "PROP_STATUS", "Status Live"), patch.object(pipeline, "STATUS_DEEP_DIVE", "Deep Live"):
            props = pipeline.build_notion_properties(
                "o/r", "https://github.com/o/r", 70, "breakdown", "what", "why", "why not", "action", "MIT"
            )
        self.assertEqual(props["Status Live"]["select"]["name"], "Deep Live")

    def test_notion_payload_uses_live_parent_and_pipeline_builders(self):
        with patch.object(pipeline, "_notion_parent", return_value={"data_source_id": "live"}) as parent:
            payload = pipeline.build_notion_payload(
                "o/r", "https://github.com/o/r", 70, "breakdown", "what", "why", "why not", "action", "MIT", "article"
            )
        parent.assert_called_once_with()
        self.assertEqual(payload["parent"], {"data_source_id": "live"})
        self.assertEqual(payload["children"][0]["type"], "code")

    def test_source_identity_wrapper_reads_live_repo_parser(self):
        with patch.object(pipeline, "_github_repo_name_from_url", return_value="patched/repo"):
            self.assertEqual(pipeline._github_repo_identity({"url": "https://example.com/x"}), "patched/repo")

    def test_effective_evidence_source_reads_live_arxiv_parser(self):
        repo = {"source": "HackerNews", "url": "https://example.com/paper"}
        with patch.object(pipeline, "_extract_arxiv_id", return_value="2609.00001"):
            self.assertEqual(pipeline._effective_evidence_source(repo), "ArXiv")

    def test_markdown_link_wrapper_reads_live_navigation_filter(self):
        text = "[Docs](https://example.com/docs)"
        with patch.object(pipeline, "_is_github_global_navigation_url", return_value=True):
            self.assertEqual(pipeline._extract_markdown_evidence_links(text), [])

    def test_compress_evidence_reads_live_truncation_callback(self):
        with patch.object(pipeline, "_truncate_source_context", side_effect=lambda text: "LIVE:" + text[:5]):
            self.assertTrue(pipeline._compress_evidence("abstract hello").startswith("LIVE:"))

    def test_deferred_wrappers_read_live_ttl_and_identity_dependencies(self):
        with patch.object(pipeline, "DEFERRED_FLASH_TTL_DAYS", 9):
            self.assertEqual(pipeline._deferred_ttl_days("FLASH"), 9)
        with patch.object(pipeline, "candidate_identity_urls", return_value={"https://example.com/live"}):
            self.assertEqual(pipeline._deferred_key({"repo": {"source": "X", "nameWithOwner": "n"}}), "https://example.com/live")

    def test_pipeline_physically_relinquishes_heavy_run242_bodies(self):
        source = (ROOT / "pipeline.py").read_text()
        tree = ast.parse(source)
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertLessEqual(functions["build_notion_properties"].end_lineno - functions["build_notion_properties"].lineno + 1, 18)
        self.assertLessEqual(functions["_build_evidence_metadata"].end_lineno - functions["_build_evidence_metadata"].lineno + 1, 1)
        self.assertNotIn("_ReadableHTMLTextParser", classes)
        self.assertNotIn("_ResearchLinkParser", classes)
        self.assertLess(len(source.splitlines()), 11200)

    def test_deferred_queue_orchestration_preserves_persistence_fail_safe(self):
        candidate = {"repo": {"source": "GitHub", "nameWithOwner": "o/r", "url": "https://github.com/o/r"}, "notion_page_id": "p1", "score": 80, "shelf_life": "EVERGREEN"}
        with patch.object(pipeline, "load_deferred_deep_dive_queue", return_value=[]), \
             patch.object(pipeline, "save_deferred_deep_dive_queue", return_value=False), \
             patch.object(pipeline, "_fallback_deferred_rows_to_notion", return_value=1) as fallback:
            self.assertEqual(pipeline.enqueue_deferred_candidates([candidate]), 0)
            fallback.assert_called_once()
            self.assertEqual(fallback.call_args.args[1], "Deferred queue persistence failed")


if __name__ == "__main__":
    unittest.main()
