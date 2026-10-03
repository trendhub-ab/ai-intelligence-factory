"""Temporary P0-A read-only diagnostic hook; remove after one audit run."""
from __future__ import annotations

import os

_TARGET = "3e9479ffdca9811385c7d1a8ffcb3d4a"

if (
    os.environ.get("NOTE_TARGET_SYNC_ID", "").strip().lower() == _TARGET
    and os.environ.get("NOTE_AUDIT_PREPARE_ONLY", "").strip().lower() == "false"
):
    import run291_note_private_draft_audit as _run291

    _run291.MAX_HISTORY_CANDIDATES = 80
