"""Zero-provider regression tests for isolated v0.4 private note draft bridge."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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

    def _recover_ledger(self, path):
        key = f"{bridge.NEXT_REPO}#204:{bridge.RECOVERY_SHA256}"
        record = {
            "status": "ATTEMPTING",
            "issue_number": 204,
            "manuscript_sha256": bridge.RECOVERY_SHA256,
            "started_at": (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat(),
        }
        path.write_text(json.dumps({key: record}), encoding="utf-8")
        return key

    @staticmethod
    def _recovery_probe(_title):
        return {
            "note_account": "VERIFIED",
            "matching_title": "NONE_VISIBLE",
            "owner_list_coverage": "BOUNDED_ONLY",
            "draft_list_coverage": "BOUNDED_ONLY",
            "draft_list_view_verified": True,
            "note_list_entries_visible": True,
            "untitled_candidate_visible": False,
            "list_load_more_observed": False,
        }

    def _final_recovery_ledger(self, path):
        key = f"{bridge.NEXT_REPO}#204:{bridge.RECOVERY_SHA256}"
        record = {
            "status": "OWNER_RECOVERY_ATTEMPTING",
            "issue_number": 204,
            "manuscript_sha256": bridge.RECOVERY_SHA256,
            "started_at": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
            "recovery_attempt_started_at": (
                datetime.now(timezone.utc) - timedelta(hours=6)
            ).isoformat(),
            "recovery_approved": True,
            "recovery_owner_list_evidence": "VISIBLE_ABSENT_BOUNDED",
        }
        path.write_text(json.dumps({key: record}), encoding="utf-8")
        return key

    def test_final_recovery_one_save_then_no_second_attempt(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            key = self._final_recovery_ledger(path)
            writes = []
            def writer(title, body, *, on_url):
                writes.append(title)
                on_url("https://editor.note.com/notes/nabc1234/edit")
                return "https://editor.note.com/notes/nabc1234/edit"
            with patch("note_publication_reconcile.draft_identity_from_url",
                       return_value="nabc1234"):
                result = bridge.recover_after_title_failure_once(
                    204, bridge.RECOVERY_SHA256, SAMPLE,
                    "AIと一緒に作業を進めていく方法",
                    recovery_approval=bridge.FINAL_RECOVERY_APPROVAL,
                    ledger_path=path, runner=writer,
                    browser_probe=self._recovery_probe,
                    history_probe=lambda _: "NEW_ROUTE_VISITED",
                )
            self.assertEqual(result["status"], "DRAFT_SAVED")
            record = json.loads(path.read_text("utf-8"))[key]
            self.assertTrue(record["final_recovery_approved"])
            self.assertIn("final_recovery_started_at", record)
            self.assertEqual(record["status"], "DRAFT_SAVED")
            self.assertEqual(len(writes), 1)
            with self.assertRaisesRegex(ValueError, "FINAL_NOT_ELIGIBLE"):
                bridge.recover_after_title_failure_once(
                    204, bridge.RECOVERY_SHA256, SAMPLE,
                    "AIと一緒に作業を進めていく方法",
                    recovery_approval=bridge.FINAL_RECOVERY_APPROVAL,
                    ledger_path=path, runner=lambda *_a, **_kw: self.fail("duplicate"),
                    browser_probe=self._recovery_probe,
                    history_probe=lambda _: "NEW_ROUTE_VISITED",
                )

    def test_final_recovery_failure_is_irreversibly_blocked(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            key = self._final_recovery_ledger(path)
            def failed(*_args, **_kwargs):
                raise RuntimeError("simulated failed final browser attempt")
            with self.assertRaisesRegex(RuntimeError, "simulated"):
                bridge.recover_after_title_failure_once(
                    204, bridge.RECOVERY_SHA256, SAMPLE,
                    "AIと一緒に作業を進めていく方法",
                    recovery_approval=bridge.FINAL_RECOVERY_APPROVAL,
                    ledger_path=path, runner=failed,
                    browser_probe=self._recovery_probe,
                    history_probe=lambda _: "NEW_ROUTE_VISITED",
                )
            record = json.loads(path.read_text("utf-8"))[key]
            self.assertEqual(record["status"], "OWNER_FINAL_RECOVERY_ATTEMPTING")
            with self.assertRaisesRegex(ValueError, "FINAL_NOT_ELIGIBLE"):
                bridge.recover_after_title_failure_once(
                    204, bridge.RECOVERY_SHA256, SAMPLE,
                    "AIと一緒に作業を進めていく方法",
                    recovery_approval=bridge.FINAL_RECOVERY_APPROVAL,
                    ledger_path=path, runner=lambda *_a, **_kw: self.fail("duplicate"),
                    browser_probe=self._recovery_probe,
                    history_probe=lambda _: "NEW_ROUTE_VISITED",
                )

    def test_final_recovery_denies_missing_approval_and_uncertain_evidence(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            key = self._final_recovery_ledger(path)
            for approval in ("", "OWNER_CONFIRMS_AGENT_SKILLS_204_ABSENT_RETRY_ONCE", "ok"):
                with self.subTest(approval=approval):
                    with self.assertRaisesRegex(ValueError, "FINAL_OWNER_APPROVAL_REQUIRED"):
                        bridge.recover_after_title_failure_once(
                            204, bridge.RECOVERY_SHA256, SAMPLE,
                            "AIと一緒に作業を進めていく方法",
                            recovery_approval=approval, ledger_path=path,
                            runner=lambda *_a, **_kw: self.fail("unsafe"),
                        )
            for history in ("EDIT_ROUTE_VISITED", "NEW_AND_EDIT_ROUTES_VISITED",
                            "HISTORY_UNAVAILABLE"):
                with self.subTest(history=history):
                    with self.assertRaisesRegex(ValueError, "FINAL_HISTORY_UNCERTAIN"):
                        bridge.recover_after_title_failure_once(
                            204, bridge.RECOVERY_SHA256, SAMPLE,
                            "AIと一緒に作業を進めていく方法",
                            recovery_approval=bridge.FINAL_RECOVERY_APPROVAL,
                            ledger_path=path, browser_probe=self._recovery_probe,
                            runner=lambda *_a, **_kw: self.fail("unsafe"),
                            history_probe=lambda _, value=history: value,
                        )
            for change in (
                {"note_account": "BROWSER_UNAVAILABLE"},
                {"matching_title": "POSSIBLE_MATCH_VISIBLE"},
                {"untitled_candidate_visible": True},
                {"list_load_more_observed": True},
                {"draft_list_coverage": "SCROLL_LIMIT"},
            ):
                with self.subTest(change=change):
                    with self.assertRaisesRegex(ValueError, "FINAL_NOTE_LIST_UNCERTAIN"):
                        bridge.recover_after_title_failure_once(
                            204, bridge.RECOVERY_SHA256, SAMPLE,
                            "AIと一緒に作業を進めていく方法",
                            recovery_approval=bridge.FINAL_RECOVERY_APPROVAL,
                            ledger_path=path, runner=lambda *_a, **_kw: self.fail("unsafe"),
                            browser_probe=lambda _: {**self._recovery_probe(""), **change},
                            history_probe=lambda _: "NEW_ROUTE_VISITED",
                        )
            self.assertEqual(json.loads(path.read_text("utf-8"))[key]["status"],
                             "OWNER_RECOVERY_ATTEMPTING")

    def test_final_recovery_rejects_bad_ledger_timestamp_or_prior_url(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            key = self._final_recovery_ledger(path)
            original = json.loads(path.read_text("utf-8"))
            for change in (
                {"draft_url": "https://editor.note.com/notes/n123/edit"},
                {"final_recovery_started_at": "earlier"},
                {"recovery_approved": False},
                {"status": "DRAFT_SAVED"},
            ):
                with self.subTest(change=change):
                    payload = json.loads(json.dumps(original))
                    payload[key].update(change)
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "FINAL_NOT_ELIGIBLE"):
                        bridge.recover_after_title_failure_once(
                            204, bridge.RECOVERY_SHA256, SAMPLE, "title",
                            recovery_approval=bridge.FINAL_RECOVERY_APPROVAL,
                            ledger_path=path,
                            runner=lambda *_a, **_kw: self.fail("unsafe"),
                        )
            for timestamp, expected_error in (
                (datetime.now(timezone.utc).isoformat(), "FINAL_AGE_INVALID"),
                ((datetime.now(timezone.utc) - timedelta(days=18)).isoformat(),
                 "FINAL_TIMESTAMP_INVALID"),
            ):
                payload = json.loads(json.dumps(original))
                payload[key]["recovery_attempt_started_at"] = timestamp
                path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, expected_error):
                    bridge.recover_after_title_failure_once(
                        204, bridge.RECOVERY_SHA256, SAMPLE, "title",
                        recovery_approval=bridge.FINAL_RECOVERY_APPROVAL,
                        ledger_path=path,
                        runner=lambda *_a, **_kw: self.fail("unsafe"),
                    )

    def test_owner_recovery_saves_once_and_preserves_original_attempt(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            key = self._recover_ledger(path)
            events = []
            def writer(title, body, *, on_url):
                events.append(title)
                on_url("https://editor.note.com/notes/nabc1234/edit")
                return "https://editor.note.com/notes/nabc1234/edit"
            with patch("note_publication_reconcile.draft_identity_from_url", return_value="nabc1234"):
                result = bridge.recover_owner_confirmed_once(
                    204, bridge.RECOVERY_SHA256, SAMPLE,
                    "AIと一緒に作業を進めていく方法",
                    recovery_approval=bridge.RECOVERY_APPROVAL,
                    ledger_path=path, runner=writer,
                    browser_probe=self._recovery_probe,
                    history_probe=lambda _time: "NEW_ROUTE_VISITED",
                )
            self.assertEqual(result["status"], "DRAFT_SAVED")
            record = json.loads(path.read_text("utf-8"))[key]
            self.assertEqual(record["status"], "DRAFT_SAVED")
            self.assertTrue(record["recovery_approved"])
            self.assertIn("recovery_attempt_started_at", record)
            self.assertEqual(len(events), 1)
            with self.assertRaisesRegex(ValueError, "RECOVERY_NOT_ELIGIBLE"):
                bridge.recover_owner_confirmed_once(
                    204, bridge.RECOVERY_SHA256, SAMPLE,
                    "AIと一緒に作業を進めていく方法",
                    recovery_approval=bridge.RECOVERY_APPROVAL,
                    ledger_path=path,
                    runner=lambda *_a, **_kw: self.fail("DUPLICATE"),
                    browser_probe=self._recovery_probe,
                    history_probe=lambda _: "NEW_ROUTE_VISITED",
                )

    def test_owner_recovery_prebrowser_failure_keeps_original_attempt_eligible(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            key = self._recover_ledger(path)
            with patch("run190_note_persistent_cloud.install",
                       side_effect=RuntimeError("selector patch invalid")):
                with self.assertRaisesRegex(RuntimeError, "selector patch invalid"):
                    bridge.recover_owner_confirmed_once(
                        204, bridge.RECOVERY_SHA256, SAMPLE,
                        "AIと一緒に作業を進めていく方法",
                        recovery_approval=bridge.RECOVERY_APPROVAL,
                        ledger_path=path,
                        runner=lambda *_a, **_kw: self.fail("UNSAFE_MUTATION"),
                        browser_probe=self._recovery_probe,
                        history_probe=lambda _: "NEW_ROUTE_VISITED",
                    )
            record = json.loads(path.read_text("utf-8"))[key]
            self.assertEqual(record["status"], "ATTEMPTING")
            self.assertNotIn("recovery_attempt_started_at", record)

    def test_owner_recovery_failure_consumes_attempt_without_retry(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            key = self._recover_ledger(path)
            def failed_writer(*_args, **_kwargs):
                raise RuntimeError("simulated before-browser failure")
            with self.assertRaisesRegex(RuntimeError, "simulated"):
                bridge.recover_owner_confirmed_once(
                    204, bridge.RECOVERY_SHA256, SAMPLE,
                    "AIと一緒に作業を進めていく方法",
                    recovery_approval=bridge.RECOVERY_APPROVAL,
                    ledger_path=path, runner=failed_writer,
                    browser_probe=self._recovery_probe,
                    history_probe=lambda _: "NEW_ROUTE_VISITED",
                )
            record = json.loads(path.read_text("utf-8"))[key]
            self.assertEqual(record["status"], "OWNER_RECOVERY_ATTEMPTING")
            with self.assertRaisesRegex(ValueError, "RECOVERY_NOT_ELIGIBLE"):
                bridge.recover_owner_confirmed_once(
                    204, bridge.RECOVERY_SHA256, SAMPLE,
                    "AIと一緒に作業を進めていく方法",
                    recovery_approval=bridge.RECOVERY_APPROVAL,
                    ledger_path=path,
                    runner=lambda *_a, **_kw: self.fail("DUPLICATE"),
                    browser_probe=self._recovery_probe,
                    history_probe=lambda _: "NEW_ROUTE_VISITED",
                )

    def test_owner_recovery_rejects_uncertain_history_and_unverified_lists(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            key = self._recover_ledger(path)
            def reject(*_args, **_kwargs):
                self.fail("Never attempt draft mutation")
            base = dict(self._recovery_probe("t"))
            for history in ("EDIT_ROUTE_VISITED", "NEW_AND_EDIT_ROUTES_VISITED",
                            "HISTORY_UNAVAILABLE", "NO_ATTEMPT_TIMESTAMP"):
                with self.subTest(history=history):
                    with self.assertRaisesRegex(ValueError, "RECOVERY_HISTORY_UNCERTAIN"):
                        bridge.recover_owner_confirmed_once(
                            204, bridge.RECOVERY_SHA256, SAMPLE,
                            "AIと一緒に作業を進めていく方法",
                            recovery_approval=bridge.RECOVERY_APPROVAL,
                            ledger_path=path, runner=reject,
                            browser_probe=self._recovery_probe,
                            history_probe=lambda _date, h=history: h,
                        )
            for change in (
                {"note_account": "NOT_VERIFIED"},
                {"matching_title": "POSSIBLE_MATCH_VISIBLE"},
                {"untitled_candidate_visible": True},
                {"note_list_entries_visible": False},
                {"draft_list_coverage": "SCROLL_LIMIT"},
                {"list_load_more_observed": True},
            ):
                with self.subTest(change=change):
                    with self.assertRaisesRegex(ValueError, "RECOVERY_NOTE_LIST_UNCERTAIN"):
                        bridge.recover_owner_confirmed_once(
                            204, bridge.RECOVERY_SHA256, SAMPLE,
                            "AIと一緒に作業を進めていく方法",
                            recovery_approval=bridge.RECOVERY_APPROVAL,
                            ledger_path=path, runner=reject,
                            browser_probe=lambda _: {**base, **change},
                            history_probe=lambda _: "NEW_ROUTE_VISITED",
                        )
            self.assertEqual(json.loads(path.read_text("utf-8"))[key]["status"], "ATTEMPTING")

    def test_owner_recovery_requires_explicit_token_exact_source_and_timestamp(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            key = self._recover_ledger(path)
            for issue, source_sha, approval in (
                (204, bridge.RECOVERY_SHA256, ""),
                (204, bridge.RECOVERY_SHA256, "approve"),
                (204, "0"*64, bridge.RECOVERY_APPROVAL),
                (205, bridge.RECOVERY_SHA256, bridge.RECOVERY_APPROVAL),
            ):
                with self.subTest(issue=issue, approval=approval):
                    with self.assertRaisesRegex(ValueError, "OWNER_APPROVAL_REQUIRED"):
                        bridge.recover_owner_confirmed_once(
                            issue, source_sha, SAMPLE, "title",
                            recovery_approval=approval, ledger_path=path,
                            runner=lambda *_a, **_kw: self.fail("unsafe"),
                        )
            original = json.loads(path.read_text("utf-8"))
            for timestamp in (
                datetime.now(timezone.utc).isoformat(),
                (datetime.now(timezone.utc) - timedelta(days=32)).isoformat(),
                "2026-11-16T17:40:46",
            ):
                test_data = json.loads(json.dumps(original))
                test_data[key]["started_at"] = timestamp
                path.write_text(json.dumps(test_data), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "RECOVERY_ATTEMPT_"):
                    bridge.recover_owner_confirmed_once(
                        204, bridge.RECOVERY_SHA256, SAMPLE, "title",
                        recovery_approval=bridge.RECOVERY_APPROVAL,
                        ledger_path=path,
                        runner=lambda *_a, **_kw: self.fail("unsafe"),
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

    def test_recovery_failed_title_stage_still_allows_read_only_inspection(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            key = f"{bridge.NEXT_REPO}#204:{SHA}"
            record = {
                "status": "OWNER_RECOVERY_ATTEMPTING",
                "issue_number": 204, "manuscript_sha256": SHA,
                "recovery_attempt_started_at": "2026-11-17T22:25:18+00:00",
                "recovery_approved": True,
                "recovery_owner_list_evidence": "VISIBLE_ABSENT_BOUNDED",
            }
            path.write_text(json.dumps({key: record}), encoding="utf-8")
            report = bridge.inspect_existing_attempt(
                204, SHA, "test title", ledger_path=path,
                browser_probe=lambda _: {
                    "note_account": "VERIFIED",
                    "matching_title": "POSSIBLE_MATCH_VISIBLE",
                    "owner_list_coverage": "BOUNDED_ONLY",
                    "draft_list_coverage": "BOUNDED_ONLY",
                    "draft_list_view_verified": True,
                },
                history_probe=lambda _: "NO_ATTEMPT_TIMESTAMP",
            )
            self.assertEqual(report["ledger"], "OWNER_RECOVERY_ATTEMPTING")
            self.assertEqual(report["matching_title"], "POSSIBLE_MATCH_VISIBLE")
            self.assertFalse(report["automatic_retry_allowed"])
            self.assertFalse(report["stable_draft_url_recorded"])
            self.assertEqual(report["note_mutations"], 0)
            self.assertFalse(report["publication_approved"])
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8"))[key], record
            )
            for change in (
                {"recovery_approved": False},
                {"recovery_owner_list_evidence": "UNVERIFIED"},
                {"recovery_attempt_started_at": ""},
            ):
                with self.subTest(change=change):
                    altered = {**record, **change}
                    path.write_text(json.dumps({key: altered}), encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "LEDGER_INVALID"):
                        bridge.inspect_existing_attempt(
                            204, SHA, "test title", ledger_path=path,
                            browser_probe=lambda _: self.fail("must refuse before scan"),
                        )

    def test_final_recovery_pending_remains_read_only_inspectable(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "ledger.json"
            key = f"{bridge.NEXT_REPO}#204:{SHA}"
            record = {
                "status": "OWNER_FINAL_RECOVERY_ATTEMPTING",
                "issue_number": 204, "manuscript_sha256": SHA,
                "final_recovery_approved": True,
                "final_owner_list_evidence": "VISIBLE_ABSENT_BOUNDED",
                "final_recovery_started_at": "2026-11-18T09:00:00+00:00",
            }
            path.write_text(json.dumps({key: record}), encoding="utf-8")
            result = bridge.inspect_existing_attempt(
                204, SHA, "test title", ledger_path=path,
                browser_probe=lambda _: {
                    "note_account": "VERIFIED",
                    "matching_title": "NONE_VISIBLE",
                },
                history_probe=lambda _: "NO_ATTEMPT_TIMESTAMP",
            )
            self.assertEqual(result["ledger"], "OWNER_FINAL_RECOVERY_ATTEMPTING")
            self.assertFalse(result["automatic_retry_allowed"])
            self.assertEqual(result["note_mutations"], 0)
            self.assertEqual(json.loads(path.read_text("utf-8"))[key], record)
            path.write_text(json.dumps({key: {**record, "final_recovery_approved": False}}),
                            encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "INSPECT_LEDGER_INVALID"):
                bridge.inspect_existing_attempt(
                    204, SHA, "test title", ledger_path=path,
                    browser_probe=lambda _: self.fail("unsafe scan"),
                )

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
        self.assertIn("options: [create, inspect, recover, recover-final]", s)
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
            self.assertEqual(len(bridge._LIST_STRUCTURE_SIGNALS), 24)
            self.assertTrue(all(
                isinstance(code, str) and code.isidentifier()
                for code in bridge._LIST_STRUCTURE_SIGNALS
            ))

    def test_document_wide_read_only_list_fallback_is_bounded(self):
        """A portal or nonsemantic title is not silently missed by main-only selectors."""
        script = bridge._LIST_SNAPSHOT_JS
        scroll = bridge._LIST_SCROLL_JS
        self.assertIn("const root = document.body || main;", script)
        self.assertIn("const bodyTitleVisible", script)
        self.assertIn("normalize(el.textContent) === target", script)
        self.assertIn("bodyTitleVisible\n    )) mask |= 2;", script)
        self.assertIn("!main.contains(el)", script)
        self.assertIn("document.body || document.querySelector", scroll)
        self.assertIn("slice(0, 2000)", script)
        self.assertEqual(bridge._LIST_STRUCTURE_SIGNALS[-4:], (
            "outside_main_article_visible",
            "outside_main_edit_control_visible",
            "outside_main_note_route_link_visible",
            "body_exact_title_visible",
        ))
        # The scanner must not click, post, save, publish or log raw DOM.
        for forbidden in ("fetch(", ".click(", "outerHTML", "innerHTML", "console.log"):
            self.assertNotIn(forbidden, script)

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
