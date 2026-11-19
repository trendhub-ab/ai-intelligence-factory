"""No-provider tests for one historical note edit-route read-only proof."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import inspect
import json
import sqlite3
from tempfile import TemporaryDirectory
import unittest

import run_v04_historical_edit_proof as proof
import run_v04_note_single_draft_bridge as bridge


class FakeRequest:
    def __init__(self, method):
        self.method = method


class FakeRoute:
    def __init__(self, method):
        self.request = FakeRequest(method)
        self.continued = False
        self.aborted = False
    def continue_(self):
        self.continued = True
    def abort(self):
        self.aborted = True


class V04EditHistoryProofTests(unittest.TestCase):
    def test_only_exact_note_edit_url_is_eligible(self):
        good = "https://editor.note.com/notes/nabc123/edit"
        self.assertEqual(proof._valid_edit_url(good), good)
        for bad in (
            "http://note.com/notes/nabc123/edit",
            "https://evil-note.com/notes/nabc123/edit",
            "https://note.com/notes/new",
            "https://note.com/notes/nabc123",
            "https://note.com/notes/nabc123/edit?token=private",
            "https://note.com/notes/nabc123/edit#frag",
            "https://note.com/notes/nabc123/edit/foo",
            "https://note.com:8080/notes/nabc123/edit",
            "https://note.com/notes/with%2Fslash/edit",
            "https://admin:secret@note.com/notes/nabc123/edit",
            "",
        ):
            with self.subTest(url=bad):
                self.assertIsNone(proof._valid_edit_url(bad))

    def test_history_extracts_exactly_one_unique_candidate_without_returning_content(self):
        with TemporaryDirectory() as td:
            profile = Path(td) / "Default"
            profile.mkdir()
            db = sqlite3.connect(str(profile / "History"))
            db.executescript(
                "CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT);"
                "CREATE TABLE visits (url INTEGER, visit_time INTEGER);"
            )
            when = datetime.now(timezone.utc) - timedelta(hours=5)
            epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
            now_tick = int((when - epoch).total_seconds() * 1e6)
            old_tick = int((when - timedelta(minutes=8) - epoch).total_seconds() * 1e6)
            entries = [
                ("https://note.com/notes/new", now_tick),
                ("https://editor.note.com/notes/nredacted123/edit", now_tick),
                ("https://note.com/notes/nredacted123/edit", now_tick),
                ("https://evil.test/notes/nbad/edit", now_tick),
                ("https://note.com/notes/nold/edit", old_tick),
            ]
            for index, (url, tick) in enumerate(entries, 1):
                db.execute("INSERT INTO urls VALUES (?, ?)", (index, url))
                db.execute("INSERT INTO visits VALUES (?, ?)", (index, tick))
            db.commit()
            code, urls = proof._history_candidates(when.isoformat(), profile_dir=Path(td))
            self.assertEqual(code, "ONE")
            self.assertEqual(len(urls), 1)
            self.assertIn("nredacted123", urls[0])
            report = proof.investigate(
                when.isoformat(), "title", "body",
                history_reader=lambda _: (code, urls),
                editor_reader=lambda *args: {
                    "history_edit_route": "EDITOR_ROUTE_OPENED",
                    "history_edit_title": "MATCH",
                    "history_edit_body": "EMPTY",
                },
            )
            self.assertEqual(report["history_edit_candidate"], "ONE")
            self.assertEqual(report["history_edit_body"], "EMPTY")
            self.assertNotIn("nredacted123", json.dumps(report))
            db.execute("INSERT INTO urls VALUES (?, ?)",
                       (8, "https://note.com/notes/nanother/edit"))
            db.execute("INSERT INTO visits VALUES (?, ?)", (8, now_tick))
            db.commit()
            code2, urls2 = proof._history_candidates(
                when.isoformat(), profile_dir=Path(td))
            self.assertEqual((code2, urls2), ("MULTIPLE", []))
            db.close()

    def test_unavailable_and_invalid_history_timestamps_fail_closed(self):
        with TemporaryDirectory() as td:
            self.assertEqual(proof._history_candidates(
                "not-a-time", profile_dir=Path(td)), ("UNAVAILABLE", []))
            self.assertEqual(proof._history_candidates(
                "2026-11-18T20:00:00", profile_dir=Path(td)), ("UNAVAILABLE", []))
            self.assertEqual(proof._history_candidates(
                "2026-11-18T20:00:00+00:00", profile_dir=Path(td)),
                ("UNAVAILABLE", []))

    def test_network_mutations_blocked(self):
        for method in ("GET", "HEAD", "OPTIONS"):
            with self.subTest(method=method):
                r = FakeRoute(method)
                proof._only_get(r)
                self.assertTrue(r.continued)
                self.assertFalse(r.aborted)
        for method in ("POST", "PATCH", "PUT", "DELETE", "TRACE"):
            with self.subTest(method=method):
                r = FakeRoute(method)
                proof._only_get(r)
                self.assertTrue(r.aborted)
                self.assertFalse(r.continued)

    def test_body_classification_without_payload_exposure(self):
        self.assertEqual(proof._classify_body("expected body", ""), "EMPTY")
        self.assertEqual(proof._classify_body("expected body", "expected body"), "EXACT")
        self.assertEqual(
            proof._classify_body("A" * 200, "A" * 60), "PREFIX_ONLY")
        self.assertEqual(proof._classify_body("expected", "completely different"), "OTHER")
        self.assertEqual(proof._classify_body("", "some text"), "UNINSPECTABLE")

    def test_multiple_history_routes_do_not_open_website(self):
        for status in ("MULTIPLE", "NONE", "UNAVAILABLE"):
            with self.subTest(status=status):
                result = proof.investigate(
                    "2026-11-18T11:00:00+00:00", "title", "private",
                    history_reader=lambda _: (status, []),
                    editor_reader=lambda *_: self.fail("must not open ambiguous route"),
                )
                self.assertEqual(result["history_edit_candidate"], status)
                self.assertEqual(result["history_edit_route"], "NOT_CHECKED")

    def test_probe_blocks_invalid_or_unsanitized_data(self):
        url = "https://note.com/notes/nprior/edit"
        for reply in (
            {"history_edit_route": url},
            {"history_edit_route": "EDITOR_ROUTE_OPENED", "history_edit_title": "MATCH",
             "history_edit_body": "PRIVATE_ARTICLE_TEXT"},
            {"history_edit_route": "NO_VERIFIED_EDITOR", "history_edit_title": "MATCH",
             "history_edit_body": "NOT_CHECKED"},
        ):
            with self.subTest(reply=reply):
                with self.assertRaisesRegex(ValueError, "PROBE_INVALID"):
                    proof.investigate(
                        "2026-11-18T11:00:00+00:00", "title", "body",
                        history_reader=lambda _: ("ONE", [url]),
                        editor_reader=lambda *_: reply,
                    )

    def test_bridged_inspection_is_read_only_and_never_grants_retry(self):
        with TemporaryDirectory() as td:
            ledger = Path(td) / "ledger.json"
            key = f"{bridge.NEXT_REPO}#204:{bridge.RECOVERY_SHA256}"
            record = {
                "status": "OWNER_RECOVERY_ATTEMPTING",
                "issue_number": 204,
                "manuscript_sha256": bridge.RECOVERY_SHA256,
                "started_at": (datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),
                "recovery_attempt_started_at": (
                    datetime.now(timezone.utc)-timedelta(hours=5)).isoformat(),
                "recovery_approved": True,
                "recovery_owner_list_evidence": "VISIBLE_ABSENT_BOUNDED",
            }
            ledger.write_text(json.dumps({key: record}), encoding="utf-8")
            view = {
                "note_account": "VERIFIED", "matching_title": "NONE_VISIBLE",
                "owner_list_coverage": "BOUNDED_ONLY", "draft_list_coverage": "BOUNDED_ONLY",
                "draft_list_view_verified": True, "note_list_entries_visible": True,
                "untitled_candidate_visible": False, "list_load_more_observed": False,
            }
            report = bridge.inspect_existing_attempt(
                204, bridge.RECOVERY_SHA256, "test title",
                ledger_path=ledger, browser_probe=lambda _: view,
                history_probe=lambda _: "NEW_ROUTE_VISITED",
                manuscript="test body",
                editor_history_probe=lambda *_: {
                    "history_edit_candidate": "ONE",
                    "history_edit_route": "EDITOR_ROUTE_OPENED",
                    "history_edit_title": "MATCH",
                    "history_edit_body": "EXACT",
                },
            )
            self.assertEqual(report["history_edit_route"], "EDITOR_ROUTE_OPENED")
            self.assertEqual(report["history_edit_body"], "EXACT")
            self.assertEqual(report["note_mutations"], 0)
            self.assertFalse(report["automatic_retry_allowed"])
            self.assertFalse(report["publication_approved"])
            self.assertEqual(json.loads(ledger.read_text(encoding="utf-8"))[key], record)

    def test_no_private_url_or_editor_mutations_in_code(self):
        source = inspect.getsource(proof)
        for forbidden in (
            "page.click(", "page.fill(", "keyboard.press(",
            "page.screenshot(", "print(candidate_url)",
            "print(observed_title)", "print(manuscript)",
            "page.goto('https://note.com/notes/new')",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn('service_workers="block"', source)
        self.assertIn('playwright.chromium.launch(', source)
        self.assertNotIn('browser = persistent.browser', source)
        self.assertIn('storage_state=state', source)
        self.assertIn('browser.close()', source)
        self.assertIn('temporary.route("**/*", _only_get)', source)
        self.assertIn("history_edit_body", source)


if __name__ == "__main__":
    unittest.main()
