from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch
from datetime import date
import content_generation_protocol as generation

import member_customer_surface_contract as contract


ROOT = Path(__file__).resolve().parents[1]


class MemberCustomerSurfaceContractTests(unittest.TestCase):
    def test_every_registered_surface_has_owner_audit_and_existing_files(self):
        self.assertEqual([], contract.validate_repository(ROOT))
        self.assertGreaterEqual(len(contract.SURFACES), 9)

    def test_member_home_and_memo_do_not_teach_internal_codes(self):
        for text in (contract.HOME_CONTENT, contract.JUDGMENT_MEMO_CONTENT):
            for token in (*contract.RAW_DECISION_CODES, *contract.FORBIDDEN_PRIMARY_JARGON):
                self.assertNotIn(token, text)
        self.assertIn("まずは、この3つだけ", contract.HOME_CONTENT)
        self.assertIn("まず書く5つ", contract.JUDGMENT_MEMO_CONTENT)

    def test_home_has_clear_three_step_product_route(self):
        text = contract.HOME_CONTENT
        self.assertIn("今月のDecision Brief", text)
        self.assertIn("AI意思決定DB", text)
        self.assertIn("判断メモ", text)
        self.assertIn("今月見るものをBriefで絞る", text)
        self.assertIn("気になったものだけDBで確かめる", text)

    def test_user_facing_views_hide_operator_score_and_sync_fields(self):
        forbidden = {"判断スコア", "同期ID", "評価の変化", "分類", "情報源"}
        for view_id, spec in contract.VIEW_CONTRACTS.items():
            with self.subTest(view_id=view_id):
                self.assertFalse(forbidden & set(spec["show"]))
                self.assertTrue(spec["name"])
                self.assertIn("AI・技術名", spec["show"])

    def test_operational_views_are_explicitly_labeled(self):
        for name in contract.INTERNAL_VIEW_RENAMES.values():
            self.assertTrue(name.startswith("運営用｜"))

    def test_required_surfaces_are_independent_of_registry_entries(self):
        with patch.object(contract, "SURFACES", {k: v for k, v in contract.SURFACES.items() if k != "member_home"}):
            self.assertTrue(any("registry changed" in e for e in contract.validate_repository(ROOT)))

    def test_new_member_renderer_must_be_classified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for spec in contract.SURFACES.values():
                for key in ("owner", "audit"):
                    path = root / spec[key]
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.touch()
            (root / "member_new_customer_page.py").write_text("def render(): return 'new page'")
            self.assertTrue(any("unclassified" in e for e in contract.validate_repository(root)))

    def test_digest_is_registered_and_has_no_internal_scoring_jargon(self):
        self.assertIn("monthly_digest", contract.SURFACES)
        rows = [
            {"name": "Finished", "url": "https://example.com/finished", "score": 90, "source": "GitHub", "status": "Deep Dive", "article_status": "Ready"},
            {"name": "Unfinished", "url": "https://example.com/unfinished", "score": 95, "source": "GitHub", "status": "Deep Dive", "article_status": "Draft"},
        ]
        rendered = generation.build_monthly_digest_markdown(date(2026, 10, 1), rows, STATUS_DEEP_DIVE="Deep Dive", ARTICLE_STATUS_READY="Ready", STATUS_STOCKED="Stocked")
        for token in contract.FORBIDDEN_PRIMARY_JARGON:
            self.assertNotIn(token, rendered)
        finished, candidates = rendered.split("## これから詳しく確かめる候補")
        self.assertIn("[Finished]", finished)
        self.assertNotIn("[Unfinished]", finished)
        self.assertIn("[Unfinished]", candidates)

    def test_nested_member_renderer_must_be_classified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "components").mkdir()
            (root / "components" / "member_new_page.py").write_text("def render(): return 'page'")
            self.assertTrue(any("unclassified" in e for e in contract.validate_repository(root)))

    def test_new_renderer_in_existing_owner_must_be_classified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "content_generation_protocol.py").write_text("def build_new_member_page(): return 'new page'")
            self.assertTrue(any("unclassified customer entrypoint" in e for e in contract.validate_repository(root)))

    def test_member_migration_requires_successful_main_ci_and_explicit_marker(self):
        import yaml
        workflow = yaml.load((ROOT / ".github/workflows/member-presentation-sync.yml").read_text(), Loader=yaml.BaseLoader)
        self.assertNotIn("push", workflow["on"])
        self.assertIn("Integration Reconciliation CI", workflow["on"]["workflow_run"]["workflows"])
        gate = workflow["jobs"]["sync"]["if"]
        self.assertIn("head_branch == 'main'", gate)
        self.assertIn("conclusion == 'success'", gate)
        self.assertIn("[member-ux-refresh]", gate)
        steps = workflow["jobs"]["sync"]["steps"]
        body = next(s for s in steps if s.get("run") == "python run219_member_human_language_ui.py body")
        self.assertIn("github.event.workflow_run.name == 'Integration Reconciliation CI'", body["env"]["MEMBER_BODY_FORCE_FULL"])


if __name__ == "__main__":
    unittest.main()
