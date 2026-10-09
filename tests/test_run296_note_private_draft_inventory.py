import unittest

import run296_note_private_draft_inventory as run296


class Run296InventoryContractTests(unittest.TestCase):
    def test_extract_edit_routes_keeps_only_private_editor_routes_and_preserves_order(self):
        hrefs = [
            "https://note.com/notes/aaa/edit",
            "/notes/bbb/edit",
            "https://note.com/notes/aaa/edit",
            "https://note.com/notes/ccc",
            "https://example.com/notes/ddd/edit",
            "javascript:void(0)",
        ]
        self.assertEqual(
            run296.extract_edit_routes(hrefs),
            [
                "https://note.com/notes/aaa/edit",
                "https://note.com/notes/bbb/edit",
            ],
        )

    def test_eyecatch_only_empty_body_is_discard_candidate_when_untracked(self):
        result = run296.classify_draft(
            title_chars=18,
            body_chars=0,
            eyecatch_present=True,
            naturalness_high=False,
            current_aiif_linked=False,
            exact_duplicate_of=None,
        )
        self.assertEqual(result["classification"], "DISCARD_CANDIDATE")
        self.assertIn("eyecatch_only_empty_body", result["reasons"])

    def test_tracked_incomplete_draft_is_never_discarded_automatically(self):
        result = run296.classify_draft(
            title_chars=18,
            body_chars=0,
            eyecatch_present=True,
            naturalness_high=False,
            current_aiif_linked=True,
            exact_duplicate_of=None,
        )
        self.assertEqual(result["classification"], "REPAIR")
        self.assertIn("tracked_draft_incomplete", result["reasons"])

    def test_ai_smell_alone_routes_to_repair_not_discard(self):
        result = run296.classify_draft(
            title_chars=30,
            body_chars=1800,
            eyecatch_present=True,
            naturalness_high=True,
            current_aiif_linked=False,
            exact_duplicate_of=None,
        )
        self.assertEqual(result["classification"], "REPAIR")
        self.assertIn("naturalness_high", result["reasons"])

    def test_complete_clean_draft_is_keep(self):
        result = run296.classify_draft(
            title_chars=30,
            body_chars=1800,
            eyecatch_present=True,
            naturalness_high=False,
            current_aiif_linked=False,
            exact_duplicate_of=None,
        )
        self.assertEqual(result["classification"], "KEEP")

    def test_exact_duplicate_untracked_is_discard_candidate(self):
        result = run296.classify_draft(
            title_chars=30,
            body_chars=1800,
            eyecatch_present=True,
            naturalness_high=False,
            current_aiif_linked=False,
            exact_duplicate_of=2,
        )
        self.assertEqual(result["classification"], "DISCARD_CANDIDATE")
        self.assertIn("exact_duplicate", result["reasons"])

    def test_safe_record_never_exposes_private_content_or_draft_identity(self):
        raw = {
            "position": 4,
            "title": "unpublished title",
            "body": "private manuscript",
            "draft_url": "https://note.com/notes/secret/edit",
            "draft_id": "secret",
            "body_fingerprint": "abc",
            "title_chars": 21,
            "body_chars": 980,
            "eyecatch_present": True,
            "naturalness_high": False,
            "current_aiif_linked": False,
            "classification": "KEEP",
            "reasons": [],
        }
        safe = run296.safe_record(raw)
        for forbidden in ("title", "body", "draft_url", "draft_id", "body_fingerprint"):
            self.assertNotIn(forbidden, safe)
        self.assertEqual(safe["position"], 4)
        self.assertEqual(safe["classification"], "KEEP")


if __name__ == "__main__":
    unittest.main()
