from __future__ import annotations

import json
import unittest
from pathlib import Path

from fact_validation_signals import _numeric_condition_compatible
from run283_numeric_evidence_equivalence import filter_numeric_false_positives
from source_document_parsing import ReadableHTMLTextParser


FIXTURE = Path(__file__).parent / "fixtures" / "run55_artifact_zero_api_snapshot.json"


class Run366Run55ArtifactZeroApiRevalidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def _parse(self, html: str) -> str:
        parser = ReadableHTMLTextParser()
        parser.feed(html)
        parser.close()
        return parser.text()

    def test_artifact_usage_audit_proves_one_provider_visible_article_send(self):
        usage = self.snapshot["usage_audit"]
        self.assertEqual(1, usage["attempts"])
        self.assertEqual(1, usage["success"])
        self.assertEqual(0, usage["error"])
        self.assertEqual(16388, usage["total_tokens"])
        self.assertEqual(
            [
                {
                    "model": "gemini-3.8-flash",
                    "kind": "deep_dive",
                    "outcome": "success",
                }
            ],
            usage["records"],
        )

        models = {row["model"].lower() for row in usage["records"]}
        kinds = {row["kind"].lower() for row in usage["records"]}
        self.assertFalse(any("gemini-3.6" in model for model in models))
        self.assertNotIn("quality_retry", kinds)
        self.assertNotIn("eyecatch_layout", kinds)

    def test_artifact_outcome_is_quality_acceptance_not_ready_persistence(self):
        scope = self.snapshot["replay_scope"]
        self.assertFalse(scope["persist_results"])
        self.assertEqual("accepted", scope["quality_outcome"])
        self.assertFalse(scope["ready_persisted"])

    def test_artifact_cannot_claim_byte_exact_replay_of_missing_pre_rescue_state(self):
        scope = self.snapshot["replay_scope"]
        self.assertFalse(scope["artifact_contains_pre_rescue_manuscript"])
        self.assertFalse(scope["artifact_contains_original_primary_source_html"])
        self.assertFalse(scope["exact_historical_byte_replay_possible"])
        self.assertTrue(scope["deterministic_regression_required_for_removed_1_50_claim"])

    def test_run55_removed_future_price_claim_is_supported_by_current_main_logic(self):
        source = self._parse(
            """
            <html><body>
              <article>
                <p>Gemini 3.8 Flash is available at the same introductory price as 3.7 Flash.</p>
                <footer>
                  <p>Introductory price expires on December 31, 2026.</p>
                  <p>Starting January 1, 2027, $1.50/1M input tokens and $7.50/1M output tokens will apply.</p>
                </footer>
              </article>
              <footer><p>Unrelated global promotion: $99.00.</p></footer>
            </body></html>
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

    def test_run55_currency_equivalence_stays_fail_closed(self):
        failures = ["unsupported numeric claim: 1.50ドル"]
        draft = "2027年1月1日から、入力100万トークンあたり1.50ドルになります。"

        bare_number_only = self._parse(
            """
            <article>
              <p>Starting January 1, 2027, the input figure is 1.50 per million tokens.</p>
            </article>
            """
        )
        self.assertEqual(
            failures,
            filter_numeric_false_positives(
                failures,
                draft,
                bare_number_only,
                condition_compatible=_numeric_condition_compatible,
            ),
        )

        wrong_amount = self._parse(
            """
            <article>
              <footer><p>Starting January 1, 2027, $1.55/1M input tokens will apply.</p></footer>
            </article>
            """
        )
        self.assertEqual(
            failures,
            filter_numeric_false_positives(
                failures,
                draft,
                wrong_amount,
                condition_compatible=_numeric_condition_compatible,
            ),
        )

        global_footer_only = self._parse(
            """
            <article><p>The article body does not state the future price.</p></article>
            <footer><p>Starting January 1, 2027, $1.50/1M input tokens will apply.</p></footer>
            """
        )
        self.assertEqual(
            failures,
            filter_numeric_false_positives(
                failures,
                draft,
                global_footer_only,
                condition_compatible=_numeric_condition_compatible,
            ),
        )


if __name__ == "__main__":
    unittest.main()
