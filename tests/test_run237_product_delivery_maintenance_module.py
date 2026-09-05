import ast
import pathlib
import unittest
from datetime import date
from types import SimpleNamespace

import product_delivery_maintenance as maintenance


ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE_PATH = ROOT / "pipeline.py"
MODULE_PATH = ROOT / "product_delivery_maintenance.py"


class _Logger:
    def __init__(self):
        self.info_calls = []
        self.warning_calls = []
        self.error_calls = []

    def info(self, *args):
        self.info_calls.append(args)

    def warning(self, *args):
        self.warning_calls.append(args)

    def error(self, *args):
        self.error_calls.append(args)


class Run237ProductDeliveryMaintenanceModuleTests(unittest.TestCase):
    def test_monthly_digest_targets_preserve_recent_three_completed_periods(self):
        self.assertEqual(
            maintenance.monthly_digest_targets(date(2026, 8, 22)),
            ["2026-07", "2026-06", "2026-05"],
        )

    def test_month_end_appends_current_period_after_completed_periods(self):
        self.assertEqual(
            maintenance.monthly_digest_targets(date(2026, 8, 31)),
            ["2026-07", "2026-06", "2026-05", "2026-08"],
        )

    def test_previous_and_current_month_helpers_preserve_contract(self):
        self.assertEqual(maintenance.previous_month_id(date(2026, 1, 15)), "2025-12")
        self.assertEqual(maintenance.current_month_id(date(2026, 1, 15)), "2026-01")

    def test_disabled_product_delivery_is_side_effect_free(self):
        calls = []
        decision = SimpleNamespace(
            ENABLE_DECISION_INTELLIGENCE_DB=True,
            ENABLE_DECISION_MONTHLY_DIGEST=True,
            sync_subscriber_technology_db=lambda: calls.append("sync"),
            create_history_monthly_digest=lambda period: calls.append(period),
        )
        result = maintenance.run_product_delivery_maintenance(
            enabled=False,
            decision_intelligence=decision,
            logger=_Logger(),
            evidence_health_runner=lambda: calls.append("health"),
            today=date(2026, 8, 22),
            today_factory=lambda: date(2099, 1, 1),
        )
        self.assertEqual(
            result, {"subscriber": None, "monthly": [], "evidence_health": None}
        )
        self.assertEqual(calls, [])

    def test_product_delivery_preserves_order_and_error_isolation(self):
        calls = []
        logger = _Logger()

        def sync():
            calls.append("sync")
            return {"enabled": True, "saved": 2}

        def digest(period):
            calls.append(period)
            if period == "2026-06":
                raise RuntimeError("historical test failure")
            return {"period": period, "created": True, "events": 1}

        decision = SimpleNamespace(
            ENABLE_DECISION_INTELLIGENCE_DB=True,
            ENABLE_DECISION_MONTHLY_DIGEST=True,
            sync_subscriber_technology_db=sync,
            create_history_monthly_digest=digest,
        )
        result = maintenance.run_product_delivery_maintenance(
            enabled=True,
            decision_intelligence=decision,
            logger=logger,
            evidence_health_runner=lambda: calls.append("health") or {"checked": 1},
            today=date(2026, 8, 22),
            today_factory=lambda: date(2099, 1, 1),
        )
        self.assertEqual(calls, ["health", "sync", "2026-07", "2026-06", "2026-05"])
        self.assertEqual(result["evidence_health"], {"checked": 1})
        self.assertEqual(result["subscriber"], {"enabled": True, "saved": 2})
        self.assertEqual(
            [row["period"] for row in result["monthly"]], ["2026-07", "2026-05"]
        )
        self.assertEqual(len(logger.error_calls), 1)

    def test_material_evidence_change_only_accelerates_next_review_and_records_health(self):
        state = {
            "page_id": "ledger-page",
            "tech_page_id": "tech-page",
            "source_type": "github",
            "url": "https://github.com/acme/tool",
        }
        updates = []
        fetch_results = []

        class Ledger:
            ENABLE_EVIDENCE_LEDGER = True

            @staticmethod
            def query_health_candidates(token):
                self.assertEqual(token, "token")
                return [state]

            @staticmethod
            def check_health(candidate, fetcher):
                self.assertIs(candidate, state)
                fetch_results.append(fetcher(candidate["url"]))
                return {"health": "MATERIAL_CHANGE", "material": True}

            @staticmethod
            def update_health(page_id, health, token, rereview_triggered):
                updates.append((page_id, health, token, rereview_triggered))

        patches = []

        class Requests:
            @staticmethod
            def patch(url, **kwargs):
                patches.append((url, kwargs))
                return SimpleNamespace(status_code=200)

        decision = SimpleNamespace(
            NOTION_DECISION_INTELLIGENCE_API_KEY="token",
            TECH_PROP_NEXT_REVIEW="Next Review",
            _headers=lambda: {"Authorization": "Bearer test"},
        )
        result = maintenance.run_evidence_health_maintenance(
            evidence_ledger=Ledger,
            decision_intelligence=decision,
            requests_module=Requests,
            logger=_Logger(),
            github_repo_name_from_url=lambda url: "acme/tool",
            fetch_github_readme_context=lambda repo: "README evidence",
            extract_arxiv_id=lambda url: None,
            fetch_arxiv_api_context=lambda arxiv_id: ("", {}),
            http_get_health_limited=lambda url, limit: (500, "", url),
            readable_html_text_parser=object,
            web_context_max_bytes=2_000_000,
            now_iso=lambda: "2026-09-05T12:00:00+00:00",
        )
        self.assertEqual(fetch_results, [(200, "README evidence", state["url"])])
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["material"], 1)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0][0], "https://api.notion.com/v1/pages/tech-page")
        self.assertEqual(
            patches[0][1]["json"],
            {"properties": {"Next Review": {"date": {"start": "2026-09-05T12:00:00+00:00"}}}},
        )
        self.assertEqual(
            updates,
            [("ledger-page", {"health": "MATERIAL_CHANGE", "material": True}, "token", True)],
        )

    def test_module_has_no_provider_or_gemini_import_surface(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_roots = set()
        runtime_identifiers = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_roots.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_roots.add(node.module.split(".")[0])
            elif isinstance(node, ast.Name):
                runtime_identifiers.add(node.id.lower())
            elif isinstance(node, ast.Attribute):
                runtime_identifiers.add(node.attr.lower())
        self.assertTrue(imported_roots.isdisjoint({"requests", "google", "notion_client"}))
        self.assertFalse(
            any("gemini" in name for name in runtime_identifiers),
            "Run237 module must not bind a Gemini runtime object",
        )

    def test_pipeline_retains_only_thin_compatibility_wrappers(self):
        source = PIPELINE_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source)
        functions = {
            node.name: node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        expected = {
            "_previous_month_id": "_previous_month_id_impl",
            "_current_month_id": "_current_month_id_impl",
            "run_evidence_health_maintenance": "_run_evidence_health_maintenance_impl",
            "run_product_delivery_maintenance": "_run_product_delivery_maintenance_impl",
        }
        for name, callee in expected.items():
            self.assertIn(name, functions)
            node = functions[name]
            self.assertFalse(
                any(isinstance(child, (ast.For, ast.While, ast.Try)) for child in ast.walk(node)),
                f"{name} must not regain orchestration logic",
            )
            returns = [child for child in ast.walk(node) if isinstance(child, ast.Return)]
            self.assertEqual(len(returns), 1, name)
            self.assertIsInstance(returns[0].value, ast.Call, name)
            call = returns[0].value
            self.assertIsInstance(call.func, ast.Name, name)
            self.assertEqual(call.func.id, callee, name)

        aliases = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "product_delivery_maintenance":
                for alias in node.names:
                    aliases[alias.name] = alias.asname
        self.assertEqual(aliases.get("previous_month_id"), "_previous_month_id_impl")
        self.assertEqual(aliases.get("current_month_id"), "_current_month_id_impl")
        self.assertEqual(
            aliases.get("run_evidence_health_maintenance"),
            "_run_evidence_health_maintenance_impl",
        )
        self.assertEqual(
            aliases.get("run_product_delivery_maintenance"),
            "_run_product_delivery_maintenance_impl",
        )


if __name__ == "__main__":
    unittest.main()
