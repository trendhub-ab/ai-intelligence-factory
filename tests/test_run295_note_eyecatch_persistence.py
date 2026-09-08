from __future__ import annotations

import inspect
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    requests_stub = types.ModuleType("requests")
    requests_stub.Response = object
    requests_stub.RequestException = Exception
    requests_stub.request = lambda *args, **kwargs: None
    requests_stub.get = lambda *args, **kwargs: None
    requests_stub.post = lambda *args, **kwargs: None
    sys.modules["requests"] = requests_stub

import note_eyecatch_persistence as proof
import run295_note_private_draft_audit as audit

ROOT = Path(__file__).resolve().parents[1]


def present_header_metrics() -> dict[str, int | bool]:
    return {
        "eyecatch_exact_control_visible_count": 0,
        "image_add_control_visible_count": 0,
        "large_top_img_count": 1,
        "large_top_background_count": 0,
        "max_top_media_width": 620,
        "max_top_media_height": 325,
        "title_geometry_available": True,
    }


def missing_metrics() -> dict[str, int | bool]:
    return {
        "eyecatch_exact_control_visible_count": 0,
        "image_add_control_visible_count": 1,
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


class Run295SharedClassificationTests(unittest.TestCase):
    def test_legacy_visible_control_is_strong_presence_proof(self) -> None:
        metrics = {
            "eyecatch_exact_control_visible_count": 1,
            "image_add_control_visible_count": 0,
            "large_top_img_count": 0,
            "large_top_background_count": 0,
        }
        self.assertEqual(proof.classify_eyecatch_persistence(metrics), proof.PRESENT_LEGACY_CONTROL)
        self.assertTrue(proof.eyecatch_persistence_confirmed(metrics))

    def test_run294_production_shape_is_accepted_as_header_media_proof(self) -> None:
        metrics = present_header_metrics()
        self.assertEqual(proof.classify_eyecatch_persistence(metrics), proof.PRESENT_HEADER_MEDIA)
        self.assertTrue(proof.eyecatch_persistence_confirmed(metrics))

    def test_visible_add_image_control_without_media_fails_closed(self) -> None:
        metrics = missing_metrics()
        self.assertEqual(proof.classify_eyecatch_persistence(metrics), proof.MISSING_LIKELY)
        self.assertFalse(proof.eyecatch_persistence_confirmed(metrics))

    def test_no_media_and_no_controls_is_ambiguous_and_not_confirmed(self) -> None:
        metrics = {
            "eyecatch_exact_control_visible_count": 0,
            "image_add_control_visible_count": 0,
            "large_top_img_count": 0,
            "large_top_background_count": 0,
        }
        self.assertEqual(proof.classify_eyecatch_persistence(metrics), proof.AMBIGUOUS)
        self.assertFalse(proof.eyecatch_persistence_confirmed(metrics))


class Run295CreationGuardTests(unittest.TestCase):
    def _base(self):
        class FakeDraftError(RuntimeError):
            pass

        class FakeBase:
            NoteDraftError = FakeDraftError

            @staticmethod
            def _find_title(page):
                return object()

            @staticmethod
            def _save_draft_and_verify(page, title, manuscript, image_required=True):
                # Simulate the obsolete production check. A plain page with count()==0
                # would pass, while Run295's proxy exposes proof as one visible control.
                legacy = page.locator(proof.LEGACY_CONTROL_SELECTOR).first
                if legacy.count() and not legacy.is_visible(timeout=10):
                    raise FakeDraftError("legacy false negative")
                return "private-route-not-emitted"

        return FakeBase

    def test_header_media_proof_satisfies_legacy_check_and_postcondition(self) -> None:
        base = self._base()
        proof.install_creation_persistence_guard(base)
        with mock.patch.object(proof, "collect_eyecatch_metrics", return_value=present_header_metrics()):
            result = base._save_draft_and_verify(_Page(), "title", "body", image_required=True)
        self.assertEqual(result, "private-route-not-emitted")

    def test_count_zero_escape_hatch_is_closed_when_shared_proof_is_missing(self) -> None:
        base = self._base()
        proof.install_creation_persistence_guard(base)
        ambiguous = {
            "eyecatch_exact_control_visible_count": 0,
            "image_add_control_visible_count": 0,
            "large_top_img_count": 0,
            "large_top_background_count": 0,
        }
        with mock.patch.object(proof, "collect_eyecatch_metrics", return_value=ambiguous):
            with self.assertRaises(base.NoteDraftError):
                base._save_draft_and_verify(_Page(), "title", "body", image_required=True)

    def test_install_is_idempotent(self) -> None:
        base = self._base()
        proof.install_creation_persistence_guard(base)
        once = base._save_draft_and_verify
        proof.install_creation_persistence_guard(base)
        self.assertIs(base._save_draft_and_verify, once)


class Run295AuditIntegrationTests(unittest.TestCase):
    def test_audit_wrapper_translates_shared_proof_into_legacy_contract(self) -> None:
        seen: dict[str, bool] = {}

        def original(page, title, manuscript):
            legacy = page.locator(proof.LEGACY_CONTROL_SELECTOR).first
            seen["legacy_visible"] = bool(legacy.count() and legacy.is_visible())
            return {"eyecatch_present": seen["legacy_visible"]}

        wrapped = audit._audit_wrapper(original)
        with mock.patch.object(audit.base.note_base, "_find_title", return_value=object()), mock.patch.object(
            proof, "collect_eyecatch_metrics", return_value=present_header_metrics()
        ):
            result = wrapped(_Page(), "private-title", "private-body")
        self.assertTrue(seen["legacy_visible"])
        self.assertTrue(result["eyecatch_present"])
        self.assertEqual(result["eyecatch_proof_mode"], proof.PRESENT_HEADER_MEDIA)
        self.assertEqual(result["max_top_media_width"], 620)

    def test_audit_wrapper_rejects_missing_before_old_selector_can_pass(self) -> None:
        wrapped = audit._audit_wrapper(lambda page, title, manuscript: {"unexpected": True})
        with mock.patch.object(audit.base.note_base, "_find_title", return_value=object()), mock.patch.object(
            proof, "collect_eyecatch_metrics", return_value=missing_metrics()
        ):
            with self.assertRaises(audit.Run295EyecatchProofError) as ctx:
                wrapped(_Page(), "private-title", "private-body")
        self.assertEqual(ctx.exception.code, "eyecatch_missing_likely")

    def test_run_restores_original_audit_on_failure(self) -> None:
        original_audit = audit.base._audit_current_page
        original_run = audit.base292.run

        def sentinel(*args, **kwargs):
            raise audit.base.PrivateDraftAuditError("sentinel")

        audit.base292.run = sentinel
        try:
            with self.assertRaises(audit.base.PrivateDraftAuditError):
                audit.run(confirm="AUDIT_NOTE_DRAFT", sync_id="a" * 32)
            self.assertIs(audit.base._audit_current_page, original_audit)
        finally:
            audit.base292.run = original_run
            audit.base._audit_current_page = original_audit


class Run295SafetyBoundaryTests(unittest.TestCase):
    def test_shared_helper_never_reads_image_src_dom_html_or_unpublished_text(self) -> None:
        source = inspect.getsource(proof)
        for forbidden in (
            "getAttribute('src')",
            'getAttribute("src")',
            ".currentSrc",
            ".outerHTML",
            ".innerHTML",
            "actual_text",
            "expected_text",
            "page.screenshot(",
            ".click(",
            ".fill(",
            "set_input_files(",
            "requests.post(",
            "generate_content",
            "publish_note",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_read_only_audit_entrypoint_has_no_mutation_model_or_public_release_surface(self) -> None:
        source = inspect.getsource(audit)
        for forbidden in (
            ".click(",
            ".fill(",
            "set_input_files(",
            "page.screenshot(",
            "requests.post(",
            "requests.patch(",
            "_upload_header_image(",
            "_save_draft_and_verify(",
            "_mark_draft_created(",
            "generate_content",
            "publish_note",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_canonical_run194_installs_shared_creation_guard(self) -> None:
        source = (ROOT / "run194_note_persistent_cloud.py").read_text(encoding="utf-8")
        self.assertIn("import note_eyecatch_persistence as eyecatch_persistence", source)
        self.assertIn("eyecatch_persistence.install_creation_persistence_guard(cloud.base)", source)


if __name__ == "__main__":
    unittest.main()
