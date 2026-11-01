"""Run908: provider-free falsification of private editor title surface diagnostics."""
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
    stub = types.ModuleType("requests")
    stub.Response = object
    stub.RequestException = Exception
    stub.request = lambda *args, **kwargs: None
    stub.get = lambda *args, **kwargs: None
    stub.post = lambda *args, **kwargs: None
    sys.modules["requests"] = stub

import note_editor_title_surface as surface
import run291_note_private_draft_audit as audit
import run292_note_rendered_body_audit as audit292

ROOT = Path(__file__).resolve().parents[1]
SECRET = "SECRET_UNPUBLISHED_TITLE"


def sample_metrics() -> dict[str, object]:
    data: dict[str, object] = {
        "title_probe_ready_state": "complete",
        "title_probe_body_size_class": "large",
    }
    for key in surface._COUNT_KEYS:
        data[key] = 0
    data["title_probe_editable_visible"] = 2
    data["title_probe_exact_leaf_visible"] = 1
    return data


class FakePage:
    def __init__(self, answer: object = None, error: Exception | None = None):
        self.answer = sample_metrics() if answer is None else answer
        self.error = error
        self.args = None

    def evaluate(self, code, args):
        self.args = args
        if self.error:
            raise self.error
        return self.answer


class Run908TitleSurfaceTests(unittest.TestCase):
    def test_read_only_observation_returns_only_bounded_fixed_keys(self):
        page = FakePage()
        result = surface.collect_title_surface_metrics(page, SECRET)
        self.assertEqual(result["title_probe_status"], "observed")
        self.assertEqual(result["title_probe_exact_leaf_visible"], 1)
        self.assertEqual(result["title_probe_ready_state"], "complete")
        self.assertEqual(set(result), set(surface._COUNT_KEYS) | {
            "title_probe_status", "title_probe_ready_state",
            "title_probe_body_size_class", "title_probe_navigation_status",
            "title_probe_shell_class",
        })
        self.assertEqual(result["title_probe_navigation_status"], "no_response")
        self.assertEqual(result["title_probe_shell_class"], "other_editables")
        self.assertEqual(page.args[0], SECRET)
        self.assertNotIn(SECRET, repr(result))

    def test_extra_private_fields_are_never_exported(self):
        payload = sample_metrics()
        payload["title"] = SECRET
        payload["draft_url"] = "https://note.com/notes/private/edit"
        payload["dom_html"] = "<div>private</div>"
        result = surface.collect_title_surface_metrics(FakePage(payload), SECRET)
        self.assertNotIn(SECRET, repr(result))
        self.assertNotIn("private", repr(result))
        self.assertNotIn("dom_html", result)

    def test_bad_types_and_unknown_document_state_fail_closed(self):
        for key, value in [
            ("title_probe_editable_visible", "3"),
            ("title_probe_editable_visible", True),
            ("title_probe_editable_visible", -1),
            ("title_probe_editable_visible", 21),
            ("title_probe_ready_state", "secret-state"),
            ("title_probe_body_size_class", "private-state"),
        ]:
            with self.subTest(key=key, value=value):
                payload = sample_metrics()
                payload[key] = value
                result = surface.collect_title_surface_metrics(FakePage(payload), SECRET)
                self.assertEqual(result["title_probe_status"], "unavailable")
                self.assertNotIn("title_probe_editable_visible", result)

    def test_invalid_shapes_and_browser_exception_are_fail_closed(self):
        for page in (
            FakePage(answer="secret private DOM"),
            FakePage(answer=[]),
            FakePage(error=RuntimeError("secret session token")),
        ):
            result = surface.collect_title_surface_metrics(page, SECRET)
            self.assertEqual(result, {
                "title_probe_status": "unavailable",
                "title_probe_ready_state": "unknown",
            })

    def test_missing_title_raises_fixed_error_with_probe_only_as_evidence(self):
        with mock.patch.object(
            audit, "_title_value",
            side_effect=audit.note_base.NoteDraftError("note title field was not found"),
        ), mock.patch.object(
            audit.title_surface, "collect_title_surface_metrics",
            return_value={"title_probe_status": "observed", "title_probe_ready_state": "complete"},
        ) as probe:
            with self.assertRaises(audit.PrivateDraftAuditError) as ctx:
                audit._read_title_with_diagnostics(object(), SECRET)
        self.assertEqual(str(ctx.exception), "Private draft title field unavailable")
        self.assertEqual(ctx.exception.safe_metrics["title_probe_status"], "observed")
        self.assertEqual(
            audit292._safe_non_body_guard_code(ctx.exception),
            "editor_title_field_unavailable",
        )
        probe.assert_called_once()

    def test_other_read_failures_stay_strict_and_never_use_probe_as_fallback(self):
        with mock.patch.object(
            audit, "_title_value",
            side_effect=audit.PrivateDraftAuditError("Could not read the private draft title"),
        ), mock.patch.object(
            audit.title_surface, "collect_title_surface_metrics"
        ) as probe:
            with self.assertRaises(audit.PrivateDraftAuditError) as ctx:
                audit._read_title_with_diagnostics(object(), SECRET)
        self.assertEqual(str(ctx.exception), "Could not read the private draft title")
        probe.assert_not_called()

    def test_read_only_boundary_and_verified_route_are_preserved(self):
        code = inspect.getsource(surface)
        run = inspect.getsource(audit._browser_audit)
        self.assertIn('page, str(article["title"]), navigation_response=editor_response', run)
        self.assertLess(run.index("run190._assert_expected_note_account(page)"),
                        run.index("persisted_title = _read_title_with_diagnostics("))
        self.assertLess(run.index("run190._verify_draft_in_article_list(page, private_url"),
                        run.index("persisted_title = _read_title_with_diagnostics("))
        for forbidden in (
            ".click(", ".fill(", "set_input_files(", ".screenshot(",
            "requests.post(", ".innerHTML", ".outerHTML", ".currentSrc",
            "localStorage", "sessionStorage", "document.cookie",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, code)
        self.assertNotIn("return _", inspect.getsource(audit._read_title_with_diagnostics).split("except")[1])

    def test_workflow_summary_contains_only_fixed_observation_fields(self):
        workflow = (ROOT / ".github/workflows/note-private-draft-audit.yml").read_text(encoding="utf-8")
        self.assertIn("'title_probe_ready_state'", workflow)
        self.assertIn("'title_probe_exact_leaf_visible'", workflow)
        self.assertIn("'title_probe_status'", workflow)
        self.assertNotIn("raw_dom", workflow)
        self.assertNotIn("unpublished_title", workflow)


if __name__ == "__main__":
    unittest.main()
