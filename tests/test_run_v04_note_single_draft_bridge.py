"""Zero-provider regression tests for isolated v0.4 private note draft bridge."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import run_v04_note_single_draft_bridge as bridge

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/v04-single-note-draft-bridge.yml"
SAMPLE = (
    "# AIと一緒に作業を進めていく方法\n\n"
    "AIに同じことを説明するの、少し大変ですよね。だから、"
    "作業の手順を一か所に置いておく方法を考えてみます。\n\n"
    + "自分で確認できる一次情報をもとに、具体例と制約を整理します。"
    * 70
    + "\n\n### Sources / Evidence\n"
    + "- https://github.blog/ai-and-ml/github-copilot/build-once-run-on-any-agent-a-practical-guide-to-agent-skills/\n"
)
SHA = sha256(SAMPLE.encode()).hexdigest()


def source_api(method, url, token, payload=None):
    if url == bridge.NEXT_API:
        return {"full_name": bridge.NEXT_REPO, "private": True, "archived": False}
    if url == bridge.NEXT_API + "/issues/204":
        return {
            "number": 204, "state": "open",
            "user": {"login": "trendhub-ab"},
            "title": "AIIF V04 PRIVATE NOTE DRAFT SOURCE — Agent Skills",
            "body": SAMPLE,
        }
    raise AssertionError("Unexpected API request: " + url)


class SingleNoteBridgeTests(unittest.TestCase):
    def test_exact_private_owner_issue_returns_real_article(self):
        result = bridge.validated_owner_manuscript(
            204, SHA, "x"*32, get=source_api)
        self.assertEqual(result, ("AIと一緒に作業を進めていく方法", SAMPLE))
        with self.assertRaisesRegex(ValueError, "MANUSCRIPT_HASH_MISMATCH"):
            bridge.validated_owner_manuscript(
                204, "0"*64, "x"*32, get=source_api)

    def test_untrusted_repo_issue_or_short_manuscript_rejected(self):
        def wrong_repo(*args):
            obj = source_api(*args)
            if "private" in obj:
                obj["private"] = False
            return obj
        with self.assertRaisesRegex(ValueError, "PRIVATE_REPO_REQUIRED"):
            bridge.validated_owner_manuscript(204, SHA, "x"*32, get=wrong_repo)

        def wrong_author(*args):
            obj = source_api(*args)
            if "body" in obj:
                obj["user"] = {"login": "intruder"}
            return obj
        with self.assertRaisesRegex(ValueError, "OWNER_ISSUE_REQUIRED"):
            bridge.validated_owner_manuscript(204, SHA, "x"*32, get=wrong_author)

        def forged_body(*args):
            obj = source_api(*args)
            if "body" in obj:
                obj["body"] = "x"
            return obj
        with self.assertRaisesRegex(ValueError, "MANUSCRIPT_HASH_MISMATCH"):
            bridge.validated_owner_manuscript(204, SHA, "x"*32, get=forged_body)

    def test_only_one_save_even_after_repeated_dispatch(self):
        with TemporaryDirectory() as td:
            path = Path(td)/"ledger.json"
            events = []
            def writer(title, manuscript, *, on_url):
                self.assertEqual(manuscript, SAMPLE)
                events.append(title)
                on_url("https://editor.note.com/notes/nabc1234/edit")
                return "https://editor.note.com/notes/nabc1234/edit"
            with patch(
                "note_publication_reconcile.draft_identity_from_url",
                return_value="nabc1234",
            ):
                first = bridge.save_once(
                    204, SHA, SAMPLE, "AIと一緒に作業を進めていく方法",
                    runner=writer, ledger_path=path,
                )
                second = bridge.save_once(
                    204, SHA, SAMPLE, "AIと一緒に作業を進めていく方法",
                    runner=lambda *_a, **_kw: self.fail("DUPLICATE DRAFT"),
                    ledger_path=path,
                )
            self.assertEqual(first["status"], "DRAFT_SAVED")
            self.assertEqual(second["status"], "ALREADY_SAVED")
            self.assertEqual(len(events), 1)
            self.assertIn(SHA, path.read_text("utf-8"))

    def test_ambiguous_failure_is_blocked_before_duplicate_write(self):
        with TemporaryDirectory() as td:
            path = Path(td)/"ledger.json"
            with self.assertRaisesRegex(RuntimeError, "browser failed"):
                bridge.save_once(
                    204, SHA, SAMPLE, "title",
                    runner=lambda *_a, **_kw: (_ for _ in ()).throw(
                        RuntimeError("browser failed")),
                    ledger_path=path,
                )
            self.assertEqual(
                next(iter(json.loads(path.read_text()).values()))["status"],
                "ATTEMPTING")
            with self.assertRaisesRegex(ValueError, "AMBIGUOUS_PRIOR_ATTEMPT"):
                bridge.save_once(
                    204, SHA, SAMPLE, "title",
                    runner=lambda *_a, **_kw: self.fail("DUPLICATE"),
                    ledger_path=path,
                )

    def test_read_only_inspection_never_authorizes_retry(self):
        with TemporaryDirectory() as td:
            path = Path(td)/"ledger.json"
            safe = lambda _title: {
                "note_account": "VERIFIED", "matching_title": "NONE_VISIBLE"
            }
            fresh = bridge.inspect_existing_attempt(
                204, SHA, "title", ledger_path=path, browser_probe=safe
            )
            self.assertEqual(fresh["ledger"], "NO_RECORD")
            self.assertFalse(fresh["automatic_retry_allowed"])
            self.assertEqual(fresh["note_mutations"], 0)
            self.assertFalse(fresh["publication_approved"])
            for phase in (
                "ATTEMPTING", "CREATED_PENDING_PERSISTENCE_PROOF", "DRAFT_SAVED"
            ):
                path.write_text(json.dumps({
                    f"{bridge.NEXT_REPO}#204:{SHA}": {
                        "issue_number": 204, "manuscript_sha256": SHA,
                        "status": phase, "draft_url":
                            "https://editor.note.com/notes/nabc1234/edit",
                    }
                }), encoding="utf-8")
                receipt = bridge.inspect_existing_attempt(
                    204, SHA, "title", ledger_path=path, browser_probe=safe
                )
                self.assertEqual(receipt["ledger"], phase)
                self.assertTrue(receipt["stable_draft_url_recorded"])
                self.assertFalse(receipt["automatic_retry_allowed"])
                self.assertEqual(receipt["matching_title"], "NONE_VISIBLE")

    def test_read_only_inspection_rejects_corrupt_ledger_or_probe(self):
        with TemporaryDirectory() as td:
            path = Path(td)/"ledger.json"
            path.write_text(json.dumps({
                f"{bridge.NEXT_REPO}#204:{SHA}": {
                    "issue_number": 204, "manuscript_sha256": SHA,
                    "status": "UNKNOWN_STATUS"
                }
            }), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "LEDGER_INVALID"):
                bridge.inspect_existing_attempt(
                    204, SHA, "title", ledger_path=path,
                    browser_probe=lambda _: self.fail("UNSAFE_PROBE")
                )
            path.unlink()
            with self.assertRaisesRegex(ValueError, "PROBE_INVALID"):
                bridge.inspect_existing_attempt(
                    204, SHA, "title", ledger_path=path,
                    browser_probe=lambda _: {"draft_url": "secret"}
                )

    def test_read_only_probe_is_ineligible_to_modify_existing_draft(self):
        s = WORKFLOW.read_text("utf-8")
        self.assertIn("inputs.operation == 'create'", s)
        self.assertIn("inputs.operation == 'inspect'", s)
        self.assertIn("inspect-draft-state:", s)
        self.assertIn("--mode inspect", s)
        self.assertIn("options: [create, inspect]", s)
        self.assertIn("needs: [verify-private-input, start-note-vm, create-exact-draft, inspect-draft-state]", s)

    def test_history_probe_reads_visit_times_without_exposing_draft_urls(self):
        import run190_note_persistent_cloud as cloud
        with TemporaryDirectory() as td:
            home = Path(td)
            profile = home / "Default"
            profile.mkdir()
            db = sqlite3.connect(str(profile / "History"))
            db.executescript(
                "CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT);"
                "CREATE TABLE visits (url INTEGER, visit_time INTEGER);"
            )
            db.execute(
                "INSERT INTO urls VALUES (?, ?)",
                (1, "https://editor.note.com/notes/nprivate123/edit"),
            )
            db.execute(
                "INSERT INTO urls VALUES (?, ?)",
                (2, "https://note.com/notes/new"),
            )
            when = "2026-11-16T17:40:46+00:00"
            epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
            tick = int((datetime.fromisoformat(when) - epoch).total_seconds() * 1e6)
            db.execute("INSERT INTO visits VALUES (?, ?)", (1, tick))
            db.commit()
            with patch.object(cloud, "_profile_dir", return_value=home):
                first = bridge._historical_editor_navigation(when)
                self.assertEqual(first, "EDIT_ROUTE_VISITED")
                self.assertNotIn("nprivate123", first)
                db.execute("INSERT INTO visits VALUES (?, ?)", (2, tick))
                db.commit()
                second = bridge._historical_editor_navigation(when)
                self.assertEqual(second, "NEW_AND_EDIT_ROUTES_VISITED")
                db.execute("DELETE FROM visits")
                db.commit()
                empty = bridge._historical_editor_navigation(when)
                self.assertEqual(empty, "NO_EDITOR_NAVIGATION_SEEN")
            db.close()

    def test_inspection_history_is_only_evidence_not_retry_authority(self):
        with TemporaryDirectory() as td:
            path = Path(td)/"ledger.json"
            path.write_text(json.dumps({
                f"{bridge.NEXT_REPO}#204:{SHA}": {
                    "issue_number": 204, "manuscript_sha256": SHA,
                    "status": "ATTEMPTING",
                    "started_at": "2026-11-16T17:40:46+00:00",
                }
            }), encoding="utf-8")
            report = bridge.inspect_existing_attempt(
                204, SHA, "title", ledger_path=path,
                browser_probe=lambda _: {
                    "note_account": "VERIFIED",
                    "matching_title": "NONE_VISIBLE",
                },
                history_probe=lambda _: "EDIT_ROUTE_VISITED",
            )
            self.assertEqual(report["historical_editor_navigation"], "EDIT_ROUTE_VISITED")
            self.assertFalse(report["automatic_retry_allowed"])
            self.assertEqual(report["ledger"], "ATTEMPTING")
            self.assertEqual(report["note_mutations"], 0)
            with self.assertRaisesRegex(ValueError, "HISTORY_INVALID"):
                bridge.inspect_existing_attempt(
                    204, SHA, "title", ledger_path=path,
                    browser_probe=lambda _: {
                        "note_account": "VERIFIED",
                        "matching_title": "NONE_VISIBLE",
                    },
                    history_probe=lambda _: "secret title or URL",
                )

    def test_create_uses_existing_browser_contract_and_safe_stage_markers(self):
        script = Path(bridge.__file__).read_text("utf-8")
        self.assertIn("cloud.install()", script)
        self.assertIn('print("V04_NOTE_STAGE=ACCOUNT_VERIFIED"', script)
        self.assertIn('print("V04_NOTE_STAGE=EDITOR_READY"', script)
        self.assertIn('print("V04_NOTE_STAGE=BODY_VERIFIED"', script)
        self.assertIn('print("V04_NOTE_STAGE=ARTICLE_LIST_CONFIRMED"', script)
        self.assertNotIn("except Exception as exc:\\n        print(exc)", script)

    def test_bounded_inventory_is_only_partial_read_only_evidence(self):
        class SafeLocator:
            def count(self):
                return 0

        class FakeNotePage:
            def __init__(self):
                self.url = ""
                self.nav = []
                self.evaluate_calls = []
                self.snapshots = [
                    {"mask": 1 | 64 | 256, "structure": (1 << 1) | (1 << 10), "next": "?page=2"},
                    {"mask": 1 | 2 | 4 | 64, "structure": (1 << 2) | (1 << 6), "next": ""},
                ]
            def goto(self, url, **kwargs):
                self.url = url
                self.nav.append(url)
            def wait_for_timeout(self, *args):
                return None
            def locator(self, *args):
                return SafeLocator()
            def evaluate(self, script, *args):
                self.evaluate_calls.append(script)
                if script == bridge._LIST_SNAPSHOT_JS:
                    return self.snapshots[0] if len(self.nav) == 1 else self.snapshots[1]
                if script == bridge._LIST_SCROLL_JS:
                    return 0
                raise AssertionError("An unexpected DOM action was attempted")

        page = FakeNotePage()
        result = bridge._bounded_list_inventory(page, "expected", draft=False)
        self.assertEqual(result["coverage"], "BOUNDED_ONLY")
        self.assertTrue(result["title_visible"])
        self.assertTrue(result["untitled_visible"])
        self.assertTrue(result["entries_visible"])
        self.assertTrue(result["pages_followed"])
        self.assertEqual(result["structure_signals"], sorted([
            "main_present", "link_visible", "main_visible",
            "article_semantic_visible",
        ]))
        self.assertEqual(page.nav, [
            "https://note.com/notes", "https://note.com/notes?page=2"
        ])
        self.assertTrue(all(
            call in (bridge._LIST_SNAPSHOT_JS, bridge._LIST_SCROLL_JS)
            for call in page.evaluate_calls
        ))

    def test_strict_list_pagination_rejects_non_list_and_cross_site(self):
        self.assertEqual(bridge._next_verified_list_url(
            "?page=2", draft=False
        ), "https://note.com/notes?page=2")
        self.assertEqual(bridge._next_verified_list_url(
            "?kind=draft&page=4", draft=True
        ), "https://note.com/notes?kind=draft&page=4")
        for unsafe in (
            "https://evil.example/notes?page=2",
            "https://evil.example@note.com/notes?page=2",
            "https://note.com/notes/nprivate/edit",
            "https://note.com/notes?page=2&action=save",
            "https://note.com/notes?page=1",
            "https://note.com/notes?page=501",
            "https://note.com/notes?page=2#fragment",
            "?kind=draft&page=2",
        ):
            self.assertIsNone(bridge._next_verified_list_url(unsafe, draft=False))
        self.assertIsNone(bridge._next_verified_list_url(
            "https://note.com/notes?page=3", draft=True))
        self.assertTrue(bridge._verified_list_route(
            "https://note.com/notes?kind=draft", draft=True))
        self.assertFalse(bridge._verified_list_route(
            "https://note.com/notes?kind=published", draft=True))

    def test_incomplete_inventory_is_not_authority_to_retry(self):
        class UninspectablePage:
            url = ""
            def goto(self, url, **_):
                self.url = url
            def wait_for_timeout(self, *_):
                pass
            def locator(self, *_):
                class Locator:
                    def count(self): return 0
                return Locator()
            def evaluate(self, *_):
                return {"mask": True, "next": ""}

        scan = bridge._bounded_list_inventory(
            UninspectablePage(), "private title", draft=True
        )
        self.assertEqual(scan["coverage"], "UNINSPECTABLE")
        self.assertFalse(scan["title_visible"])

        with TemporaryDirectory() as td:
            report = bridge.inspect_existing_attempt(
                204, SHA, "title",
                ledger_path=Path(td) / "nonexistent.json",
                browser_probe=lambda _title: {
                    "note_account": "VERIFIED",
                    "matching_title": "NONE_VISIBLE",
                    "owner_list_coverage": "BOUNDED_ONLY",
                    "draft_list_coverage": "UNINSPECTABLE",
                    "draft_list_view_verified": False,
                    "untitled_candidate_visible": False,
                    "list_load_more_observed": False,
                    "list_pagination_followed": False,
                    "note_list_entries_visible": False,
                },
                history_probe=lambda _: "NO_ATTEMPT_TIMESTAMP",
            )
            self.assertFalse(report["automatic_retry_allowed"])
            self.assertEqual(report["note_mutations"], 0)
            self.assertEqual(report["draft_list_coverage"], "UNINSPECTABLE")

    def test_inspection_rejects_secret_or_unapproved_scan_evidence(self):
        with TemporaryDirectory() as td:
            path = Path(td)/"none.json"
            def invalid_probe(_):
                return {
                    "note_account": "VERIFIED",
                    "matching_title": "POSSIBLE_MATCH_VISIBLE",
                    "draft_list_coverage": "COMPLETE",
                }
            with self.assertRaisesRegex(ValueError, "COVERAGE_INVALID"):
                bridge.inspect_existing_attempt(
                    204, SHA, "title", ledger_path=path,
                    browser_probe=invalid_probe,
                    history_probe=lambda _: "NO_ATTEMPT_TIMESTAMP",
                )
            def secret_probe(_):
                return {
                    "note_account": "VERIFIED",
                    "matching_title": "NONE_VISIBLE",
                    "private_draft_url": "https://editor.note.com/notes/private/edit",
                }
            with self.assertRaisesRegex(ValueError, "PROBE_INVALID"):
                bridge.inspect_existing_attempt(
                    204, SHA, "title", ledger_path=path,
                    browser_probe=secret_probe,
                    history_probe=lambda _: "NO_ATTEMPT_TIMESTAMP",
                )

    def test_structure_diagnostics_do_not_contain_private_dom_content(self):
        with TemporaryDirectory() as td:
            recorded = {
                "note_account": "VERIFIED",
                "matching_title": "NONE_VISIBLE",
                "owner_list_structure": [
                    "document_ready", "main_present", "navigation_visible",
                ],
                "draft_list_structure": [
                    "article_semantic_visible", "edit_control_hidden",
                    "loading_indicator_visible",
                ],
            }
            observed = bridge.inspect_existing_attempt(
                204, SHA, "private article title",
                ledger_path=Path(td)/"ledger.json",
                browser_probe=lambda _: recorded,
                history_probe=lambda _: "NO_ATTEMPT_TIMESTAMP",
            )
            self.assertEqual(
                observed["draft_list_structure"], recorded["draft_list_structure"]
            )
            self.assertFalse(observed["automatic_retry_allowed"])
            self.assertEqual(observed["note_mutations"], 0)
            self.assertNotIn("private article title", json.dumps(observed))
            self.assertNotIn("note.com/notes/", json.dumps(observed))

    def test_structure_output_rejects_unknown_codes_or_duplicate_entries(self):
        with TemporaryDirectory() as td:
            def browser(flags):
                return lambda _: {
                    "note_account": "VERIFIED", "matching_title": "NONE_VISIBLE",
                    "owner_list_structure": flags,
                }
            for flags in (
                ["raw_html=<secret>"], ["main_present", "main_present"],
                ["hidden URL"], "main_present", list(range(25)),
            ):
                with self.subTest(flags=str(flags)[:35]):
                    with self.assertRaisesRegex(ValueError, "STRUCTURE_INVALID"):
                        bridge.inspect_existing_attempt(
                            204, SHA, "title",
                            ledger_path=Path(td) / "ledger.json",
                            browser_probe=browser(flags),
                            history_probe=lambda _: "NO_ATTEMPT_TIMESTAMP",
                        )
            self.assertEqual(len(bridge._LIST_STRUCTURE_SIGNALS), 20)
            self.assertTrue(all(
                isinstance(code, str) and code.isidentifier()
                for code in bridge._LIST_STRUCTURE_SIGNALS
            ))

    def test_structure_shape_is_not_content_or_retry_proof(self):
        class WrongStructurePage:
            url = ""
            def goto(self, url, **_):
                self.url = url
            def wait_for_timeout(self, *_):
                pass
            def locator(self, *_):
                class L:
                    def count(self): return 0
                return L()
            def evaluate(self, script, *_):
                if script == bridge._LIST_SNAPSHOT_JS:
                    return {"mask": 0, "next": "", "structure": "raw private text"}
                if script == bridge._LIST_SCROLL_JS:
                    return 0
                raise AssertionError("Unexpected write or browser request")
        result = bridge._bounded_list_inventory(
            WrongStructurePage(), "title", draft=True
        )
        self.assertEqual(result["coverage"], "UNINSPECTABLE")
        self.assertEqual(result["structure_signals"], [])
        self.assertFalse(result["title_visible"])

    def test_workflow_is_one_off_no_auto_or_publication(self):
        s = WORKFLOW.read_text("utf-8")
        for piece in (
            "workflow_dispatch:", "CREATE_V04_SINGLE_PRIVATE_NOTE_DRAFT",
            "github.actor == 'trendhub-ab'",
            "github.ref == 'refs/heads/main'",
            "github.run_attempt == 1", "note-draft-create-v2",
            "run_v04_note_single_draft_bridge.py",
            "self-hosted, linux, x64, aiif-note-cloud",
            "GCP_WORKLOAD_IDENTITY_PROVIDER", "NOTE_STORAGE_STATE_B64:",
            "stop-note-vm:", "persist-credentials: false",
            "uses: actions/setup-python@v6", "python-version: '3.11'",
        ):
            self.assertIn(piece, s)
        for forbidden in (
            "\n  schedule:", "\n  push:", "\n  pull_request:",
            "production_pipeline.py", "note_ready_sync.py",
            "AIIF_NEXT_GEMINI_API_KEY", "publish_note",
        ):
            self.assertNotIn(forbidden, s)


if __name__ == "__main__":
    unittest.main()
