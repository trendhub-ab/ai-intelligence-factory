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


def _ambiguous_metrics() -> dict[str, int | bool]:
    return {
        "eyecatch_exact_control_visible_count": 0,
        "image_add_control_visible_count": 0,
        "large_top_img_count": 0,
        "large_top_background_count": 0,
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


class Run796Run295EyecatchProofStabilityTests(unittest.TestCase):
    def test_read_only_audit_reuses_one_confirmed_eyecatch_proof(self) -> None:
        def original(page, title, manuscript):
            legacy = page.locator(proof.LEGACY_CONTROL_SELECTOR).first
            if not (legacy.count() and legacy.is_visible(timeout=10)):
                raise audit.base.PrivateDraftAuditError(
                    "Private draft eyecatch persistence could not be confirmed"
                )
            return {"eyecatch_present": True}

        wrapped = audit._audit_wrapper(original)
        with mock.patch.object(
            audit.base.note_base, "_find_title", return_value=object()
        ), mock.patch.object(
            proof,
            "collect_eyecatch_metrics",
            side_effect=[_present_header_metrics(), _ambiguous_metrics()],
        ) as collect:
            result = wrapped(_Page(), "private-title", "private-body")

        self.assertTrue(result["eyecatch_present"])
        self.assertEqual(result["eyecatch_proof_mode"], proof.PRESENT_HEADER_MEDIA)
        self.assertEqual(collect.call_count, 1)


if __name__ == "__main__":
    unittest.main()
