import inspect
import unittest

import note_draft_automation as base
import run187_note_editor_readiness as run187


class Run187NoteEditorReadinessTests(unittest.TestCase):
    def test_editor_url_accepts_new_and_edit_routes_only(self):
        self.assertTrue(run187._is_editor_url("https://note.com/notes/new"))
        self.assertTrue(run187._is_editor_url("https://note.com/notes/abc123/edit"))
        self.assertTrue(run187._is_editor_url("https://editor.note.com/notes/abc123/edit"))
        self.assertFalse(run187._is_editor_url("https://note.com/"))
        self.assertFalse(run187._is_editor_url("https://example.com/notes/new"))

    def test_title_candidate_prefers_semantic_title(self):
        explicit = run187._title_candidate_score(
            attrs="aria-label 記事タイトル",
            tag="div",
            y=420,
            height=80,
            editable=True,
        )
        geometric = run187._title_candidate_score(
            attrs="role textbox",
            tag="div",
            y=300,
            height=80,
            editable=True,
        )
        self.assertEqual((0, 420), explicit)
        self.assertEqual((4, 300), geometric)
        self.assertLess(explicit[0], geometric[0])

    def test_title_candidate_rejects_large_or_low_body_editable(self):
        self.assertIsNone(
            run187._title_candidate_score(attrs="", tag="div", y=900, height=80, editable=True)
        )
        self.assertIsNone(
            run187._title_candidate_score(attrs="", tag="div", y=500, height=500, editable=True)
        )

    def test_install_only_patches_title_discovery(self):
        original = base._find_title
        try:
            run187.install()
            self.assertIs(base._find_title, run187._find_title)
        finally:
            base._find_title = original

    def test_no_model_or_public_release_surface(self):
        source = inspect.getsource(run187)
        self.assertNotIn("GEMINI_API_KEY", source)
        self.assertNotIn("_generate_via_chat", source)
        self.assertNotIn("公開に進む", source)
        self.assertNotIn("投稿する", source)
        self.assertIn("https://note.com/notes/new", source)


if __name__ == "__main__":
    unittest.main()
