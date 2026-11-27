"""Exact incident #45639717033: readonly ledger + Chrome history evidence.

No browser launch, network, state repair or draft creation. Public logs
contain only counts and fixed enums; a history visit is not persistence proof.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
import unicodedata
from urllib.parse import urlsplit
import re

SYNC_HASH = "c2f305938e7b7a8e5bf5c7762e7003f11a52f4a396c84016e3e2cd6535d8c463"
QUEUE_HASH = "407c9b51f5bf8fe4d51202ecf9523099ba8ee6c4f311be7937e8279f3f07680d"
TITLE_HASH = "0c8efb0f63dd4655491093689cef298f849263bb25f3bd45ffdf14d1ed9afc91"
MANUSCRIPT_HASH = "e10674570ef504519b8b5f782e5c970408ece5b6322bbec38b107747e67c837b"
STATES = frozenset(("PREPARED","CREATE_INTENT_RECORDED","DRAFT_CREATED","DRAFT_VERIFIED",
    "QUEUE_CONFIRMATION_PENDING","QUEUE_CONFIRMED","CREATION_UNKNOWN",
    "VERIFICATION_BLOCKED","CONFLICT","MANUAL_RECONCILIATION_REQUIRED"))
NO_AUTHORITY = {"note_write_authorized": False, "notion_write_authorized": False,
                "public_release_authorized": False, "automatic_retry_authorized": False}


def digest(value):
    return sha256(unicodedata.normalize("NFC", value).strip().encode("utf-8")).hexdigest()


def id_hash(value):
    return digest(value.replace("-", "").lower()) if isinstance(value, str) else ""


def read_only_db(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000_000:
        raise ValueError("UNAVAILABLE")
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
    conn.execute("PRAGMA query_only=ON")
    return conn


def target_ledger(directory, integrity_audit):
    receipt = integrity_audit(directory)
    if receipt.get("status") != "P15_LOCAL_LEDGER_READONLY_AUDIT_COMPLETE" or receipt.get("ledger_files_read_complete") is not True:
        raise ValueError("INTEGRITY")
    conn = read_only_db(directory / "delivery-ledger-v1.sqlite3")
    try:
        rows = conn.execute("SELECT record_id, state, stable_draft_id, snapshot_json, attempt_count FROM deliveries").fetchall()
        matches = []
        for record_id, state, draft, raw, attempts in rows:
            snap = json.loads(raw)
            if not isinstance(snap, dict) or state not in STATES:
                raise ValueError("SCHEMA")
            flags = (id_hash(snap.get("sync_id")) == SYNC_HASH,
                     id_hash(snap.get("queue_page_id")) == QUEUE_HASH,
                     snap.get("title_digest") == TITLE_HASH,
                     snap.get("manuscript_sha256") == MANUSCRIPT_HASH)
            if any(flags):
                matches.append((record_id, state, draft, attempts, all(flags)))
        v04 = json.loads((directory / "v04-private-drafts-v1.json").read_text("utf-8"))
        v04_count = sum(entry.get("manuscript_sha256") == MANUSCRIPT_HASH for entry in v04.values())
        if len(matches) != 1 or v04_count or not matches[0][4]:
            return {"target_sqlite_matches": len(matches), "target_v04_matches": v04_count,
                    "target_state": "ABSENT" if not matches and not v04_count else "AMBIGUOUS",
                    "stable_draft_id_present": False, "event_count": 0, "attempt_count": 0}
        record_id, state, draft, attempts, _ = matches[0]
        events = conn.execute("SELECT new_state FROM delivery_events WHERE record_id=? ORDER BY event_id", (record_id,)).fetchall()
        if not events or any(x[0] not in STATES for x in events) or events[-1][0] != state:
            raise ValueError("EVENTS")
        if type(attempts) is not int or attempts < 1:
            raise ValueError("ATTEMPTS")
        return {"target_sqlite_matches": 1, "target_v04_matches": 0, "target_state": state,
                "stable_draft_id_present": bool(draft), "event_count": len(events),
                "attempt_count": attempts, "state_sequence": [x[0] for x in events]}
    finally:
        conn.close()


def history_count(profile):
    # Exact failed delivery window; no route IDs or URLs leave the host.
    epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    lo, hi = (int((datetime.fromisoformat(x)-epoch).total_seconds()*1_000_000)
              for x in ("2026-11-25T14:59:16+00:00","2026-11-25T15:17:54+00:00"))
    if not profile.is_dir():
        return "UNAVAILABLE", 0
    paths = sorted(profile.rglob("History"))
    if not paths or len(paths) > 12:
        return "UNAVAILABLE", 0
    candidates = set()
    for path in paths:
        conn = read_only_db(path)
        try:
            rows = conn.execute("SELECT u.url FROM visits v JOIN urls u ON u.id=v.url WHERE v.visit_time BETWEEN ? AND ? LIMIT 1025",(lo,hi)).fetchall()
            if len(rows) > 1024:
                return "UNAVAILABLE", 0
            for (raw,) in rows:
                p = urlsplit(raw)
                if p.scheme == "https" and p.hostname in ("note.com","editor.note.com") and not p.username and not p.password:
                    m = re.fullmatch(r"/notes/(n[a-z0-9]{8,32})/edit/?",p.path)
                    if m:
                        candidates.add(m[1])
        finally:
            conn.close()
    return ("OBSERVED" if candidates else "NONE_IN_WINDOW"), len(candidates)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        from aiif_next.p15_local_ledger_readonly_audit import audit_directory
        state = target_ledger(args.ledger_dir, audit_directory)
    except Exception:
        print(json.dumps({"status": "ONEPATH_NOTE_TAIL_STOP", "reason": "LEDGER_READ_UNVERIFIED", **NO_AUTHORITY}))
        return 2
    try:
        profile = Path(os.environ.get("NOTE_CHROME_USER_DATA_DIR") or args.ledger_dir / "chrome-profile")
        history, count = history_count(profile)
    except Exception:
        history, count = "UNAVAILABLE", 0
    print(json.dumps({"status": "ONEPATH_NOTE_TAIL_READONLY_COMPLETE", **state,
                      "history_status": history, "history_candidate_count": count,
                      "note_server_persistence_verified": False, **NO_AUTHORITY}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
