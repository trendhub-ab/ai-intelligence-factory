import unittest
from datetime import date
from types import SimpleNamespace
from unittest import mock

import pipeline
import product_delivery_maintenance as maintenance


class Run237ProductDeliveryMaintenanceIntegrationTests(unittest.TestCase):
    def test_pipeline_helper_wrappers_delegate_to_canonical_module(self):
        self.assertEqual(pipeline._previous_month_id(date(2026, 1, 15)), "2025-12")
        self.assertEqual(pipeline._current_month_id(date(2026, 1, 15)), "2026-01")

    def test_product_delivery_wrapper_reads_live_pipeline_enable_flag(self):
        periods = []
        with mock.patch.object(pipeline, "ENABLE_REVENUE_PRODUCT_PHASE2", True), \
             mock.patch.object(pipeline.decision_intelligence, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             mock.patch.object(pipeline.decision_intelligence, "ENABLE_DECISION_MONTHLY_DIGEST", True), \
             mock.patch.object(pipeline, "run_evidence_health_maintenance", return_value={"checked": 4}) as health, \
             mock.patch.object(
                 pipeline.decision_intelligence,
                 "sync_subscriber_technology_db",
                 return_value={"enabled": True, "saved": 3},
             ) as sync, \
             mock.patch.object(
                 pipeline.decision_intelligence,
                 "create_history_monthly_digest",
                 side_effect=lambda period: periods.append(period) or {"period": period, "created": False},
             ):
            result = pipeline.run_product_delivery_maintenance(today=date(2026, 8, 22))

        health.assert_called_once_with()
        sync.assert_called_once_with()
        self.assertEqual(periods, ["2026-07", "2026-06", "2026-05"])
        self.assertEqual(result["evidence_health"], {"checked": 4})
        self.assertEqual(result["subscriber"], {"enabled": True, "saved": 3})

    def test_product_delivery_wrapper_disable_is_live_and_fail_closed(self):
        with mock.patch.object(pipeline, "ENABLE_REVENUE_PRODUCT_PHASE2", False), \
             mock.patch.object(pipeline.decision_intelligence, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             mock.patch.object(pipeline, "run_evidence_health_maintenance") as health, \
             mock.patch.object(pipeline.decision_intelligence, "sync_subscriber_technology_db") as sync:
            result = pipeline.run_product_delivery_maintenance(today=date(2026, 8, 22))

        self.assertEqual(result, {"subscriber": None, "monthly": [], "evidence_health": None})
        health.assert_not_called()
        sync.assert_not_called()

    def test_evidence_health_wrapper_binds_live_pipeline_dependencies(self):
        states = [{
            "page_id": "ledger",
            "tech_page_id": None,
            "source_type": "github",
            "url": "https://github.com/acme/tool",
        }]
        updates = []

        class FakeLedger:
            ENABLE_EVIDENCE_LEDGER = True

            @staticmethod
            def query_health_candidates(token):
                return list(states)

            @staticmethod
            def check_health(state, fetcher):
                self.assertEqual(
                    fetcher(state["url"]),
                    (200, "live pipeline README", state["url"]),
                )
                return {"health": "COSMETIC_CHANGE", "material": False}

            @staticmethod
            def update_health(page_id, health, token, rereview_triggered):
                updates.append((page_id, rereview_triggered))

        fake_decision = SimpleNamespace(
            NOTION_DECISION_INTELLIGENCE_API_KEY="live-token",
            TECH_PROP_NEXT_REVIEW="Next Review",
            _headers=lambda: {},
        )
        with mock.patch.object(pipeline, "evidence_ledger", FakeLedger), \
             mock.patch.object(pipeline, "decision_intelligence", fake_decision), \
             mock.patch.object(pipeline, "_github_repo_name_from_url", return_value="acme/tool") as repo_name, \
             mock.patch.object(pipeline, "fetch_github_readme_context", return_value="live pipeline README") as readme:
            result = pipeline.run_evidence_health_maintenance()

        repo_name.assert_called_once_with(states[0]["url"])
        readme.assert_called_once_with("acme/tool")
        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["cosmetic"], 1)
        self.assertEqual(result["material"], 0)
        self.assertEqual(updates, [("ledger", False)])

    def test_module_function_objects_are_the_pipeline_canonical_delegate_targets(self):
        self.assertIs(pipeline._previous_month_id_impl, maintenance.previous_month_id)
        self.assertIs(pipeline._current_month_id_impl, maintenance.current_month_id)
        self.assertIs(
            pipeline._run_evidence_health_maintenance_impl,
            maintenance.run_evidence_health_maintenance,
        )
        self.assertIs(
            pipeline._run_product_delivery_maintenance_impl,
            maintenance.run_product_delivery_maintenance,
        )


if __name__ == "__main__":
    unittest.main()
