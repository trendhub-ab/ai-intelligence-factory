from __future__ import annotations

import ast
import pathlib
import unittest

import deep_dive_portfolio as portfolio


ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "pipeline.py"
MODULE_PATH = ROOT / "deep_dive_portfolio.py"


def _normalize(value):
    value = str(value or "OTHER").upper()
    return value if value in {"AGENT", "MODEL", "INFRA", "SECURITY", "OTHER"} else "OTHER"


class _Logger:
    def __init__(self):
        self.info_calls = []

    def info(self, *args):
        self.info_calls.append(args)


class Run238DeepDivePortfolioModuleTests(unittest.TestCase):
    def test_module_is_stdlib_only_and_has_no_provider_runtime_surface(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
            elif isinstance(node, ast.Name):
                names.add(node.id.lower())
        self.assertTrue(imported.issubset({"__future__", "typing", "urllib"}))
        self.assertTrue(names.isdisjoint({"requests", "genai", "notion_client"}))

    def test_publication_probability_score_preserves_historical_boundaries(self):
        strong = {
            "repo": {
                "source": "GitHub",
                "primaryUrl": "https://github.com/acme/tool",
                "description": "x" * 180,
                "publishedAt": "2026-09-01T00:00:00Z",
                "licenseInfo": {"spdxId": "MIT"},
            }
        }
        self.assertEqual(portfolio.publication_probability_score(strong), 98)
        arxiv = {
            "repo": {
                "source": "ArXiv",
                "primaryUrl": "https://arxiv.org/abs/2609.00001",
                "description": "paper",
            }
        }
        self.assertEqual(portfolio.publication_probability_score(arxiv), 92)

    def test_balance_never_promotes_materially_weaker_candidate(self):
        ordered = [
            {"portfolio_topic": "AGENT", "deep_dive_priority_score": 96, "shelf_life": "TREND"},
            {"portfolio_topic": "AGENT", "deep_dive_priority_score": 94, "shelf_life": "TREND"},
            {"portfolio_topic": "MODEL", "deep_dive_priority_score": 70, "shelf_life": "TREND"},
        ]
        result = portfolio.apply_content_portfolio_balance(
            ordered,
            2,
            enabled=True,
            min_distinct_topics=2,
            priority_tolerance=8,
            evergreen_portfolio_min=0,
            normalize_portfolio_topic=_normalize,
        )
        self.assertEqual([x["deep_dive_priority_score"] for x in result[:2]], [96, 94])

    def test_balance_promotes_near_peer_and_other_fails_safe(self):
        ordered = [
            {"portfolio_topic": "AGENT", "deep_dive_priority_score": 96, "shelf_life": "TREND"},
            {"portfolio_topic": "AGENT", "deep_dive_priority_score": 94, "shelf_life": "TREND"},
            {"portfolio_topic": "MODEL", "deep_dive_priority_score": 90, "shelf_life": "TREND"},
        ]
        result = portfolio.apply_content_portfolio_balance(
            ordered,
            2,
            enabled=True,
            min_distinct_topics=2,
            priority_tolerance=8,
            evergreen_portfolio_min=0,
            normalize_portfolio_topic=_normalize,
        )
        self.assertEqual([x["portfolio_topic"] for x in result[:2]], ["AGENT", "MODEL"])

        unknown = [
            {"portfolio_topic": "OTHER", "deep_dive_priority_score": 96},
            {"portfolio_topic": "AGENT", "deep_dive_priority_score": 94},
            {"portfolio_topic": "MODEL", "deep_dive_priority_score": 93},
        ]
        fail_safe = portfolio.apply_content_portfolio_balance(
            unknown,
            2,
            enabled=True,
            min_distinct_topics=2,
            priority_tolerance=8,
            evergreen_portfolio_min=0,
            normalize_portfolio_topic=_normalize,
        )
        self.assertEqual(fail_safe, unknown)

    def test_reliability_slot_preserves_threshold_and_advantage_contract(self):
        logger = _Logger()
        ordered = [
            {
                "score": 90,
                "deep_dive_priority_score": 99,
                "repo": {"source": "ProductHunt", "primaryUrl": "https://producthunt.com/posts/a"},
            },
            {
                "score": 88,
                "deep_dive_priority_score": 98,
                "repo": {"source": "HackerNews", "primaryUrl": "https://news.ycombinator.com/item?id=1"},
            },
            {
                "score": 87,
                "deep_dive_priority_score": 90,
                "repo": {
                    "source": "GitHub",
                    "primaryUrl": "https://github.com/acme/tool",
                    "description": "x" * 180,
                    "publishedAt": "2026-09-01",
                    "licenseInfo": {"spdxId": "MIT"},
                    "nameWithOwner": "acme/tool",
                },
            },
        ]
        result = portfolio.apply_publication_reliability_slot(
            ordered,
            2,
            enabled=True,
            reliability_slots=1,
            min_decision_score=60,
            min_advantage=5,
            logger=logger,
        )
        self.assertEqual(result[1]["repo"].get("nameWithOwner"), "acme/tool")
        self.assertEqual(len(logger.info_calls), 1)

    def test_stock_selection_filters_unpersisted_and_preserves_non_profit_sort(self):
        calls = []

        def attach_profit(item, commercial, shelf):
            calls.append(("profit", item["id"]))

        def attach_topic(item, topic, raw):
            calls.append(("topic", item["id"]))

        screened = [
            {"id": "a", "score": 80, "notion_page_id": "p-a", "repo": {"stargazerCount": 1}},
            {"id": "b", "score": 80, "notion_page_id": "p-b", "repo": {"stargazerCount": 5}},
            {"id": "c", "score": 99, "notion_page_id": None, "repo": {"stargazerCount": 99}},
            {"id": "d", "score": 59, "notion_page_id": "p-d", "repo": {"stargazerCount": 99}},
        ]
        result = portfolio.select_stocked_deep_dive_candidates(
            screened,
            notion_save_threshold_score=60,
            attach_profit_metadata=attach_profit,
            attach_portfolio_topic=attach_topic,
            enable_profit_priority=False,
            profit_score_neutral=50,
            top_n_for_deep_dive=3,
            evergreen_portfolio_min=0,
            evergreen_priority_tolerance=0,
            apply_content_portfolio_balance_fn=lambda ordered, slots: ordered,
            apply_publication_reliability_slot_fn=lambda ordered, slots: ordered,
        )
        self.assertEqual([x["id"] for x in result], ["b", "a"])
        self.assertEqual(calls, [("profit", "a"), ("topic", "a"), ("profit", "b"), ("topic", "b")])

    def test_pipeline_owns_only_live_binding_wrappers(self):
        source = PIPELINE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        expected = {
            "_topic_counts": "_topic_counts_impl",
            "_apply_content_portfolio_balance": "_apply_content_portfolio_balance_impl",
            "publication_probability_score": "_publication_probability_score_impl",
            "_apply_publication_reliability_slot": "_apply_publication_reliability_slot_impl",
            "_select_stocked_deep_dive_candidates": "_select_stocked_deep_dive_candidates_impl",
        }
        for name, callee in expected.items():
            self.assertIn(name, functions)
            node = functions[name]
            self.assertFalse(any(isinstance(child, (ast.For, ast.While, ast.Try)) for child in ast.walk(node)))
            calls = [child for child in ast.walk(node) if isinstance(child, ast.Call)]
            self.assertTrue(
                any(isinstance(call.func, ast.Name) and call.func.id == callee for call in calls),
                name,
            )

        aliases = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "deep_dive_portfolio":
                for alias in node.names:
                    aliases[alias.name] = alias.asname
        self.assertEqual(aliases.get("topic_counts"), "_topic_counts_impl")
        self.assertEqual(aliases.get("apply_content_portfolio_balance"), "_apply_content_portfolio_balance_impl")
        self.assertEqual(aliases.get("publication_probability_score"), "_publication_probability_score_impl")
        self.assertEqual(aliases.get("apply_publication_reliability_slot"), "_apply_publication_reliability_slot_impl")
        self.assertEqual(aliases.get("select_stocked_deep_dive_candidates"), "_select_stocked_deep_dive_candidates_impl")


if __name__ == "__main__":
    unittest.main()
