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

    def test_draft_routes_from_api_payload_uses_only_confirmed_drafts(self):
        payload = {
            "data": {
                "notes": [
                    {"key": "naaa111", "status": "draft"},
                    {"key": "nbbb222", "status": "draft"},
                ],
                "isLastPage": True,
            }
        }
        self.assertEqual(
            run296.draft_routes_from_api_payload(payload),
            [
                "https://editor.note.com/notes/naaa111/edit/",
                "https://editor.note.com/notes/nbbb222/edit/",
            ],
        )

    def test_draft_routes_from_api_payload_fails_closed_on_non_draft_item(self):
        payload = {
            "data": {
                "notes": [{"key": "naaa111", "status": "published"}],
                "isLastPage": True,
            }
        }
        with self.assertRaises(run296.InventoryError) as ctx:
            run296.draft_routes_from_api_payload(payload)
        self.assertEqual(ctx.exception.code, "draft_api_scope_violation")

    def test_draft_routes_from_api_payload_fails_closed_on_missing_key(self):
        payload = {"data": {"notes": [{"status": "draft"}], "isLastPage": True}}
        with self.assertRaises(run296.InventoryError) as ctx:
            run296.draft_routes_from_api_payload(payload)
        self.assertEqual(ctx.exception.code, "draft_api_identity_missing")

    def test_quality_diagnostics_explain_ai_smell_without_private_text(self):
        body = (
            "私たちは無意識に新しい技術を難しく考えがちです。そんな経験は少なくないでしょう。"
            "こうした背景から、この技術はどれほど便利であっても判断が必要です。"
            "私ならこの変化を踏まえ、今すぐ全面導入する必要はないと考えます。"
            "まずはできるところから小さく始めたいところです。"
        )
        result = run296.quality_diagnostics(body)
        self.assertTrue(result["naturalness_high"])
        self.assertGreaterEqual(result["naturalness_score"], 5)
        self.assertIn("generic_business_scaffold_count", result)
        self.assertIn("human_depth_score", result)
        self.assertIn("reader_accessibility", result)
        self.assertIn("reader_curiosity_pull", result)
        self.assertNotIn(body, repr(result))

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
            "quality": {
                "naturalness_score": 2,
                "reader_accessibility": "GOOD",
                "accessibility_issues": [],
            },
            "reasons": [],
        }
        safe = run296.safe_record(raw)
        for forbidden in ("title", "body", "draft_url", "draft_id", "body_fingerprint"):
            self.assertNotIn(forbidden, safe)
        self.assertEqual(safe["position"], 4)
        self.assertEqual(safe["classification"], "KEEP")


if __name__ == "__main__":
    unittest.main()
