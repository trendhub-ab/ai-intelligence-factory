from __future__ import annotations

import inspect
import unittest

import run295_note_private_draft_audit as audit


class Run295IdentityListProofContractTests(unittest.TestCase):
    def test_exact_account_and_official_list_are_proven_before_eyecatch(self) -> None:
        source = inspect.getsource(audit._audit_wrapper)
        self.assertIn("_prove_account_and_official_list(page, draft_url)", source)
        self.assertIn("draft_url = str(page.url or \"\")", source)
        self.assertLess(
            source.index("_prove_account_and_official_list(page, draft_url)"),
            source.index("collect_eyecatch_metrics"),
        )

    def test_identity_proof_has_safe_categorical_fail_closed_codes(self) -> None:
        source = inspect.getsource(audit)
        self.assertIn("note_account_ownership_unconfirmed", source)
        self.assertIn("draft_absent_from_official_article_list", source)
        self.assertIn("official_article_list_proof_unconfirmed", source)
        self.assertIn("draft_route_reopen_failed", source)
        self.assertIn("Run295IdentityProofError", source)
        self.assertNotIn("draft_url\": draft_url", source)


if __name__ == "__main__":
    unittest.main()
