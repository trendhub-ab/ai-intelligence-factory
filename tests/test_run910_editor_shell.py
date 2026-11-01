"""Run910: zero-provider falsification of private note editor shell categorization."""
from __future__ import annotations

import inspect
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import requests  # noqa: F401
except ModuleNotFoundError:
    stub = types.ModuleType("requests")
    stub.Response = object
    stub.RequestException = Exception
    stub.request = lambda *args, **kwargs: None
    stub.get = lambda *args, **kwargs: None
    stub.post = lambda *args, **kwargs: None
    sys.modules["requests"] = stub

import note_editor_title_surface as probe
import run291_note_private_draft_audit as audit


class FakeResponse:
    def __init__(self, status):
        self.status = status


class FakePage:
    def __init__(self, payload, error=None):
        self.payload = payload
        self.error = error
        self.query = None

    def evaluate(self, js, args):
        self.query = js
        if self.error:
            raise self.error
        return self.payload


def snapshot():
    result = {k: 0 for k in probe._COUNT_KEYS}
    result["title_probe_ready_state"] = "complete"
    result["title_probe_body_size_class"] = "small"
    result["title_probe_body_elements"] = 20
    result["title_probe_script_count"] = 7
    return result


class Run910ShellContractTests(unittest.TestCase):
    def test_http_response_categories_are_allowlisted_and_exact(self):
        cases = [
            (None, "no_response"),
            (FakeResponse(200), "http_2xx"),
            (FakeResponse(302), "http_3xx"),
            (FakeResponse(401), "http_401"),
            (FakeResponse(403), "http_403"),
            (FakeResponse(404), "http_404"),
            (FakeResponse(429), "http_4xx_other"),
            (FakeResponse(503), "http_5xx"),
            (FakeResponse(True), "unknown"),
            (FakeResponse("200"), "unknown"),
            (FakeResponse(999), "unknown"),
        ]
        for response, expected in cases:
            with self.subTest(response=repr(response), expected=expected):
                self.assertEqual(probe.navigation_status_category(response), expected)

    def test_untrusted_response_cannot_leak_headers_url_or_body(self):
        class Malicious:
            status = 403
            url = "https://note.com/notes/private-secret/edit"
            headers = {"Cookie": "private-secret"}
            text = "unpublished-body"
        result = probe.collect_title_surface_metrics(
            FakePage(snapshot()), "PRIVATE-TITLE", navigation_response=Malicious()
        )
        self.assertEqual(result["title_probe_navigation_status"], "http_403")
        self.assertNotIn("private-secret", repr(result))
        self.assertNotIn("unpublished", repr(result))
        self.assertNotIn("PRIVATE-TITLE", repr(result))

    def test_shell_state_is_observation_not_a_success_bypass(self):
        cases = [
            ({"title_probe_alert_visible": 1}, "alert_marker"),
            ({"title_probe_loading_visible": 1}, "loading_marker"),
            ({"title_probe_editable_visible": 1}, "other_editables"),
            ({"title_probe_app_root_count": 1}, "app_root_no_editables"),
            ({"title_probe_main_visible": 1}, "main_no_editables"),
            ({}, "no_visible_editor_markers"),
        ]
        for extras, expected in cases:
            with self.subTest(expected=expected):
                metrics = snapshot()
                metrics.update(extras)
                result = probe.collect_title_surface_metrics(
                    FakePage(metrics), "PRIVATE-TITLE", navigation_response=FakeResponse(200)
                )
                self.assertEqual(result["title_probe_shell_class"], expected)
                self.assertEqual(result["title_probe_navigation_status"], "http_2xx")
                self.assertNotIn("audit_passed", repr(result))

    def test_invalid_shell_bucket_or_numeric_metrics_fail_closed(self):
        for update in [
            {"title_probe_body_size_class": "private"},
            {"title_probe_script_count": "7"},
            {"title_probe_script_count": 22},
            {"title_probe_app_root_count": True},
            {"title_probe_alert_visible": -1},
        ]:
            with self.subTest(update=update):
                metrics = snapshot()
                metrics.update(update)
                result = probe.collect_title_surface_metrics(FakePage(metrics), "SECRET")
                self.assertEqual(result, {
                    "title_probe_status": "unavailable",
                    "title_probe_ready_state": "unknown",
                })

    def test_exception_text_is_not_exported(self):
        page = FakePage(snapshot(), error=RuntimeError(
            "token=PRIVATE_TOKEN https://note.com/notes/private/edit"
        ))
        result = probe.collect_title_surface_metrics(page, "SECRET")
        self.assertEqual(result["title_probe_status"], "unavailable")
        self.assertNotIn("PRIVATE_TOKEN", repr(result))

    def test_instrumentation_only_after_owner_and_official_list_proof(self):
        src = inspect.getsource(audit._browser_audit)
        account = src.index("run190._assert_expected_note_account(page)")
        official_list = src.index("run190._verify_draft_in_article_list(page")
        navigate = src.index("editor_response = page.goto(private_url")
        diagnose = src.index("navigation_response=editor_response")
        self.assertLess(account, official_list)
        self.assertLess(official_list, navigate)
        self.assertLess(navigate, diagnose)
        self.assertIn('if not run187._is_editor_url(str(page.url or "")):', src)
        self.assertIn("persisted_title != str(article", src)

    def test_title_failure_remains_a_hard_stop_with_only_diagnostics(self):
        page = object()
        observed = {"title_probe_navigation_status": "http_5xx"}
        with patch.object(
            audit, "_title_value",
            side_effect=audit.note_base.NoteDraftError("note title field was not found"),
        ), patch.object(
            audit.title_surface, "collect_title_surface_metrics", return_value=observed
        ) as collect:
            with self.assertRaises(audit.PrivateDraftAuditError) as caught:
                audit._read_title_with_diagnostics(
                    page, "SECRET", navigation_response=FakeResponse(503)
                )
        self.assertEqual(str(caught.exception), "Private draft title field unavailable")
        self.assertEqual(caught.exception.safe_metrics, observed)
        collect.assert_called_once()
        self.assertEqual(collect.call_args.kwargs["navigation_response"].status, 503)

    def test_no_mutation_or_raw_private_data_telemetry(self):
        src = inspect.getsource(probe)
        for forbidden in (
            ".click(", ".fill(", ".press(", ".screenshot(",
            "getAttribute('src')", ".outerHTML", ".innerHTML",
            ".currentSrc", "document.cookie", "localStorage", "sessionStorage",
            "fetch(", "XMLHttpRequest", ".headers", ".url", ".text(",
            "set_input_files(", "requests.post(", "publish_note", "generate_content",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, src)
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/note-private-draft-audit.yml").read_text(encoding="utf-8")
        for marker in (
            "'title_probe_navigation_status'", "'title_probe_shell_class'",
            "'title_probe_body_size_class'", "'title_probe_app_root_count'",
            "'title_probe_alert_visible'",
        ):
            self.assertIn(marker, workflow)


if __name__ == "__main__":
    unittest.main()
