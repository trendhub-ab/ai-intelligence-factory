from __future__ import annotations

import json
import sys
import types
import unittest
from contextlib import contextmanager
from unittest import mock

import run291_note_private_draft_audit as base
import run292_note_rendered_body_audit as audit292
import run295_note_private_draft_audit as audit295


class _FakePage:
    def __init__(self) -> None:
        self.url = "https://editor.note.com/notes/private-secret/edit"

    def goto(self, *args, **kwargs):
        return None

    def wait_for_timeout(self, *args, **kwargs):
        return None

    def set_default_timeout(self, *args, **kwargs):
        return None


class _FakeContext:
    def __init__(self) -> None:
        self.page = _FakePage()

    def new_page(self):
        return self.page

    def close(self):
        return None


class _FakePlaywrightManager:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


@contextmanager
def _fake_playwright_import():
    """Provide only the lazy import surface Run291 needs; install no browser dependency."""
    package = types.ModuleType("playwright")
    package.__path__ = []
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = lambda: _FakePlaywrightManager()
    package.sync_api = sync_api
    with mock.patch.dict(
        sys.modules,
        {"playwright": package, "playwright.sync_api": sync_api},
    ):
        yield


class P0AHistoryDiagnosticContractTests(unittest.TestCase):
    def test_history_match_failure_carries_only_integer_stage_counts(self) -> None:
        article = {
            "title": "PRIVATE-TITLE-SENTINEL",
            "manuscript": "PRIVATE-BODY-SENTINEL",
        }
        candidates = [
            "https://editor.note.com/notes/private-route-one/edit",
            "https://editor.note.com/notes/private-route-two/edit",
        ]
        fake_context = _FakeContext()

        with _fake_playwright_import(), \
             mock.patch.object(base, "_recent_private_edit_urls", return_value=candidates), \
             mock.patch.object(base.run190, "_profile_dir", return_value=object()), \
             mock.patch.object(base.run190, "_launch_persistent_context", return_value=fake_context), \
             mock.patch.object(base.note_base, "_looks_logged_out", return_value=False), \
             mock.patch.object(base.run187, "_is_editor_url", return_value=True), \
             mock.patch.object(base, "_title_value", return_value="OTHER PRIVATE TITLE"):
            with self.assertRaises(base.PrivateDraftAuditError) as caught:
                base._browser_audit(article)

        metrics = caught.exception.safe_metrics
        self.assertEqual(metrics["history_candidate_count"], 2)
        self.assertEqual(metrics["history_navigation_success_count"], 2)
        self.assertEqual(metrics["history_navigation_error_count"], 0)
        self.assertEqual(metrics["history_authenticated_count"], 2)
        self.assertEqual(metrics["history_editor_route_count"], 2)
        self.assertEqual(metrics["history_title_read_count"], 2)
        self.assertEqual(metrics["history_title_match_count"], 0)
        self.assertTrue(all(isinstance(value, int) for value in metrics.values()))
        serialized = json.dumps(metrics, ensure_ascii=False)
        for secret in (
            "PRIVATE-TITLE-SENTINEL",
            "PRIVATE-BODY-SENTINEL",
            "private-route-one",
            "private-route-two",
            "OTHER PRIVATE TITLE",
        ):
            self.assertNotIn(secret, serialized)

    def test_no_history_failure_carries_zero_candidate_count(self) -> None:
        with _fake_playwright_import(), \
             mock.patch.object(base, "_recent_private_edit_urls", return_value=[]), \
             mock.patch.object(base.run190, "_profile_dir", return_value=object()):
            with self.assertRaises(base.PrivateDraftAuditError) as caught:
                base._browser_audit({"title": "PRIVATE", "manuscript": "PRIVATE"})
        self.assertEqual(caught.exception.safe_metrics, {"history_candidate_count": 0})

    def test_run292_generic_base_failure_preserves_safe_metrics_only(self) -> None:
        exc = base.PrivateDraftAuditError(
            "The requested private draft could not be matched safely from local Chrome history",
            safe_metrics={
                "history_candidate_count": 3,
                "history_title_match_count": 0,
            },
        )
        result = audit292._safe_failure_result(
            "a" * 32,
            audit292._safe_non_body_guard_code(exc),
            exc.safe_metrics,
        )
        self.assertEqual(result["history_candidate_count"], 3)
        self.assertEqual(result["history_title_match_count"], 0)

    def test_run295_generic_base_failure_can_forward_same_safe_metrics(self) -> None:
        exc = base.PrivateDraftAuditError(
            "The requested private draft could not be matched safely from local Chrome history",
            safe_metrics={"history_candidate_count": 4},
        )
        result = audit295._safe_failure_result(
            "b" * 32,
            audit292._safe_non_body_guard_code(exc),
            exc.safe_metrics,
        )
        self.assertEqual(result["history_candidate_count"], 4)


if __name__ == "__main__":
    unittest.main()
