from pathlib import Path

ledger_path = Path('note_delivery_ledger.py')
text = ledger_path.read_text(encoding='utf-8')
text = text.replace(
    'from typing import Callable, Iterable, TypeVar\n',
    'from typing import Callable, Iterable, Mapping, Protocol, TypeVar, runtime_checkable\n',
    1,
)

intent_marker = '''@dataclass(frozen=True)\nclass IntentDecision:\n    record: DeliveryRecord\n    creation_authorized: bool\n    reason: str\n\n'''
protocol_block = '''@dataclass(frozen=True)\nclass IntentDecision:\n    record: DeliveryRecord\n    creation_authorized: bool\n    reason: str\n\n\n@runtime_checkable\nclass DeliveryLedger(Protocol):\n    def get_by_operation_key(self, op_key: str) -> DeliveryRecord | None: ...\n\n    def get_active_by_logical_key(self, logical_key: str) -> DeliveryRecord | None: ...\n\n    def begin_or_load(self, snapshot: DeliverySnapshot, *, run_correlation_id: str) -> IntentDecision: ...\n\n    def record_draft_created(\n        self, operation_key: str, *, draft_id: str, note_host: str, expected_version: int\n    ) -> DeliveryRecord: ...\n\n    def record_verified(\n        self, operation_key: str, *, canonical_sha256: str, expected_version: int\n    ) -> DeliveryRecord: ...\n\n    def record_queue_pending(\n        self, operation_key: str, *, category: str, expected_version: int\n    ) -> DeliveryRecord: ...\n\n    def record_queue_confirmed(\n        self, operation_key: str, *, receipt_digest: str, expected_version: int\n    ) -> DeliveryRecord: ...\n\n    def record_blocked(\n        self, operation_key: str, *, state: DeliveryState, category: str, expected_version: int\n    ) -> DeliveryRecord: ...\n\n'''
if intent_marker not in text:
    raise SystemExit('IntentDecision marker not found')
text = text.replace(intent_marker, protocol_block, 1)

snapshot_marker = '''def _snapshot_from_json(value: str) -> DeliverySnapshot:\n    data = json.loads(value)\n    data["transform_versions"] = tuple(tuple(item) for item in data["transform_versions"])\n    return DeliverySnapshot(**data)\n\n'''
serialization_block = '''def _snapshot_from_json(value: str) -> DeliverySnapshot:\n    data = json.loads(value)\n    data["transform_versions"] = tuple(tuple(item) for item in data["transform_versions"])\n    return DeliverySnapshot(**data)\n\n\ndef delivery_record_to_dict(record: DeliveryRecord) -> dict[str, object]:\n    data = asdict(record)\n    data["state"] = record.state.value\n    return data\n\n\ndef delivery_record_from_dict(data: Mapping[str, object]) -> DeliveryRecord:\n    if not isinstance(data, Mapping):\n        raise LedgerSchemaError("invalid_ledger_record")\n    if str(data.get("schema_version") or "") != DELIVERY_RECORD_SCHEMA_VERSION:\n        raise LedgerSchemaError("unsupported_ledger_schema")\n\n    snapshot_raw = data.get("snapshot")\n    if not isinstance(snapshot_raw, Mapping):\n        raise LedgerSchemaError("invalid_ledger_snapshot")\n    if str(snapshot_raw.get("schema_version") or "") != SNAPSHOT_SCHEMA_VERSION:\n        raise LedgerSchemaError("unsupported_snapshot_schema")\n\n    try:\n        snapshot_data = dict(snapshot_raw)\n        transforms = snapshot_data.get("transform_versions", ())\n        snapshot_data["transform_versions"] = tuple(tuple(item) for item in transforms)\n        snapshot = DeliverySnapshot(**snapshot_data)\n    except (KeyError, TypeError, ValueError) as exc:\n        raise LedgerSchemaError("invalid_ledger_snapshot") from exc\n\n    try:\n        state = DeliveryState(str(data["state"]))\n    except (KeyError, ValueError) as exc:\n        raise LedgerSchemaError("invalid_ledger_state") from exc\n\n    try:\n        return DeliveryRecord(\n            record_id=str(data["record_id"]),\n            schema_version=str(data["schema_version"]),\n            logical_key=str(data["logical_key"]),\n            revision_key=str(data["revision_key"]),\n            operation_key=str(data["operation_key"]),\n            snapshot=snapshot,\n            state=state,\n            state_version=int(data["state_version"]),\n            attempt_count=int(data["attempt_count"]),\n            owner_correlation_id=None if data.get("owner_correlation_id") is None else str(data.get("owner_correlation_id")),\n            owner_expires_at=None if data.get("owner_expires_at") is None else str(data.get("owner_expires_at")),\n            created_at=str(data["created_at"]),\n            updated_at=str(data["updated_at"]),\n            draft_id=None if data.get("draft_id") is None else str(data.get("draft_id")),\n            note_host=None if data.get("note_host") is None else str(data.get("note_host")),\n            last_verified_canonical_hash=(\n                None if data.get("last_verified_canonical_hash") is None else str(data.get("last_verified_canonical_hash"))\n            ),\n            queue_receipt_digest=(\n                None if data.get("queue_receipt_digest") is None else str(data.get("queue_receipt_digest"))\n            ),\n            conflict_category=None if data.get("conflict_category") is None else str(data.get("conflict_category")),\n        )\n    except (KeyError, TypeError, ValueError) as exc:\n        raise LedgerSchemaError("invalid_ledger_record") from exc\n\n'''
if snapshot_marker not in text:
    raise SystemExit('snapshot marker not found')
text = text.replace(snapshot_marker, serialization_block, 1)
ledger_path.write_text(text, encoding='utf-8')

runtime_path = Path('note_delivery_runtime.py')
runtime = runtime_path.read_text(encoding='utf-8')
runtime = runtime.replace(
    '    DeliveryLedgerError,\n    DeliveryRecord,\n',
    '    DeliveryLedger,\n    DeliveryLedgerError,\n    DeliveryRecord,\n',
    1,
)
runtime = runtime.replace('ledger: SQLiteDeliveryLedger,', 'ledger: DeliveryLedger,')
runtime_path.write_text(runtime, encoding='utf-8')
