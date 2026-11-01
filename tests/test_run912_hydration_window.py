"""Run912: bounded hydration probe for exact existing note private draft.

No network, no real note browser and no model calls.
"""
from __future__ import annotations

import inspect
import sys
import types
import unittest
from unittest import mock
from pathlib import Path

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


class Page:
    url = "https://note.com/notes/EXACT_ID/edit"

    def __init__(self, fail=False):
        self.waits = []
        self.fail = fail

    def wait_for_timeout(self, value):
        self.waits.append(value)
        if self.fail:
            raise RuntimeError("SECRET_PRIVATE_CONTENT")


def sample(ready="loading", editables=0, shell="app_root_no_editables", size="small"):
    return {
        "title_probe_status": "observed",
        "title_probe_ready_state": ready,
        "title_probe_editable_visible": editables,
        "title_probe_shell_class": shell,
        "title_probe_body_size_class": size,
    }


def valid_metrics():
    return {
        "hydration_probe_status": "observed",
        "hydration_first_ready_state": "loading",
        "hydration_middle_ready_state": "complete",
        "hydration_final_ready_state": "complete",
        "hydration_first_shell_class": "app_root_no_editables",
        "hydration_final_shell_class": "other_editables",
        "hydration_first_body_size_class": "small",
        "hydration_final_body_size_class": "medium",
        "hydration_editables_transition": "appeared_later",
    }


class Run912HydrationTests(unittest.TestCase):
    def test_three_bounded_snapshots_without_navigation(self):
        page = Page()
        samples = [
            sample(),
            sample("interactive", 0, "main_no_editables", "medium"),
            sample("complete", 1, "other_editables", "medium"),
        ]
        with mock.patch.object(probe, "_hydration_snapshot", side_effect=samples) as capture:
            result = probe.observe_editor_hydration(page)
        self.assertEqual(page.waits, [2000, 3000])
        self.assertEqual(capture.call_count, 3)
        self.assertEqual(result["hydration_probe_status"], "observed")
        self.assertEqual(result["hydration_middle_ready_state"], "interactive")
        self.assertEqual(result["hydration_final_ready_state"], "complete")
        self.assertEqual(result["hydration_editables_transition"], "appeared_later")
        self.assertEqual(set(result), set(probe.HYDRATION_ALLOWED_FIELDS))

    def test_persistently_inert_shell_is_classified_not_treated_as_deleted_draft(self):
        page = Page()
        with mock.patch.object(probe, "_hydration_snapshot",
                               side_effect=[sample(), sample("complete"), sample("complete")]):
            metrics = probe.observe_editor_hydration(page)
        self.assertEqual(metrics["hydration_editables_transition"], "absent_throughout")
        self.assertEqual(metrics["hydration_final_shell_class"], "app_root_no_editables")
        self.assertNotIn("draft_deleted", repr(metrics))

    def test_invalid_snapshots_or_errors_fail_closed_without_leakage(self):
        for snapshots in [
            [sample(), {"title_probe_status": "unavailable"}],
            [sample(), sample(), {"title_probe_ready_state": "PRIVATE_BODY",
                                   "title_probe_status": "observed"}],
        ]:
            with self.subTest(snapshots=snapshots):
                with mock.patch.object(probe, "_hydration_snapshot", side_effect=snapshots):
                    metrics = probe.observe_editor_hydration(Page())
                self.assertEqual(metrics, {"hydration_probe_status": "unavailable"})
                self.assertNotIn("PRIVATE_BODY", repr(metrics))
        with mock.patch.object(probe, "_hydration_snapshot",
                               side_effect=[sample(), sample(), sample()]):
            self.assertEqual(probe.observe_editor_hydration(Page(fail=True)),
                             {"hydration_probe_status": "unavailable"})

    def test_hydration_snapshot_rejects_untrusted_fields_without_logging_content(self):
        class DomPage:
            def __init__(self, payload):
                self.payload = payload

            def evaluate(self, script):
                assert "textContent" not in script
                assert "innerHTML" not in script
                assert "document.cookie" not in script
                return self.payload

        raw = {"ready": "loading", "editables": 0, "main": 0,
               "roots": 1, "alerts": 0, "loaders": 0, "size": "small",
               "private_body": "UNPUBLISHED"}
        observed = probe._hydration_snapshot(DomPage(raw))
        self.assertEqual(observed["title_probe_shell_class"], "app_root_no_editables")
        self.assertNotIn("UNPUBLISHED", repr(observed))
        for key, value in [
            ("editables", "PRIVATE"), ("roots", True),
            ("loaders", 55), ("ready", "PRIVATE"),
            ("size", "PRIVATE"),
        ]:
            with self.subTest(key=key):
                malformed = dict(raw)
                malformed[key] = value
                self.assertIsNone(probe._hydration_snapshot(DomPage(malformed)))

    def test_reject_unknown_keys_invalid_enums_and_private_data(self):
        for key, value in [
            ("hydration_final_ready_state", "secret"),
            ("hydration_first_shell_class", "PRIVATE_EDITOR"),
            ("hydration_editables_transition", 1),
            ("hydration_final_body_size_class", True),
        ]:
            payload = valid_metrics()
            payload[key] = value
            self.assertEqual(probe._validated_hydration_metrics(payload),
                             {"hydration_probe_status": "unavailable"})
        payload = valid_metrics()
        payload["dom_text"] = "UNPUBLISHED_MANUSCRIPT"
        self.assertEqual(probe._validated_hydration_metrics(payload),
                         {"hydration_probe_status": "unavailable"})

    def test_hydration_rechecks_same_strict_title_gate_and_never_falls_back(self):
        page = Page()
        with mock.patch.object(audit, "_title_value", side_effect=[
            audit.note_base.NoteDraftError("not loaded"), "EXACT_PRIVATE_TITLE"
        ]) as strict, mock.patch.object(
            probe, "observe_editor_hydration", return_value=valid_metrics()
        ) as hydrated, mock.patch.object(
            audit.run187, "_is_editor_url", return_value=True
        ), mock.patch.object(
            probe, "_hydration_snapshot"
        ) as metrics:
            result = audit._read_title_with_diagnostics(page, "EXACT_PRIVATE_TITLE")
        self.assertEqual(result, "EXACT_PRIVATE_TITLE")
        self.assertEqual(strict.call_count, 2)
        hydrated.assert_called_once_with(page)
        metrics.assert_not_called()

    def test_persistently_missing_title_emits_safe_evidence_and_fails_closed(self):
        page = Page()
        with mock.patch.object(
            audit, "_title_value", side_effect=audit.note_base.NoteDraftError("missing")
        ) as strict, mock.patch.object(
            probe, "observe_editor_hydration", return_value=valid_metrics()
        ), mock.patch.object(
            audit.run187, "_is_editor_url", return_value=True
        ), mock.patch.object(
            probe, "_hydration_snapshot", return_value={"title_probe_status": "observed"}
        ):
            with self.assertRaises(audit.PrivateDraftAuditError) as error:
                audit._read_title_with_diagnostics(page, "SECRET_TITLE")
        self.assertEqual(str(error.exception), "Private draft title field unavailable")
        self.assertEqual(strict.call_count, 2)
        self.assertEqual(error.exception.safe_metrics["hydration_editables_transition"],
                         "appeared_later")
        self.assertNotIn("SECRET_TITLE", repr(error.exception.safe_metrics))

    def test_route_drift_is_fail_closed_before_second_title_lookup(self):
        page = Page()
        with mock.patch.object(audit, "_title_value",
                               side_effect=audit.note_base.NoteDraftError("missing")) as strict, mock.patch.object(
            probe, "observe_editor_hydration", return_value=valid_metrics()
        ), mock.patch.object(
            audit.run187, "_is_editor_url", return_value=False
        ):
            with self.assertRaises(audit.PrivateDraftAuditError):
                audit._read_title_with_diagnostics(page, "SECRET_TITLE")
        strict.assert_called_once()

    def test_probe_is_read_only_and_summary_allowlisted(self):
        src = inspect.getsource(probe.observe_editor_hydration)
        for disallowed in ("page.goto(", ".click(", ".fill(", ".press(", ".reload(",
                           ".screenshot(", ".innerHTML", ".outerHTML", ".url",
                           "document.cookie", "localStorage", "sessionStorage"):
            self.assertNotIn(disallowed, src)
        workflow = (Path(__file__).resolve().parents[1] /
                    ".github/workflows/note-private-draft-audit.yml").read_text(encoding="utf-8")
        for field in probe.HYDRATION_ALLOWED_FIELDS:
            self.assertIn(f"'{field}'", workflow)


if __name__ == "__main__":
    unittest.main()
