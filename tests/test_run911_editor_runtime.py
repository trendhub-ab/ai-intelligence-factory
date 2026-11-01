"""Run911: zero-network privacy and ordering tests for passive editor runtime evidence."""
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

import note_editor_title_surface as surface
import run291_note_private_draft_audit as audit


class FakeEmitter:
    def __init__(self, fail_event=None):
        self.handlers = {}
        self.fail_event = fail_event
        self.removed = []

    def on(self, name, handler):
        if name == self.fail_event:
            raise RuntimeError("PRIVATE-SENSITIVE-STATE")
        self.handlers[name] = handler

    def remove_listener(self, name, handler):
        self.removed.append(name)
        self.handlers.pop(name, None)

    def emit(self, name, value):
        callback = self.handlers.get(name)
        if callback:
            callback(value)


class _Request:
    def __init__(self, resource_type, secret="unpublished"):
        self.resource_type = resource_type
        self.url = f"https://note.com/notes/{secret}/edit"
        self.post_data = secret


class _Response:
    def __init__(self, status, resource_type, secret="unpublished"):
        self.status = status
        self.request = _Request(resource_type, secret)
        self.headers = {"x-private": secret}
        self.url = f"https://note.com/notes/{secret}"


class _Console:
    def __init__(self, kind):
        self.type = kind
        self.text = "PRIVATE_ARTICLE_BODY"
        self.location = {"url": "https://note.com/secret"}


class Run911EditorRuntimeEvidenceTests(unittest.TestCase):
    def test_passive_counters_are_fixed_and_do_not_emit_unpublished_content(self):
        page = FakeEmitter()
        evidence = surface.EditorRuntimeObservation()
        evidence.attach(page)
        page.emit("pageerror", RuntimeError("PRIVATE_TITLE_AND_SESSION"))
        page.emit("console", _Console("error"))
        page.emit("console", _Console("warning"))
        page.emit("requestfailed", _Request("script", "PRIVATE_DRAFT_ID"))
        page.emit("requestfailed", _Request("xhr"))
        page.emit("requestfailed", _Request("image"))
        page.emit("response", _Response(403, "fetch", "PRIVATE_BODY"))
        page.emit("response", _Response(503, "script"))
        page.emit("response", _Response(200, "script"))
        page.emit("response", _Response(201, "xhr"))
        page.emit("crash", "PRIVATE_CAUSE")
        result = evidence.safe_metrics()
        self.assertEqual(result["runtime_probe_status"], "observed")
        self.assertEqual(result["runtime_page_error_count"], 1)
        self.assertEqual(result["runtime_console_error_count"], 1)
        self.assertEqual(result["runtime_failed_script_count"], 1)
        self.assertEqual(result["runtime_failed_fetch_count"], 1)
        self.assertEqual(result["runtime_failed_other_count"], 1)
        self.assertEqual(result["runtime_http_403_count"], 1)
        self.assertEqual(result["runtime_http_5xx_count"], 1)
        self.assertEqual(result["runtime_script_http_error_count"], 1)
        self.assertEqual(result["runtime_fetch_http_error_count"], 1)
        self.assertEqual(result["runtime_script_success_count"], 1)
        self.assertEqual(result["runtime_fetch_success_count"], 1)
        self.assertEqual(result["runtime_page_crash_count"], 1)
        self.assertEqual(set(result), {"runtime_probe_status", *surface._RUNTIME_COUNTERS})
        for secret in ("PRIVATE_TITLE_AND_SESSION", "PRIVATE_DRAFT_ID", "PRIVATE_BODY",
                       "PRIVATE_ARTICLE_BODY", "PRIVATE_CAUSE"):
            self.assertNotIn(secret, repr(result))
        evidence.detach()
        self.assertEqual(page.handlers, {})
        self.assertEqual(len(page.removed), 5)

    def test_resource_categories_and_invalid_response_types_fail_closed(self):
        page = FakeEmitter()
        evidence = surface.EditorRuntimeObservation()
        evidence.attach(page)
        page.emit("requestfailed", _Request("document"))
        page.emit("response", _Response(404, "document"))
        page.emit("response", _Response("503", "script"))
        page.emit("response", _Response(True, "script"))
        page.emit("response", _Response(700, "script"))
        result = evidence.safe_metrics()
        self.assertEqual(result["runtime_failed_document_count"], 1)
        self.assertEqual(result["runtime_document_http_error_count"], 1)
        self.assertEqual(result["runtime_http_404_count"], 1)
        self.assertEqual(result["runtime_http_5xx_count"], 0)
        evidence.detach()

    def test_partial_listener_failure_never_claims_observed_and_detaches(self):
        page = FakeEmitter(fail_event="requestfailed")
        evidence = surface.EditorRuntimeObservation()
        evidence.attach(page)
        self.assertEqual(evidence.safe_metrics(), {"runtime_probe_status": "unavailable"})
        evidence.detach()
        self.assertEqual(page.handlers, {})

    def test_many_events_are_capped_and_unknown_payload_is_never_serialized(self):
        page = FakeEmitter()
        evidence = surface.EditorRuntimeObservation()
        evidence.attach(page)
        for _ in range(60):
            page.emit("pageerror", RuntimeError("SENSITIVE"))
            page.emit("response", _Response(503, "script"))
        result = evidence.safe_metrics()
        self.assertEqual(result["runtime_page_error_count"], 20)
        self.assertEqual(result["runtime_http_5xx_count"], 20)
        self.assertEqual(result["runtime_script_http_error_count"], 20)

    def test_title_failure_still_raises_and_only_fixed_count_fields_are_accepted(self):
        class FakeEvidence:
            def safe_metrics(self):
                return {
                    "runtime_probe_status": "observed",
                    "runtime_page_error_count": 2,
                    "runtime_fetch_success_count": 1,
                    "runtime_console_error_count": "SECRET",
                    "runtime_http_401_count": 999,
                    "private_url": "https://note.com/notes/PRIVATE_ID/edit",
                    "title": "PRIVATE_TITLE",
                }
        with patch.object(
            audit, "_title_value",
            side_effect=audit.note_base.NoteDraftError("note title field was not found"),
        ), patch.object(
            audit.title_surface, "collect_title_surface_metrics",
            return_value={"title_probe_status": "observed"},
        ):
            with self.assertRaises(audit.PrivateDraftAuditError) as cm:
                audit._read_title_with_diagnostics(
                    object(), "PRIVATE_TITLE", runtime_probe=FakeEvidence()
                )
        self.assertEqual(str(cm.exception), "Private draft title field unavailable")
        metrics = cm.exception.safe_metrics
        self.assertEqual(metrics["runtime_page_error_count"], 2)
        self.assertEqual(metrics["runtime_fetch_success_count"], 1)
        self.assertNotIn("runtime_console_error_count", metrics)
        self.assertNotIn("runtime_http_401_count", metrics)
        self.assertNotIn("private_url", metrics)
        self.assertNotIn("title", metrics)
        self.assertNotIn("PRIVATE_TITLE", repr(metrics))

    def test_listener_scope_only_after_official_list_and_cleanup_guaranteed(self):
        src = inspect.getsource(audit._browser_audit)
        self.assertLess(src.index("run190._verify_draft_in_article_list(page"),
                        src.index("runtime_probe.attach(page)"))
        self.assertLess(src.index("runtime_probe.attach(page)"),
                        src.index("editor_response = page.goto(private_url"))
        self.assertIn("runtime_probe.detach()", src)
        self.assertLess(src.index("runtime_probe.detach()"), src.index("context.close()"))
        self.assertIn('if not run187._is_editor_url(str(page.url or "")):', src)

    def test_no_mutating_browser_actions_or_private_logging_in_module(self):
        src = inspect.getsource(surface.EditorRuntimeObservation)
        for forbidden in (
            ".click(", ".fill(", ".screenshot(", "getAttribute(", ".innerHTML",
            ".outerHTML", ".currentSrc", "localStorage", "sessionStorage",
            "document.cookie", ".headers", ".url", ".text(",
            "requests.post(", "publish_note", "generate_content",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, src)
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/note-private-draft-audit.yml").read_text(encoding="utf-8")
        self.assertIn("'runtime_page_error_count'", workflow)
        self.assertIn("'runtime_failed_script_count'", workflow)
        self.assertIn("'runtime_script_http_error_count'", workflow)


if __name__ == "__main__":
    unittest.main()
