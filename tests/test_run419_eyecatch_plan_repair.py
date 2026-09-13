import inspect
import unittest
from unittest import mock

from PIL import ImageFont

import run419_rubygems_eyecatch_plan_repair as r419


class Run419EyecatchPlanRepairTests(unittest.TestCase):
    def _valid_source_title(self):
        import run180_eyecatch_semantic_layout as r180
        return r180._source_title_for_direction(r419.r418.EXPECTED_NOTE_TITLE)

    def test_valid_semantic_title_repairs_bad_geometry_without_rewrite(self):
        import editorial_eyecatch as ee
        import run178_eyecatch_editorial_layout_optimizer as r178
        import run180_eyecatch_semantic_layout as r180

        source = self._valid_source_title()
        sub = "OpenAIのAIエージェントとRubyGemsを巡るセキュリティ事例"
        raw = {
            "eyecatch_title": "OpenAIエージェントのRubyGems騒動、権限管理の境界線",
            "title_lines": ["OpenAIエージェントのRubyGems騒動、権限管理の境界線"],
            "title_font_size": 999,
            "title_line_gap": 99,
            "subheadline_lines": ["壊れた分割"],
            "subheadline_font_size": 999,
            "highlight_text": "権限管理の境界線",
        }
        # Run179 normally supplies the pinned font; for zero-network unit coverage use a
        # deterministic local default font so only repair semantics/partition are tested.
        with mock.patch.object(ee, "_jp_font", side_effect=lambda size, bold=True: ImageFont.load_default()):
            repaired = r419._repair_layout_plan(source, sub, raw)
        self.assertIsNotNone(repaired)
        self.assertEqual(
            r178._canonical_partition_text("".join(repaired["title_lines"])),
            r178._canonical_partition_text(repaired["eyecatch_title"]),
        )
        self.assertEqual(
            r178._canonical_partition_text("".join(repaired["subheadline_lines"])),
            r178._canonical_partition_text(sub),
        )
        self.assertGreaterEqual(repaired["title_font_size"], r180.TITLE_MIN_FONT)
        self.assertLessEqual(repaired["title_font_size"], r180.TITLE_MAX_FONT)
        self.assertGreaterEqual(repaired["subheadline_font_size"], r180.SUB_MIN_FONT)
        self.assertLessEqual(repaired["subheadline_font_size"], r180.SUB_MAX_FONT)
        self.assertLessEqual(repaired["title_line_gap"], 18)

    def test_invalid_semantic_title_is_never_repaired(self):
        source = self._valid_source_title()
        raw = {
            "eyecatch_title": "AIエージェントの権限管理を考える",
            "title_lines": ["AIエージェントの権限管理を考える"],
            "title_font_size": 60,
            "title_line_gap": 12,
            "subheadline_lines": ["OpenAIのAIエージェントとRubyGemsを巡るセキュリティ事例"],
            "subheadline_font_size": 24,
            "highlight_text": "権限管理を考える",
        }
        self.assertIsNone(
            r419._repair_layout_plan(
                source,
                "OpenAIのAIエージェントとRubyGemsを巡るセキュリティ事例",
                raw,
            )
        )

    def test_repaired_render_has_one_model_call_and_no_raw_fallback(self):
        source = inspect.getsource(r419._render_canonical_repaired)
        self.assertIn("Run419 refuses a second model request", source)
        self.assertIn('gemini-3.5-flash', source)
        self.assertIn("_repair_layout_plan", source)
        self.assertIn("_render_with_validated_plan", source)
        self.assertNotIn("generate_note_editorial_eyecatch", source)
        self.assertNotIn("gemini-3.8-flash", source)

    def test_exact_target_and_private_draft_path_are_inherited(self):
        source = inspect.getsource(r419.render_and_attach)
        self.assertIn("require_broken=True", source)
        self.assertIn("_upload_replace", source)
        self.assertIs(r419.refresh_existing_private_draft.__globals__["r418"], r419.r418)

    def test_no_public_release_surface(self):
        source = inspect.getsource(r419)
        for token in ("publish_note", "click_publish", "release_note", "公開する"):
            self.assertNotIn(token, source)
        self.assertIn('"public_release": False', source)


if __name__ == "__main__":
    unittest.main()
