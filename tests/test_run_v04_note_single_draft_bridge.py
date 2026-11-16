"""Zero-provider regression tests for isolated v0.4 private note draft bridge."""
from __future__ import annotations

from hashlib import sha256
import json
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
