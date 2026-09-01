from __future__ import annotations

import inspect
import unittest

import run187_note_editor_readiness as run187
import run189_note_editor_route_gate as run189


class Run189NoteEditorRouteGateTests(unittest.TestCase):
    def test_editor_url_gate_rejects_homepage_and_accepts_editor_routes(self) -> None:
        self.assertFalse(run187._is_editor_url("https://note.com/"))
        self.assertFalse(run187._is_editor_url("https://note.com/new"))
        self.assertTrue(run187._is_editor_url("https://note.com/notes/new"))
        self.assertTrue(run187._is_editor_url("https://note.com/notes/abc123/edit"))
        self.assertTrue(run187._is_editor_url("https://editor.note.com/notes/abc123/edit"))

    def test_title_discovery_requires_editor_route_before_dom_scan(self) -> None:
        source = inspect.getsource(run189._find_title)
        ensure_pos = source.index("_ensure_editor_route(page)")
        explicit_pos = source.index("run187._explicit_title(page)")
        ranked_pos = source.index("run187._ranked_title(page)")
        self.assertLess(ensure_pos, explicit_pos)
        self.assertLess(ensure_pos, ranked_pos)
        self.assertIn("run187._is_editor_url", source)

    def test_header_upload_requires_editor_route_first(self) -> None:
        source = inspect.getsource(run189._upload_header_image)
        ensure_pos = source.index("_ensure_editor_route(page)")
        upload_pos = source.index("_ORIGINAL_RUN188_UPLOAD")
        self.assertLess(ensure_pos, upload_pos)

    def test_official_post_control_precedes_direct_route_fallback(self) -> None:
        source = inspect.getsource(run189._ensure_editor_route)
        click_pos = source.index("_click_post_control(page)")
        direct_pos = source.index('page.goto("https://note.com/notes/new"')
        self.assertLess(click_pos, direct_pos)

    def test_overlay_has_zero_model_and_no_release_action(self) -> None:
        source = inspect.getsource(run189)
        self.assertIn("base._find_title = _find_title", source)
        self.assertIn("base._upload_header_image = _upload_header_image", source)
        self.assertNotIn("Gemini", source.replace("zero Gemini/model calls", ""))
        self.assertNotIn("公開する", source)
        self.assertNotIn("投稿する", source)


if __name__ == "__main__":
    unittest.main()
