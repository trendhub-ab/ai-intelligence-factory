from __future__ import annotations

import inspect
import unittest

import run291_note_private_draft_audit as audit


class Run795Run291NoteListTitleIntegrationTests(unittest.TestCase):
    def test_read_only_audit_passes_exact_title_into_official_list_proof(self) -> None:
        source = inspect.getsource(audit._browser_audit)
        self.assertIn(
            'run190._verify_draft_in_article_list(page, private_url, str(article["title"]))',
            source,
        )


if __name__ == "__main__":
    unittest.main()
