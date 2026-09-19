from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run_public_legacy_critical_repair as repair


ROOT = Path(__file__).resolve().parents[1]


class PublicLegacyCriticalRepairTests(unittest.TestCase):
    def test_exact_two_targets_are_hard_bound(self):
        self.assertEqual(2, len(repair.TARGETS))
        ids = {target.note_id for target in repair.TARGETS}
        self.assertEqual({"nbad7b7a478d3", "n012a6d7edfda"}, ids)
        self.assertEqual("REPAIR_TWO_PUBLIC_LEGACY_ARTICLES", repair.CONFIRM_TOKEN)

    def test_rubygems_title_is_current_gate_compatible(self):
        target = next(t for t in repair.TARGETS if t.key == "rubygems")
        self.assertTrue(target.new_title.endswith("。"))
        self.assertEqual(target.old_title + "。", target.new_title)

    def test_repair_manuscripts_remove_known_overclaims(self):
        assets = repair.validate_repair_assets()
        self.assertEqual({"rubygems", "ai_proficiency"}, set(assets))
        for target in repair.TARGETS:
            body = repair._load_manuscript(target)
            for marker in target.legacy_markers:
                with self.subTest(target=target.key, marker=marker):
                    self.assertNotIn(marker, body)
            for marker in target.current_markers:
                with self.subTest(target=target.key, marker=marker):
                    self.assertIn(marker, body)

    def test_ai_proficiency_keeps_evidence_boundary_explicit(self):
        target = next(t for t in repair.TARGETS if t.key == "ai_proficiency")
        body = repair._load_manuscript(target)
        self.assertIn("この研究だけでAI投資のROI（投資対効果）への影響までは断定できない。", body)
        self.assertIn("ただし、この研究だけで因果関係までは断定できません。", body)
        self.assertIn("一律研修だけに頼らない", body)

    def test_rubygems_keeps_unknown_motive_unknown(self):
        target = next(t for t in repair.TARGETS if t.key == "rubygems")
        body = repair._load_manuscript(target)
        self.assertIn("なぜその手段が選ばれたのかは分かっていません。", body)
        self.assertIn("エージェント内部の認識や意図そのものを証明するものではありません。", body)
        self.assertIn("この帰属は研究チームの分析に基づくものです。", body)

    def test_updater_cannot_create_new_note_or_call_models(self):
        source = inspect.getsource(repair)
        for forbidden in (
            "NOTE_NEW_URL",
            "_create_browser_draft(",
            "_mark_draft_created(",
            "GEMINI_API_KEY",
            "generate_content(",
            "_generate_via_chat(",
            "production_pipeline",
            "_paste_manuscript(",
            "_verify_body_content(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn("_select_exact_text", source)
        self.assertIn("_apply_exact_replacement", source)
        self.assertIn('_unique_button(page, "公開に進む").click()', source)
        self.assertIn('_unique_button(page, "更新する").click()', source)

    def test_every_browser_mutation_is_an_exact_reviewed_replacement(self):
        self.assertGreater(len(repair.RUBYGEMS_REPLACEMENTS), 0)
        self.assertGreater(len(repair.AI_PROFICIENCY_REPLACEMENTS), 0)
        for target in repair.TARGETS:
            for change in target.replacements:
                with self.subTest(target=target.key, old=change.old[:40]):
                    self.assertTrue(change.old)
                    self.assertTrue(change.new)
                    self.assertNotEqual(change.old, change.new)

    def test_targeted_edits_cover_the_two_audit_root_causes(self):
        ruby_new = "\n".join(change.new for change in repair.RUBYGEMS_REPLACEMENTS)
        self.assertIn("認識や意図そのものを証明するものではありません", ruby_new)
        self.assertIn("なぜその手段が選ばれたのかは分かっていません", ruby_new)
        ai_new = "\n".join(change.new for change in repair.AI_PROFICIENCY_REPLACEMENTS)
        self.assertIn("ROI（投資対効果）への影響までは断定できない", ai_new)
        self.assertIn("因果関係までは断定できません", ai_new)

    def test_eyecatch_is_not_mutated(self):
        source = inspect.getsource(repair)
        for forbidden in ("_upload_header_image(", "_download_eyecatch(", "set_input_files("):
            self.assertNotIn(forbidden, source)

    def test_repair_assets_are_repo_local(self):
        for target in repair.TARGETS:
            self.assertTrue(target.manuscript_path.is_file())
            self.assertTrue(str(target.manuscript_path).startswith(str(ROOT)))


if __name__ == "__main__":
    unittest.main()
