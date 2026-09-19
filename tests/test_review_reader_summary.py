"""Exercise current review-manuscript projection without loading providers or writing Notion."""
import ast
from pathlib import Path
import unittest

import note_manuscript as manuscript
import run296_editorial_format_v2 as format_v2


class ReviewSummaryTests(unittest.TestCase):
    def render_review(self):
        tree = ast.parse(Path("pipeline.py").read_text(encoding="utf-8"))
        assignment = next(node for node in ast.walk(tree)
                          if isinstance(node, ast.Assign) and any(
                              isinstance(target, ast.Name) and target.id == "review_manuscript"
                              for target in node.targets))
        body = "## 詳細\n\n既存の本文と制約を保持します。"
        summary = {"what": "新しい仕組みが公開された。",
                   "why": "運用時の権限設計に影響する。",
                   "decision": "まず通信範囲を点検する。"}

        def build(*args, **kwargs):
            return format_v2.normalize_article_format_v2(
                manuscript.build_clean_note_manuscript(
                    *args, **kwargs, split_free_paid=lambda draft, name: (draft, ""),
                    display_heading_aliases=lambda key: [], subscription_enabled=False,
                    subscription_landing_url="", subscription_campaign_id=""))

        context = dict(parsed={"note_draft": body, "title_text": "テスト記事"},
                       name="Source", manuscript_primary_url="https://example.org/source",
                       spdx_id="N/A", source="HackerNews", review_evidence_urls=[],
                       discovery_url="", published_at=None,
                       build_reader_first_summary=lambda parsed: summary,
                       build_clean_note_manuscript=build)
        exec(compile(ast.Module(body=[assignment], type_ignores=[]), "pipeline.py", "exec"), context)
        return context["review_manuscript"], body, summary

    def test_review_projection_keeps_narrative_body_before_summary_and_source_footer(self):
        text, body, summary = self.render_review()
        self.assertIn(body, text)
        positions = [text.index(value) for value in summary.values()]
        self.assertEqual(positions, sorted(positions))
        self.assertLess(text.index(body), positions[0])
        self.assertLess(positions[-1], text.index("### Sources / Evidence"))
        self.assertNotIn("### 元情報", text)
        for value in summary.values():
            self.assertEqual(text.count(value), 1)


if __name__ == "__main__":
    unittest.main()
