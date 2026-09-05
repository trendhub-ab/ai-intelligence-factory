from __future__ import annotations

import unittest
from unittest.mock import patch

import deep_dive_portfolio as portfolio
import pipeline


class Run238DeepDivePortfolioIntegrationTests(unittest.TestCase):
    def test_pipeline_delegate_aliases_are_exact_module_functions(self):
        self.assertIs(pipeline._topic_counts_impl, portfolio.topic_counts)
        self.assertIs(
            pipeline._apply_content_portfolio_balance_impl,
            portfolio.apply_content_portfolio_balance,
        )
        self.assertIs(
            pipeline._publication_probability_score_impl,
            portfolio.publication_probability_score,
        )
        self.assertIs(
            pipeline._apply_publication_reliability_slot_impl,
            portfolio.apply_publication_reliability_slot,
        )
        self.assertIs(
            pipeline._select_stocked_deep_dive_candidates_impl,
            portfolio.select_stocked_deep_dive_candidates,
        )

    def test_topic_count_wrapper_reads_live_normalizer(self):
        with patch.object(
            pipeline,
            "normalize_portfolio_topic",
            side_effect=lambda value: "MODEL" if value == "x" else "OTHER",
        ):
            result = pipeline._topic_counts(
                [{"portfolio_topic": "x"}, {"portfolio_topic": "x"}, {"portfolio_topic": "y"}]
            )
        self.assertEqual(result, {"MODEL": 2})

    def test_balance_wrapper_reads_live_enable_and_tolerance(self):
        ordered = [
            {"portfolio_topic": "AGENT", "deep_dive_priority_score": 96, "shelf_life": "TREND"},
            {"portfolio_topic": "AGENT", "deep_dive_priority_score": 94, "shelf_life": "TREND"},
            {"portfolio_topic": "MODEL", "deep_dive_priority_score": 90, "shelf_life": "TREND"},
        ]
        with patch.object(pipeline, "ENABLE_PORTFOLIO_BALANCE", False):
            self.assertIs(pipeline._apply_content_portfolio_balance(ordered, 2), ordered)

        with (
            patch.object(pipeline, "ENABLE_PORTFOLIO_BALANCE", True),
            patch.object(pipeline, "PORTFOLIO_MIN_DISTINCT_TOPICS", 2),
            patch.object(pipeline, "PORTFOLIO_TOPIC_PRIORITY_TOLERANCE", 8),
            patch.object(pipeline, "EVERGREEN_PORTFOLIO_MIN", 0),
            patch.object(pipeline, "normalize_portfolio_topic", side_effect=lambda value: str(value or "OTHER")),
        ):
            result = pipeline._apply_content_portfolio_balance(ordered, 2)
        self.assertEqual([x["portfolio_topic"] for x in result[:2]], ["AGENT", "MODEL"])

    def test_publication_probability_wrapper_preserves_exact_module_behavior(self):
        item = {
            "repo": {
                "source": "GitHub",
                "primaryUrl": "https://github.com/acme/tool",
                "description": "x" * 180,
                "publishedAt": "2026-09-01",
                "licenseInfo": {"spdxId": "MIT"},
            }
        }
        self.assertEqual(
            pipeline.publication_probability_score(item),
            portfolio.publication_probability_score(item),
        )

    def test_reliability_wrapper_reads_live_disable_flag(self):
        ordered = [{"score": 90, "repo": {"source": "GitHub"}}]
        with patch.object(pipeline, "ENABLE_PUBLICATION_RELIABILITY_SLOT", False):
            self.assertIs(pipeline._apply_publication_reliability_slot(ordered, 1), ordered)

    def test_stock_selection_wrapper_binds_live_threshold_and_callbacks(self):
        screened = [
            {"id": "keep", "score": 80, "notion_page_id": "p1", "repo": {"stargazerCount": 1}},
            {"id": "drop", "score": 70, "notion_page_id": "p2", "repo": {"stargazerCount": 99}},
        ]
        calls = []

        def balance(ordered, visible_slots):
            calls.append(("balance", visible_slots, [x["id"] for x in ordered]))
            return ordered

        def reliability(ordered, visible_slots):
            calls.append(("reliability", visible_slots, [x["id"] for x in ordered]))
            return ordered

        with (
            patch.object(pipeline, "NOTION_SAVE_THRESHOLD_SCORE", 75),
            patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", True),
            patch.object(pipeline, "PROFIT_SCORE_NEUTRAL", 50),
            patch.object(pipeline, "TOP_N_FOR_DEEP_DIVE", 3),
            patch.object(pipeline, "EVERGREEN_PORTFOLIO_MIN", 0),
            patch.object(pipeline, "EVERGREEN_PRIORITY_TOLERANCE", 0),
            patch.object(pipeline, "_attach_profit_metadata", side_effect=lambda item, *_: item.setdefault("deep_dive_priority_score", item["score"])),
            patch.object(pipeline, "_attach_portfolio_topic", side_effect=lambda item, *_: item.setdefault("portfolio_topic", "OTHER")),
            patch.object(pipeline, "_apply_content_portfolio_balance", side_effect=balance),
            patch.object(pipeline, "_apply_publication_reliability_slot", side_effect=reliability),
        ):
            result = pipeline._select_stocked_deep_dive_candidates(screened)

        self.assertEqual([x["id"] for x in result], ["keep"])
        self.assertEqual(calls, [("balance", 1, ["keep"]), ("reliability", 1, ["keep"])])


if __name__ == "__main__":
    unittest.main()
