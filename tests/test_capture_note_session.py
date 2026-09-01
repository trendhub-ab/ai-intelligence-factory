import unittest

from tools.capture_note_session import _is_note_session_page


class CaptureNoteSessionTests(unittest.TestCase):
    def test_accepts_stable_note_pages(self):
        self.assertTrue(_is_note_session_page("https://note.com/"))
        self.assertTrue(_is_note_session_page("https://note.com/trendhub_biz"))
        self.assertTrue(_is_note_session_page("https://www.note.com/example"))

    def test_rejects_oauth_and_login_pages(self):
        self.assertFalse(_is_note_session_page("https://accounts.google.com/v3/signin/identifier"))
        self.assertFalse(_is_note_session_page("https://note.com/login"))
        self.assertFalse(_is_note_session_page("https://note.com/signin"))
        self.assertFalse(_is_note_session_page("https://note.com/signup"))
        self.assertFalse(_is_note_session_page("https://note.com/auth/google_oauth2/callback"))

    def test_rejects_lookalike_hosts(self):
        self.assertFalse(_is_note_session_page("https://note.com.example.com/"))
        self.assertFalse(_is_note_session_page("https://example.com/note.com"))


if __name__ == "__main__":
    unittest.main()
