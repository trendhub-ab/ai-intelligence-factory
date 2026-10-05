from pathlib import Path

runtime_path = Path('note_delivery_runtime.py')
runtime = runtime_path.read_text(encoding='utf-8')

runtime = runtime.replace(
    'import note_publication_reconcile as reconcile\n\nfrom note_document_contract',
    'import note_publication_reconcile as reconcile\nfrom note_delivery_gcs import GCSDeliveryLedger\n\nfrom note_document_contract',
    1,
)

runtime = runtime.replace(
    'NOTE_DELIVERY_LEDGER_ENV = "NOTE_DELIVERY_LEDGER_PATH"\nDEFAULT_LEDGER_PATH = Path.home() / ".aiif-note" / "delivery-ledger-v1.sqlite3"\n',
    'NOTE_DELIVERY_LEDGER_BACKEND_ENV = "NOTE_DELIVERY_LEDGER_BACKEND"\nNOTE_DELIVERY_LEDGER_BUCKET_ENV = "NOTE_DELIVERY_LEDGER_BUCKET"\nNOTE_DELIVERY_LEDGER_PREFIX_ENV = "NOTE_DELIVERY_LEDGER_PREFIX"\nNOTE_DELIVERY_LEDGER_PATH_ENV = "NOTE_DELIVERY_LEDGER_PATH"\nDEFAULT_GCS_PREFIX = "delivery/v1"\n',
    1,
)

runtime = runtime.replace(
    'raise base.NoteDraftError("VM preparation returned a different sync_id")',
    'raise base.NoteDraftError("Delivery preparation returned a different sync_id")',
    1,
)

old_factory = '''def delivery_ledger_from_environment() -> SQLiteDeliveryLedger:\n    raw = str(os.environ.get(NOTE_DELIVERY_LEDGER_ENV, "")).strip()\n    path = Path(raw).expanduser() if raw else DEFAULT_LEDGER_PATH\n    return SQLiteDeliveryLedger(path)\n'''
new_factory = '''def delivery_ledger_from_environment() -> DeliveryLedger:\n    backend = str(os.environ.get(NOTE_DELIVERY_LEDGER_BACKEND_ENV, "")).strip().lower()\n    if not backend:\n        raise LedgerUnavailableError("ledger_backend_required")\n\n    if backend == "gcs":\n        bucket = str(os.environ.get(NOTE_DELIVERY_LEDGER_BUCKET_ENV, "")).strip()\n        if not bucket:\n            raise LedgerUnavailableError("gcs_bucket_required")\n        prefix = str(os.environ.get(NOTE_DELIVERY_LEDGER_PREFIX_ENV, DEFAULT_GCS_PREFIX)).strip()\n        return GCSDeliveryLedger(bucket, prefix=prefix or DEFAULT_GCS_PREFIX)\n\n    if backend == "sqlite":\n        raw = str(os.environ.get(NOTE_DELIVERY_LEDGER_PATH_ENV, "")).strip()\n        if not raw:\n            raise LedgerUnavailableError("sqlite_ledger_path_required")\n        return SQLiteDeliveryLedger(Path(raw).expanduser())\n\n    raise LedgerUnavailableError("unsupported_ledger_backend")\n'''
if old_factory not in runtime:
    raise SystemExit('old delivery_ledger_from_environment factory not found')
runtime = runtime.replace(old_factory, new_factory, 1)
runtime_path.write_text(runtime, encoding='utf-8')

preflight = '''#!/usr/bin/env bash
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
'''
Path('note_delivery_ledger_preflight.sh').write_text(preflight, encoding='utf-8')
