import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

import deferred_queue_policy as dq
import notion_payloads as np
import source_document_parsing as sd


ROOT = Path(__file__).resolve().parents[1]


class Run242ModuleTests(unittest.TestCase):
    def test_modules_have_no_provider_network_or_persistence_imports(self):
        forbidden = {"requests", "google", "google.genai", "notion_client"}
        for filename in ("notion_payloads.py", "source_document_parsing.py", "deferred_queue_policy.py"):
            tree = ast.parse((ROOT / filename).read_text())
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.add(node.module or "")
            self.assertFalse(any(name in forbidden or name.startswith("google") for name in imports), filename)
            source = (ROOT / filename).read_text()
            self.assertNotIn("requests.", source)
            self.assertNotIn("open(", source)

    def test_safe_chunk_text_preserves_paragraph_and_sentence_boundaries(self):
        self.assertEqual(np.safe_chunk_text("", 10), [])
        self.assertEqual(np.safe_chunk_text("abc\ndef", 10), ["abc\ndef"])
        chunks = np.safe_chunk_text("あいうえお。かきくけこ。", 6)
        self.assertEqual(chunks, ["あいうえお。", "かきくけこ。"])
        self.assertTrue(all(len(chunk) <= 6 for chunk in chunks))

    def test_notion_date_property_is_fail_safe(self):
        self.assertEqual(np.notion_date_property(""), {"date": None})
        self.assertEqual(np.notion_date_property("2026-09-05T00:00:00+09:00"), {"date": {"start": "2026-09-05T00:00:00+09:00"}})

    def test_metadata_notion_properties_preserve_stock_contract(self):
        cfg = {
            "PROP_NAME": "Name", "PROP_URL": "URL", "PROP_SOURCE": "Source", "PROP_ENGAGEMENT": "Engagement",
            "PROP_SCORE": "Decision Score", "PROP_STATUS": "Status", "STATUS_STOCKED": "Stocked",
            "PROP_CONTENT_STATUS": "Content Status", "CONTENT_STATUS_STOCKED": "Stocked",
            "PROP_ARTICLE_STATUS": "Article Status", "ARTICLE_STATUS_NOT_PLANNED": "Not Planned",
            "PROP_SUBSCRIPTION_VISIBILITY": "Subscription Visibility", "VISIBILITY_SUBSCRIBER_ONLY": "Subscriber Only",
            "PROP_SCREENING_SCORE": "Screening Score", "PROP_SCREENING_REASON": "Screening Reason",
            "PROP_SOURCE_SUMMARY": "Source Summary", "PROP_GROUNDING_STATUS": "Grounding Status",
            "GROUNDING_METADATA_ONLY": "Metadata Only", "PROP_SCORE_BREAKDOWN": "Score Breakdown",
            "PROP_PUBLISHED_AT": "Published At", "PROP_ANALYZED_AT": "Analyzed At", "PROP_LICENSE": "License",
        }
        props = np.build_metadata_notion_properties(
            "o/r", "https://github.com/o/r", 63, "x" * 2500, source_summary="summary", spdx_id="MIT", config=cfg,
        )
        self.assertEqual(props["Status"]["select"]["name"], "Stocked")
        self.assertEqual(props["Content Status"]["select"]["name"], "Stocked")
        self.assertEqual(props["Article Status"]["select"]["name"], "Not Planned")
        self.assertEqual(props["Subscription Visibility"]["select"]["name"], "Subscriber Only")
        self.assertEqual(len(props["Screening Reason"]["rich_text"][0]["text"]["content"]), 2000)
        self.assertEqual(props["License"]["rich_text"][0]["text"]["content"], "MIT")

    def test_manuscript_children_preserve_single_code_block_shape(self):
        children = np.build_notion_manuscript_children("abc", "ready", chunker=lambda text: [text])
        self.assertEqual(len(children), 1)
        block = children[0]
        self.assertEqual(block["type"], "code")
        self.assertEqual(block["code"]["language"], "markdown")
        self.assertEqual(block["code"]["caption"][0]["text"]["content"], "ready")

    def test_github_identity_and_global_navigation_are_conservative(self):
        self.assertEqual(sd.github_repo_name_from_url("https://github.com/openai/openai/issues/1"), "openai/openai")
        self.assertEqual(sd.github_repo_name_from_url("https://github.com/features/copilot"), "")
        self.assertTrue(sd.is_github_global_navigation_url("https://github.com/customer-stories/example"))
        self.assertFalse(sd.is_github_global_navigation_url("https://github.com/openai/openai"))
        repo = {"canonicalEntityId": "github:o/r", "url": "https://example.com"}
        self.assertEqual(sd.github_repo_identity(repo, repo_name_from_url=sd.github_repo_name_from_url), "o/r")

    def test_markdown_evidence_link_filter_rejects_badges_social_and_navigation(self):
        text = "\n".join([
            "[Docs](https://example.com/docs)",
            "![Badge](https://img.shields.io/x)",
            "[GitHub pricing](https://github.com/pricing)",
            "[Twitter](https://twitter.com/x)",
        ])
        links = sd.extract_markdown_evidence_links(text, is_global_navigation_url=sd.is_github_global_navigation_url)
        self.assertEqual(links, [("https://example.com/docs", "Docs")])

    def test_research_link_parser_does_not_treat_arxiv_host_alone_as_evidence(self):
        parser = sd.ResearchLinkParser("https://arxiv.org/abs/1234.5678")
        parser.feed('<a href="https://arxiv.org/help">Help</a><a href="/pdf/1234.5678">PDF</a>')
        self.assertEqual(parser.links, [("https://arxiv.org/pdf/1234.5678", "PDF")])

    def test_html_parser_removes_navigation_and_repeated_lines(self):
        parser = sd.ReadableHTMLTextParser()
        parser.feed("<nav>menu</nav><main><p>Hello world</p><p>Hello world</p><p>Evidence</p></main>")
        self.assertEqual(parser.text().splitlines(), ["Hello world", "Evidence"])

    def test_evidence_metadata_uses_word_boundaries(self):
        metadata = sd.build_evidence_metadata("rapid capital latest", False)
        self.assertNotEqual(metadata["coverage"]["method"], "FOUND")
        self.assertNotEqual(metadata["coverage"]["benchmark"], "FOUND")
        positive = sd.build_evidence_metadata("API test limitation 120 ms", True)
        self.assertEqual(positive["coverage"]["method"], "FOUND")
        self.assertEqual(positive["coverage"]["benchmark"], "FOUND")
        self.assertEqual(positive["coverage"]["limitations"], "FOUND")
        self.assertIn("120 ms", positive["numeric_claims"])

    def test_deferred_ttl_identity_and_serialization_contract(self):
        ttl = lambda shelf: dq.deferred_ttl_days(shelf, flash_ttl_days=1, trend_ttl_days=3, evergreen_ttl_days=30)
        self.assertEqual(ttl("FLASH"), 1)
        self.assertEqual(ttl("unknown"), 3)
        candidate = {"repo": {"source": "GitHub", "nameWithOwner": "o/r", "url": "https://github.com/o/r"}, "score": 80, "shelf_life": "EVERGREEN"}
        key = lambda c: dq.deferred_key(c, candidate_identity_urls=lambda _r: {"https://github.com/o/r"}, normalize_title_for_match=str.lower)
        now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        row = dq.deferred_serializable(candidate, ttl_days=ttl, key_for_candidate=key, now=now)
        self.assertEqual(row["key"], "https://github.com/o/r")
        self.assertEqual(row["expires_at"], (now + timedelta(days=30)).isoformat())
        self.assertEqual(row["portfolio_topic"], "OTHER")

    def test_deferred_validation_ranking_and_overflow_are_deterministic(self):
        now = datetime(2026, 9, 5, tzinfo=timezone.utc)
        payload = {"items": [
            {"key": "old", "repo": {}, "expires_at": (now - timedelta(seconds=1)).isoformat()},
            {"key": "live", "repo": {}, "expires_at": (now + timedelta(days=1)).isoformat()},
        ]}
        self.assertEqual([r["key"] for r in dq.valid_deferred_items(payload, max_queue=10, now=now)], ["live"])
        queue = [{"key": "a", "score": 50, "deferred_at": "2026-09-01"}]
        candidates = [{"key": "b", "score": 80}, {"key": "c", "score": 70}]
        new_rows, final, evicted, ranked = dq.merge_rank_deferred_candidates(
            queue, candidates, serialize_candidate=lambda c: {**c, "deferred_at": "2026-09-05"}, max_queue=2,
        )
        self.assertEqual(len(new_rows), 2)
        self.assertEqual([r["key"] for r in final], ["b", "c"])
        self.assertEqual([r["key"] for r in evicted], ["a"])
        self.assertEqual([r["key"] for r in ranked], ["b", "c", "a"])


if __name__ == "__main__":
    unittest.main()
