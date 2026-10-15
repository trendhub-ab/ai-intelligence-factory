from __future__ import annotations

import unittest
from unittest import mock

import note_eyecatch_persistence as proof
import run295_note_private_draft_audit as audit


def _present_header_metrics() -> dict[str, int | bool]:
    return {
        "eyecatch_exact_control_visible_count": 0,
        "image_add_control_visible_count": 0,
        "large_top_img_count": 1,
        "large_top_background_count": 0,
        "max_top_media_width": 620,
        "max_top_media_height": 325,
        "title_geometry_available": True,
    }


class _NoLegacyLocator:
    @property
    def first(self):
        return self

    def count(self) -> int:
        return 0

    def is_visible(self, *args, **kwargs) -> bool:
        return False


class _Page:
    def locator(self, selector: str, *args, **kwargs):
        return _NoLegacyLocator()


class Run797Run295Run292ProofHandoffTests(unittest.TestCase):
    def test_top_level_run_hands_confirmed_proof_into_run292_canonical_audit(self) -> None:
        original_run291_audit = audit.base._audit_current_page
        original_run291_run = audit.base.run
        original_run292_upstream = audit.base292._ORIGINAL_AUDIT_CURRENT_PAGE

        def legacy_upstream(page, title, manuscript):
            legacy = page.locator(proof.LEGACY_CONTROL_SELECTOR).first
            if not (legacy.count() and legacy.is_visible(timeout=10)):
                raise audit.base.PrivateDraftAuditError(
                    "Private draft eyecatch persistence could not be confirmed"
                )
            return {"eyecatch_present": True}

        def fake_run291(*, confirm: str, sync_id: str, prepare_only: bool = False):
            self.assertFalse(prepare_only)
            metrics = audit.base._audit_current_page(_Page(), "private-title", "private-body")
            return {
                "success": True,
                "status": "audit_passed",
                "zero_gemini_calls": True,
                "read_only": True,
                "public_release": False,
                "draft_mutation": False,
                "sync_id": sync_id,
                **metrics,
            }

        audit.base292._ORIGINAL_AUDIT_CURRENT_PAGE = legacy_upstream
        audit.base.run = fake_run291
        try:
            with mock.patch.object(
                audit.base.note_base, "_find_title", return_value=object()
            ), mock.patch.object(
                audit.base.note_base, "_find_body", return_value=object()
            ), mock.patch.object(
                audit.base292.note_dom, "snapshot_note_body", return_value={}
            ), mock.patch.object(
                audit.base292, "_canonical_snapshot_metrics", return_value={"canonical_match": True}
            ), mock.patch.object(
                proof, "collect_eyecatch_metrics", return_value=_present_header_metrics()
            ) as collect:
                result = audit.run(
                    confirm=audit.base.CONFIRM_TOKEN,
                    sync_id="a" * 32,
                    prepare_only=False,
                )

            self.assertTrue(result["success"])
            self.assertTrue(result["eyecatch_present"])
            self.assertTrue(result["canonical_match"])
            self.assertEqual(result["eyecatch_proof_mode"], proof.PRESENT_HEADER_MEDIA)
            self.assertEqual(collect.call_count, 1)
        finally:
            audit.base292._ORIGINAL_AUDIT_CURRENT_PAGE = original_run292_upstream
            audit.base.run = original_run291_run
            audit.base._audit_current_page = original_run291_audit


if __name__ == "__main__":
    unittest.main()
