import unittest
from pathlib import Path

import documentation_freshness_guard as guard


ROOT = Path(__file__).resolve().parents[1]


class Run210DocumentationFreshnessGuardTests(unittest.TestCase):
    def test_current_repository_contract_is_documented(self):
        self.assertEqual(guard.validate(ROOT), [])

    def test_new_runtime_layer_without_spec_update_is_rejected(self):
        production = """
def install_runtime_layers(pipeline_module):
    import run203_runtime_state_channel
    import run999_new_production_contract
    return pipeline_module
"""
        spec = "- `run203_runtime_state_channel.py`\n"
        errors = guard.runtime_layer_errors(production, spec)
        self.assertTrue(any("run999_new_production_contract.py" in error for error in errors))

    def test_runtime_layer_is_accepted_only_when_documented(self):
        production = """
def install_runtime_layers(pipeline_module):
    import run999_new_production_contract
    return pipeline_module
"""
        spec = "- `run999_new_production_contract.py`\n"
        self.assertEqual(guard.runtime_layer_errors(production, spec), [])

    def test_flash_ceiling_change_requires_deliberate_docs_guard_update(self):
        one_shot = "\n".join(
            [
                'GEMINI_36_FLASH_DAILY_BUDGET: "20"',
                'GEMINI_37_FLASH_DAILY_BUDGET: "18"',
                'GEMINI_35_FLASH_DAILY_BUDGET: "18"',
            ]
        )
        daily = "name: Daily [PAUSED]\nif: ${{ false }}\n"
        pending = (
            "FAST_LANE_PENDING_RETRY_REQUEST_BUDGET = 3\n"
            "FAST_LANE_503_COOLDOWN_THRESHOLD = 1\n"
        )
        quota = (
            "18 requests/day 18/20 Google AI Studio Rate Limits\n"
            "timeoutだからといって巻き戻しません\n"
            "最大3 requests 1回目のHTTP 503 Reader Value repair\n"
        )
        spec = (
            "pre-send reservationを巻き戻さない\n"
            "最大3 requests 1回目のHTTP 503 Reader Value repair\n"
        )
        errors = guard.quota_contract_errors(one_shot, daily, pending, quota, spec)
        self.assertTrue(any("GEMINI_36_FLASH_DAILY_BUDGET" in error for error in errors))

    def test_pending_retry_budget_change_requires_docs_guard_update(self):
        one_shot = "\n".join(
            [
                'GEMINI_36_FLASH_DAILY_BUDGET: "18"',
                'GEMINI_37_FLASH_DAILY_BUDGET: "18"',
                'GEMINI_35_FLASH_DAILY_BUDGET: "18"',
            ]
        )
        daily = "name: Daily [PAUSED]\nif: ${{ false }}\n"
        pending = (
            "FAST_LANE_PENDING_RETRY_REQUEST_BUDGET = 4\n"
            "FAST_LANE_503_COOLDOWN_THRESHOLD = 1\n"
        )
        quota = (
            "18 requests/day 18/20 Google AI Studio Rate Limits\n"
            "timeoutだからといって巻き戻しません\n"
            "最大3 requests 1回目のHTTP 503 Reader Value repair\n"
        )
        spec = (
            "pre-send reservationを巻き戻さない\n"
            "最大3 requests 1回目のHTTP 503 Reader Value repair\n"
        )
        errors = guard.quota_contract_errors(one_shot, daily, pending, quota, spec)
        self.assertTrue(any("request budget changed from 3" in error for error in errors))

    def test_daily_unpause_requires_canonical_review(self):
        one_shot = "\n".join(
            [
                'GEMINI_36_FLASH_DAILY_BUDGET: "18"',
                'GEMINI_37_FLASH_DAILY_BUDGET: "18"',
                'GEMINI_35_FLASH_DAILY_BUDGET: "18"',
            ]
        )
        daily = "name: Daily Intelligence & Content Pipeline\n"
        pending = (
            "FAST_LANE_PENDING_RETRY_REQUEST_BUDGET = 3\n"
            "FAST_LANE_503_COOLDOWN_THRESHOLD = 1\n"
        )
        quota = (
            "18 requests/day 18/20 Google AI Studio Rate Limits\n"
            "timeoutだからといって巻き戻しません\n"
            "最大3 requests 1回目のHTTP 503 Reader Value repair\n"
        )
        spec = (
            "pre-send reservationを巻き戻さない\n"
            "最大3 requests 1回目のHTTP 503 Reader Value repair\n"
        )
        errors = guard.quota_contract_errors(one_shot, daily, pending, quota, spec)
        self.assertTrue(any("Daily workflow is no longer hard PAUSED" in error for error in errors))

    def _member_contract_docs(self):
        spec = (
            "Run211 Inventory plan Subscriber Decision Brief Sync Member Presentation Sync\n"
        )
        readme = "Run211 Subscriber Decision Brief Sync Member Presentation Sync\n"
        return spec, readme

    def test_member_presentation_direct_source_race_is_rejected(self):
        inventory = "run-name: Subscriber Inventory Bootstrap [${{ inputs.mode }}]\n"
        subscriber = """
workflow_run:
  workflows:
    - Daily Intelligence & Content Pipeline
    - Daily Intelligence & Content Pipeline [ONE-SHOT]
    - Subscriber Inventory Bootstrap
  types: [completed]
github.event.workflow_run.name != 'Subscriber Inventory Bootstrap'
contains(github.event.workflow_run.display_title, '[apply]')
group: member-derived-notion-writes
"""
        presentation = """
workflow_run:
  workflows:
    - Subscriber Decision Brief Sync
    - Daily Intelligence & Content Pipeline [ONE-SHOT]
  types: [completed]
group: member-derived-notion-writes
"""
        spec, readme = self._member_contract_docs()
        errors = guard.member_product_sync_errors(
            inventory, subscriber, presentation, spec, readme
        )
        self.assertTrue(any("racing its source" in error for error in errors))

    def test_inventory_plan_write_fanout_is_rejected(self):
        inventory = "run-name: Subscriber Inventory Bootstrap [${{ inputs.mode }}]\n"
        subscriber = """
workflow_run:
  workflows:
    - Daily Intelligence & Content Pipeline
    - Daily Intelligence & Content Pipeline [ONE-SHOT]
    - Subscriber Inventory Bootstrap
  types: [completed]
github.event.workflow_run.name != 'Subscriber Inventory Bootstrap'
group: member-derived-notion-writes
"""
        presentation = """
workflow_run:
  workflows:
    - Subscriber Decision Brief Sync
  types: [completed]
group: member-derived-notion-writes
"""
        spec, readme = self._member_contract_docs()
        errors = guard.member_product_sync_errors(
            inventory, subscriber, presentation, spec, readme
        )
        self.assertTrue(any("apply-only downstream filter" in error for error in errors))

    def _run218_contract_docs(self):
        common = (
            f"{guard.CANONICAL_MEMBER_HOME_ID}\n"
            f"{guard.CANONICAL_MEMBER_HOME_TITLE}\n"
            f"{guard.CURRENT_MEMBER_DB_ID}\n"
            f"{guard.CURRENT_MEMBER_DATA_SOURCE_ID}\n"
            f"{guard.LEGACY_MEMBER_DATA_SOURCE_ID}\n"
            "旧版・使用禁止\n"
            "PC-first live Top3 今月の重要変化 評価の変化 >= 20 <= -20\n"
        )
        spec = "Paid Member Navigation/UI Baseline: **Run218\n" + common
        readme = "paid member navigation/UI baseline:** Run218\n" + common
        run217 = (
            f"{guard.SUPERSEDED_RUN217_HOME_ID}\n"
            "superseded by Run218\n"
            "【旧・統合済み】AI Intelligence｜会員ホーム\n"
        )
        run218 = (
            common
            + f"{guard.SUPERSEDED_RUN217_HOME_ID}\n"
            + "PC is the primary member experience\n"
            + "Mobile/simple views are secondary fallback surfaces only\n"
            + "注目順位 <= 3\n"
            + "presentation-only fallback\n"
            + "does not modify the monthly checkbox\n"
            + "blank table\n"
            + "評価の変化 >= 20 評価の変化 <= -20\n"
            + "Gemini/model requests used for this run: **0**\n"
        )
        return spec, readme, run217, run218

    def test_run218_canonical_navigation_contract_is_accepted(self):
        docs = self._run218_contract_docs()
        self.assertEqual(guard.member_navigation_ux_errors(*docs), [])

    def test_old_run217_home_cannot_be_promoted_back_to_canonical(self):
        spec, readme, run217, run218 = self._run218_contract_docs()
        spec += "\n正規会員入口は`AI Intelligence｜会員ホーム`\n"
        errors = guard.member_navigation_ux_errors(spec, readme, run217, run218)
        self.assertTrue(any("promoted back" in error for error in errors))

    def test_pc_first_contract_cannot_be_silently_removed(self):
        spec, readme, run217, run218 = self._run218_contract_docs()
        run218 = run218.replace("PC is the primary member experience", "PC optional")
        errors = guard.member_navigation_ux_errors(spec, readme, run217, run218)
        self.assertTrue(any("PC is the primary member experience" in error for error in errors))

    def test_important_change_fallback_cannot_mutate_source_semantics(self):
        spec, readme, run217, run218 = self._run218_contract_docs()
        run218 = run218.replace("does not modify the monthly checkbox", "checkbox may be set for display")
        errors = guard.member_navigation_ux_errors(spec, readme, run217, run218)
        self.assertTrue(any("monthly checkbox" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
