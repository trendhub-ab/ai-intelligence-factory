from __future__ import annotations

import unittest

from fact_validation_signals import _numeric_condition_compatible
from run283_numeric_evidence_equivalence import filter_numeric_false_positives
from source_document_parsing import ReadableHTMLTextParser


class Run365ArticleFooterEvidenceTests(unittest.TestCase):
    def _parse(self, html: str) -> str:
        parser = ReadableHTMLTextParser()
        parser.feed(html)
        parser.close()
        return parser.text()

    def test_article_footer_is_preserved_but_global_footer_is_still_skipped(self):
        text = self._parse(
            """
            <html><body>
              <article>
                <p>Gemini 3.8 Flash is available at the same introductory price as 3.7 Flash.</p>
                <footer>
                  <p>Introductory price expires on December 31, 2026.</p>
                  <p>Starting January 1, 2027, $1.50/1M input tokens and $7.50/1M output tokens will apply.</p>
                </footer>
              </article>
              <footer>
                <p>Global navigation privacy 999 dollars.</p>
              </footer>
            </body></html>
            """
        )
        self.assertIn("Starting January 1, 2027, $1.50/1M input tokens", text)
        self.assertIn("$7.50/1M output tokens", text)
        self.assertNotIn("Global navigation privacy", text)
        self.assertNotIn("999 dollars", text)

    def test_preserved_article_footer_reaches_existing_currency_equivalence(self):
        source = self._parse(
            """
            <article>
              <p>Gemini 3.8 Flash is available at the same introductory price as 3.7 Flash at $0.75 per million input tokens.</p>
              <footer>
                <p>Introductory price expires on December 31, 2026.</p>
                <p>Starting January 1, 2027, $1.50/1M input tokens and $7.50/1M output tokens will apply.</p>
              </footer>
            </article>
            """
        )
        failures = ["unsupported numeric claim: 1.50ドル"]
        draft = "2027年1月1日から、入力100万トークンあたり1.50ドルになります。"
        self.assertEqual(
            [],
            filter_numeric_false_positives(
                failures,
                draft,
                source,
                condition_compatible=_numeric_condition_compatible,
            ),
        )

    def test_unrelated_global_footer_amount_cannot_ground_article_claim(self):
        source = self._parse(
            """
            <article><p>The documented introductory input price is $0.75 per million tokens.</p></article>
            <footer><p>Unrelated site promotion: $1.50.</p></footer>
            """
        )
        failures = ["unsupported numeric claim: 1.50ドル"]
        draft = "入力100万トークンあたり1.50ドルです。"
        self.assertEqual(
            failures,
            filter_numeric_false_positives(
                failures,
                draft,
                source,
                condition_compatible=_numeric_condition_compatible,
            ),
        )


if __name__ == "__main__":
    unittest.main()
