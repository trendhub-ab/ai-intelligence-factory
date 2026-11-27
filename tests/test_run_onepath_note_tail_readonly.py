"""Synthetic tests: exact matching, partial match stop, no state mutation."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import run_onepath_note_tail_readonly as audit


class TailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "delivery-ledger-v1.sqlite3"
        with sqlite3.connect(self.db) as conn:
            conn.executescript("CREATE TABLE deliveries(record_id,state,stable_draft_id,snapshot_json,attempt_count); CREATE TABLE delivery_events(event_id,record_id,new_state);")
        (self.dir / "v04-private-drafts-v1.json").write_text("{}")
        self.snap = {"sync_id": "a"*32, "queue_page_id": "b"*32,
                     "title_digest": audit.TITLE_HASH, "manuscript_sha256": audit.MANUSCRIPT_HASH}
        self.addCleanup(patch.stopall)
        patch.multiple(audit, SYNC_HASH=audit.id_hash("a"*32), QUEUE_HASH=audit.id_hash("b"*32)).start()

    def integrity(self, _):
        return {"status":"P15_LOCAL_LEDGER_READONLY_AUDIT_COMPLETE","ledger_files_read_complete":True}

    def add_row(self, snap=None, state="CREATE_INTENT_RECORDED", draft=None):
        with sqlite3.connect(self.db) as conn:
            conn.execute("INSERT INTO deliveries VALUES(?,?,?,?,?)",("r",state,draft,json.dumps(snap or self.snap),1))
            conn.execute("INSERT INTO delivery_events VALUES(?,?,?)",(1,"r",state))

    def inspect(self):
        original = self.db.read_bytes()
        result = audit.target_ledger(self.dir,self.integrity)
        self.assertEqual(self.db.read_bytes(),original)
        return result

    def test_absent_is_not_retry_authority(self):
        self.assertEqual(self.inspect()["target_state"],"ABSENT")
        self.assertFalse(any(audit.NO_AUTHORITY.values()))

    def test_exact_intent(self):
        self.add_row()
        result = self.inspect()
        self.assertEqual(result["target_state"],"CREATE_INTENT_RECORDED")
        self.assertFalse(result["stable_draft_id_present"])
        self.assertEqual(result["event_count"],1)

    def test_verified_draft_id_not_exposed(self):
        self.add_row(state="DRAFT_VERIFIED",draft="n1234567890")
        result = self.inspect()
        self.assertTrue(result["stable_draft_id_present"])
        self.assertNotIn("n1234567890",json.dumps(result))

    def test_partial_match_ambiguous(self):
        self.add_row(dict(self.snap,queue_page_id="c"*32))
        self.assertEqual(self.inspect()["target_state"],"AMBIGUOUS")

    def test_integrity_failure(self):
        with self.assertRaises(ValueError):
            audit.target_ledger(self.dir,lambda _:{})

    def test_no_history_is_unknown(self):
        self.assertEqual(audit.history_count(self.dir/"missing"),("UNAVAILABLE",0))
