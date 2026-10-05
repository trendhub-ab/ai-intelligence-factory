#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
from __future__ import annotations

import json
import os
from pathlib import Path

from note_delivery_ledger import DeliveryState, LedgerUnavailableError
from note_delivery_runtime import _logical_key_for_identity, delivery_ledger_from_environment


def normalized(value: object) -> str:
    return str(value or "").strip()


def safe_result(status: str, should_run_delivery: bool) -> dict[str, object]:
    return {
        "status": status,
        "should_run_delivery": bool(should_run_delivery),
        "zero_gemini_calls": True,
    }


sync_id = normalized(os.environ.get("NOTE_TARGET_SYNC_ID", "")).lower()
note_target = normalized(os.environ.get("NOTE_TARGET_IDENTITY", ""))
result_file = normalized(os.environ.get("NOTE_DRAFT_RESULT_FILE", ""))

if not sync_id or not note_target:
    raise LedgerUnavailableError("ledger_gate_identity_missing")

ledger = delivery_ledger_from_environment()
logical_key = _logical_key_for_identity(sync_id, note_target)
record = ledger.get_active_by_logical_key(logical_key)

if record is None:
    result = safe_result("ledger_clean_new", True)
elif record.state in {
    DeliveryState.DRAFT_VERIFIED,
    DeliveryState.QUEUE_CONFIRMATION_PENDING,
    DeliveryState.QUEUE_CONFIRMED,
}:
    result = safe_result("ledger_reconcile_existing", True)
else:
    result = safe_result("ledger_blocked_ambiguous", False)

if result_file:
    path = Path(result_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

print(
    "[P0B LEDGER PREFLIGHT] "
    + json.dumps(
        {
            "status": result["status"],
            "should_run_delivery": result["should_run_delivery"],
            "zero_gemini_calls": True,
        },
        ensure_ascii=False,
    )
)
PY
