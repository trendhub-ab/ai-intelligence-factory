from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run315_member_onboarding_update as run315
import run316_member_onboarding_finalize_probe as run316

ROOT = Path(__file__).resolve().parents[1]


class Run316MemberOnboardingFinalizeProbeTests(unittest.TestCase):
    def test_probe_is_hard_bound_to_exact_audited_or_staged_article(self) -> None:
        self.assertEqual(run316.CONFIRM_TOKEN, "PROBE_MEMBER_ONBOARDING_FINALIZE_N284E428C80F4")
        self.assertEqual(run316.STAGED_BODY_SHA256, "aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6")
        auth = inspect.getsource(run316._authorized_source_state)
        probe = inspect.getsource(run316.probe)
        self.assertIn("run315.AUDITED_TITLE", auth)
        self.assertIn("run315.AUDITED_BODY_SHA256", auth)
        self.assertIn("run315.NEW_TITLE", auth)
        self.assertIn("STAGED_BODY_SHA256", auth)
        self.assertIn("run315._verify_editor(body)", auth)
        self.assertIn("run315.TARGET_PUBLISH_URL", probe)
        self.assertIn("run315.MEMBERSHIP_NAME", probe)

    def test_probe_does_not_rewrite_title_or_body(self) -> None:
        source = inspect.getsource(run316.probe)
        self.assertNotIn("_set_title", source)
        self.assertNotIn("_paste_manuscript", source)
        self.assertNotIn("MANUSCRIPT", source)
        self.assertNotIn("page.keyboard", source)

    def test_probe_selects_membership_but_never_clicks_final_commit(self) -> None:
        source = inspect.getsource(run316.probe)
        self.assertIn("run315._ensure_membership_selected(page)", source)
        self.assertNotIn('_unique_button(page, "更新する")', source)
        self.assertNotIn('_unique_button(page, "公開する")', source)
        self.assertNotIn('_unique_button(page, "投稿する")', source)
        self.assertNotIn('_unique_button(page, "保存する")', source)
        self.assertIn('"final_commit_clicked": False', source)

    def test_inventory_covers_current_actionable_control_shapes(self) -> None:
        source = inspect.getsource(run316._control_inventory)
        self.assertIn("button,[role=", source)
        self.assertIn("input[type=", source)
        self.assertIn("aria-label", source)
        self.assertIn("aria-disabled", source)
        self.assertIn("inViewport", source)
        self.assertIn("context", source)

    def test_workflow_is_manual_exact_and_zero_model(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "note-member-onboarding-finalize-probe.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("PROBE_MEMBER_ONBOARDING_FINALIZE_N284E428C80F4", workflow)
        self.assertIn("run316_member_onboarding_finalize_probe.py", workflow)
        self.assertIn("final commit clicked: `false`", workflow)
        self.assertIn("zero Gemini calls: `true`", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)

    def test_chatops_route_is_exact_and_no_save_described(self) -> None:
        bridge = (ROOT / ".github" / "workflows" / "chatops-note.yml").read_text(encoding="utf-8")
        self.assertIn("/aiif note onboarding probe", bridge)
        self.assertIn("onboarding_probe", bridge)
        self.assertIn("note-member-onboarding-finalize-probe.yml", bridge)
        self.assertIn("no final commit", bridge)


if __name__ == "__main__":
    unittest.main()
