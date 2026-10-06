from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import unicodedata
from typing import Callable, Iterable, TypeVar
from uuid import uuid4

from note_document_contract import (
    CONTRACT_VERSION,
    NORMALIZATION_POLICY_VERSION,
    Document,
    normalize_document,
    render_safe_html,
)

SNAPSHOT_SCHEMA_VERSION = "note-delivery-snapshot-v1"
LOGICAL_KEY_SCHEMA_VERSION = "note-delivery-logical-key-v1"
REVISION_KEY_SCHEMA_VERSION = "note-delivery-revision-key-v1"
OPERATION_KEY_SCHEMA_VERSION = "note-delivery-operation-key-v1"
DELIVERY_RECORD_SCHEMA_VERSION = "note-delivery-record-v1"
DESTINATION_SURFACE = "private_note_draft"
SQLITE_SCHEMA_VERSION = 1


class DeliveryState(str, Enum):
    PREPARED = "PREPARED"
    CREATE_INTENT_RECORDED = "CREATE_INTENT_RECORDED"
    DRAFT_CREATED = "DRAFT_CREATED"
    DRAFT_VERIFIED = "DRAFT_VERIFIED"
    QUEUE_CONFIRMATION_PENDING = "QUEUE_CONFIRMATION_PENDING"
    QUEUE_CONFIRMED = "QUEUE_CONFIRMED"
    CREATION_UNKNOWN = "CREATION_UNKNOWN"
    VERIFICATION_BLOCKED = "VERIFICATION_BLOCKED"
    CONFLICT = "CONFLICT"
    MANUAL_RECONCILIATION_REQUIRED = "MANUAL_RECONCILIATION_REQUIRED"


class DeliveryLedgerError(RuntimeError):
    pass


class LedgerUnavailableError(DeliveryLedgerError):
    pass


class LedgerSchemaError(DeliveryLedgerError):
    pass


class InvalidStateTransition(DeliveryLedgerError):
    pass


class ConcurrentStateChange(DeliveryLedgerError):
    pass


@dataclass(frozen=True)
class DeliverySnapshot:
    schema_version: str
    sync_id: str
    queue_page_id: str
    title_digest: str
    manuscript_sha256: str
    publication_policy_sha256: str
    canonical_document_sha256: str
    canonical_contract_version: str
    normalization_policy_version: str
    transform_versions: tuple[tuple[str, str], ...]
    eyecatch_sha256: str
    eyecatch_asset_id: str
    note_target: str
    ready_provenance: str


@dataclass(frozen=True)
class DeliveryRecord:
    record_id: str
    schema_version: str
    logical_key: str
    revision_key: str
    operation_key: str
    snapshot: DeliverySnapshot
    state: DeliveryState
    state_version: int
    attempt_count: int
    owner_correlation_id: str | None
    owner_expires_at: str | None
    created_at: str
    updated_at: str
    draft_id: str | None
    note_host: str | None
    last_verified_canonical_hash: str | None
    queue_receipt_digest: str | None
    conflict_category: str | None


@dataclass(frozen=True)
class IntentDecision:
    record: DeliveryRecord
    creation_authorized: bool
    reason: str


def _normalized_text(value: object) -> str:
    return unicodedata.normalize("NFC", str(value or "")).strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_document_sha256(document: Document) -> str:
    normalized = normalize_document(document)
    return _sha256_text(render_safe_html(normalized))


def build_delivery_snapshot(
    *,
    sync_id: str,
    queue_page_id: str,
    title: str,
    manuscript_sha256: str,
    publication_policy_sha256: str,
    document: Document,
    transform_versions: Iterable[tuple[str, str]],
    eyecatch_sha256: str,
    eyecatch_asset_id: str,
    note_target: str,
    ready_provenance: str,
) -> DeliverySnapshot:
    normalized_title = _normalized_text(title)
    transforms = tuple(sorted((_normalized_text(k), _normalized_text(v)) for k, v in transform_versions))
    return DeliverySnapshot(
        schema_version=SNAPSHOT_SCHEMA_VERSION,
        sync_id=_normalized_text(sync_id),
        queue_page_id=_normalized_text(queue_page_id),
        title_digest=_sha256_text(normalized_title),
        manuscript_sha256=_normalized_text(manuscript_sha256),
        publication_policy_sha256=_normalized_text(publication_policy_sha256),
        canonical_document_sha256=canonical_document_sha256(document),
        canonical_contract_version=CONTRACT_VERSION,
        normalization_policy_version=NORMALIZATION_POLICY_VERSION,
        transform_versions=transforms,
        eyecatch_sha256=_normalized_text(eyecatch_sha256),
        eyecatch_asset_id=_normalized_text(eyecatch_asset_id),
        note_target=_normalized_text(note_target),
        ready_provenance=_normalized_text(ready_provenance),
    )


def logical_delivery_key(snapshot: DeliverySnapshot) -> str:
    material = {
        "schema_version": LOGICAL_KEY_SCHEMA_VERSION,
        "sync_id": snapshot.sync_id,
        "note_target": snapshot.note_target,
        "destination_surface": DESTINATION_SURFACE,
    }
    return _sha256_text(_canonical_json(material))


def revision_key(snapshot: DeliverySnapshot) -> str:
    material = {
        "schema_version": REVISION_KEY_SCHEMA_VERSION,
        "snapshot": asdict(snapshot),
    }
    return _sha256_text(_canonical_json(material))


def operation_key(snapshot: DeliverySnapshot) -> str:
    material = {
        "schema_version": OPERATION_KEY_SCHEMA_VERSION,
        "logical_delivery_key": logical_delivery_key(snapshot),
        "revision_key": revision_key(snapshot),
    }
    return _sha256_text(_canonical_json(material))


def _snapshot_json(snapshot: DeliverySnapshot) -> str:
    return _canonical_json(asdict(snapshot))


def _snapshot_from_json(value: str) -> DeliverySnapshot:
    data = json.loads(value)
    data["transform_versions"] = tuple(tuple(item) for item in data["transform_versions"])
    return DeliverySnapshot(**data)


_ALLOWED_TRANSITIONS: dict[DeliveryState, frozenset[DeliveryState]] = {
    DeliveryState.CREATE_INTENT_RECORDED: frozenset({
        DeliveryState.DRAFT_CREATED,
        DeliveryState.CREATION_UNKNOWN,
        DeliveryState.CONFLICT,
        DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
    }),
    DeliveryState.DRAFT_CREATED: frozenset({
        DeliveryState.DRAFT_VERIFIED,
        DeliveryState.VERIFICATION_BLOCKED,
        DeliveryState.CONFLICT,
        DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
    }),
    DeliveryState.DRAFT_VERIFIED: frozenset({
        DeliveryState.QUEUE_CONFIRMATION_PENDING,
        DeliveryState.QUEUE_CONFIRMED,
        DeliveryState.VERIFICATION_BLOCKED,
        DeliveryState.CONFLICT,
        DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
    }),
    DeliveryState.QUEUE_CONFIRMATION_PENDING: frozenset({
        DeliveryState.QUEUE_CONFIRMED,
        DeliveryState.VERIFICATION_BLOCKED,
        DeliveryState.CONFLICT,
        DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
    }),
    DeliveryState.CREATION_UNKNOWN: frozenset({
        DeliveryState.DRAFT_CREATED,
        DeliveryState.CONFLICT,
        DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
    }),
    DeliveryState.VERIFICATION_BLOCKED: frozenset({
        DeliveryState.DRAFT_VERIFIED,
        DeliveryState.CONFLICT,
        DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
    }),
}

_T = TypeVar("_T")


class SQLiteDeliveryLedger:
    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path).expanduser()

    def _connect(self) -> sqlite3.Connection:
        try:
            conn = sqlite3.connect(
                str(self.path),
                timeout=5.0,
                isolation_level=None,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA synchronous=FULL")
            mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if str(mode).lower() != "wal":
                conn.close()
                raise LedgerUnavailableError("ledger_wal_unavailable")
            return conn
        except DeliveryLedgerError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise LedgerUnavailableError("ledger_open_failed") from exc

    def initialize(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        except OSError as exc:
            raise LedgerUnavailableError("ledger_parent_unavailable") from exc

        conn: sqlite3.Connection | None = None
        try:
            conn = self._connect()
            version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            if version == 0:
                if tables:
                    raise LedgerSchemaError("unversioned_ledger_schema")
                conn.execute("BEGIN IMMEDIATE")
                try:
                    self._create_schema(conn)
                    conn.execute(f"PRAGMA user_version={SQLITE_SCHEMA_VERSION}")
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    raise
            elif version != SQLITE_SCHEMA_VERSION:
                raise LedgerSchemaError("unsupported_ledger_schema")

            expected = {"deliveries", "logical_bindings", "delivery_events"}
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
            }
            if not expected.issubset(tables):
                raise LedgerSchemaError("incomplete_ledger_schema")
        except LedgerSchemaError:
            raise
        except DeliveryLedgerError:
            raise
        except (OSError, sqlite3.Error) as exc:
            raise LedgerUnavailableError("ledger_initialize_failed") from exc
        finally:
            if conn is not None:
                conn.close()

        try:
            os.chmod(self.path.parent, 0o700)
            os.chmod(self.path, 0o600)
        except OSError as exc:
            raise LedgerUnavailableError("ledger_permissions_failed") from exc

    @staticmethod
    def _create_schema(conn: sqlite3.Connection) -> None:
        statements = (
            """CREATE TABLE deliveries (
                record_id TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL,
                logical_key TEXT NOT NULL,
                revision_key TEXT NOT NULL,
                operation_key TEXT NOT NULL UNIQUE,
                snapshot_json TEXT NOT NULL,
                state TEXT NOT NULL,
                state_version INTEGER NOT NULL,
                attempt_count INTEGER NOT NULL,
                owner_correlation_id TEXT,
                owner_expires_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                stable_draft_id TEXT,
                note_host TEXT,
                last_verified_canonical_hash TEXT,
                queue_receipt_digest TEXT,
                conflict_category TEXT
            )""",
            """CREATE TABLE logical_bindings (
                logical_key TEXT PRIMARY KEY,
                operation_key TEXT NOT NULL UNIQUE,
                draft_id TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(operation_key) REFERENCES deliveries(operation_key)
            )""",
            """CREATE TABLE delivery_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL,
                prior_state TEXT,
                new_state TEXT NOT NULL,
                category TEXT NOT NULL,
                run_correlation_id TEXT,
                state_version INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(record_id) REFERENCES deliveries(record_id)
            )""",
        )
        for statement in statements:
            conn.execute(statement)

    def _transaction(self, fn: Callable[[sqlite3.Connection], _T]) -> _T:
        self.initialize()
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            result = fn(conn)
            conn.execute("COMMIT")
            return result
        except DeliveryLedgerError:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise
        except sqlite3.Error as exc:
            try:
                conn.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            raise LedgerUnavailableError("ledger_transaction_failed") from exc
        finally:
            conn.close()

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> DeliveryRecord:
        return DeliveryRecord(
            record_id=row["record_id"],
            schema_version=row["schema_version"],
            logical_key=row["logical_key"],
            revision_key=row["revision_key"],
            operation_key=row["operation_key"],
            snapshot=_snapshot_from_json(row["snapshot_json"]),
            state=DeliveryState(row["state"]),
            state_version=int(row["state_version"]),
            attempt_count=int(row["attempt_count"]),
            owner_correlation_id=row["owner_correlation_id"],
            owner_expires_at=row["owner_expires_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            draft_id=row["stable_draft_id"],
            note_host=row["note_host"],
            last_verified_canonical_hash=row["last_verified_canonical_hash"],
            queue_receipt_digest=row["queue_receipt_digest"],
            conflict_category=row["conflict_category"],
        )

    @staticmethod
    def _load_operation(conn: sqlite3.Connection, op_key: str) -> DeliveryRecord | None:
        row = conn.execute("SELECT * FROM deliveries WHERE operation_key=?", (op_key,)).fetchone()
        return SQLiteDeliveryLedger._row_to_record(row) if row is not None else None

    def get_by_operation_key(self, op_key: str) -> DeliveryRecord | None:
        self.initialize()
        conn = self._connect()
        try:
            return self._load_operation(conn, op_key)
        except sqlite3.Error as exc:
            raise LedgerUnavailableError("ledger_read_failed") from exc
        finally:
            conn.close()

    def get_active_by_logical_key(self, logical_key: str) -> DeliveryRecord | None:
        self.initialize()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT d.* FROM logical_bindings b JOIN deliveries d ON d.operation_key=b.operation_key "
                "WHERE b.logical_key=?",
                (logical_key,),
            ).fetchone()
            return self._row_to_record(row) if row is not None else None
        except sqlite3.Error as exc:
            raise LedgerUnavailableError("ledger_read_failed") from exc
        finally:
            conn.close()

    def begin_or_load(self, snapshot: DeliverySnapshot, *, run_correlation_id: str) -> IntentDecision:
        op_key = operation_key(snapshot)
        logical_key = logical_delivery_key(snapshot)

        def work(conn: sqlite3.Connection) -> IntentDecision:
            existing = self._load_operation(conn, op_key)
            if existing is not None:
                conn.execute(
                    "UPDATE deliveries SET attempt_count=attempt_count+1, updated_at=? WHERE operation_key=?",
                    (_utc_now(), op_key),
                )
                existing = self._load_operation(conn, op_key)
                if existing is None:
                    raise LedgerUnavailableError("ledger_invariant_missing")
                return IntentDecision(existing, False, "existing_operation")

            active_row = conn.execute(
                "SELECT d.* FROM logical_bindings b JOIN deliveries d ON d.operation_key=b.operation_key "
                "WHERE b.logical_key=?",
                (logical_key,),
            ).fetchone()
            if active_row is not None:
                return IntentDecision(self._row_to_record(active_row), False, "active_logical_delivery")

            now = _utc_now()
            owner_expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
            record_id = uuid4().hex
            conn.execute(
                "INSERT INTO deliveries (record_id, schema_version, logical_key, revision_key, operation_key, "
                "snapshot_json, state, state_version, attempt_count, owner_correlation_id, owner_expires_at, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, ?, ?, ?, ?)",
                (
                    record_id,
                    DELIVERY_RECORD_SCHEMA_VERSION,
                    logical_key,
                    revision_key(snapshot),
                    op_key,
                    _snapshot_json(snapshot),
                    DeliveryState.CREATE_INTENT_RECORDED.value,
                    _normalized_text(run_correlation_id),
                    owner_expires,
                    now,
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO logical_bindings (logical_key, operation_key, draft_id, updated_at) VALUES (?, ?, NULL, ?)",
                (logical_key, op_key, now),
            )
            conn.execute(
                "INSERT INTO delivery_events (record_id, prior_state, new_state, category, run_correlation_id, "
                "state_version, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
                (
                    record_id,
                    DeliveryState.PREPARED.value,
                    DeliveryState.CREATE_INTENT_RECORDED.value,
                    "create_intent_recorded",
                    _normalized_text(run_correlation_id),
                    now,
                ),
            )
            record = self._load_operation(conn, op_key)
            if record is None:
                raise LedgerUnavailableError("ledger_invariant_missing")
            return IntentDecision(record, True, "creation_authorized")

        return self._transaction(work)

    def _transition(
        self,
        op_key: str,
        *,
        new_state: DeliveryState,
        expected_version: int,
        category: str,
        fields: dict[str, object] | None = None,
    ) -> DeliveryRecord:
        fields = dict(fields or {})

        def work(conn: sqlite3.Connection) -> DeliveryRecord:
            current = self._load_operation(conn, op_key)
            if current is None:
                raise InvalidStateTransition("delivery_not_found")
            if current.state_version != expected_version:
                raise ConcurrentStateChange("state_version_mismatch")
            allowed = _ALLOWED_TRANSITIONS.get(current.state, frozenset())
            if new_state not in allowed:
                raise InvalidStateTransition("invalid_state_transition")

            next_version = current.state_version + 1
            now = _utc_now()
            assignments = ["state=?", "state_version=?", "updated_at=?"]
            values: list[object] = [new_state.value, next_version, now]
            column_map = {
                "stable_draft_id": "stable_draft_id",
                "note_host": "note_host",
                "last_verified_canonical_hash": "last_verified_canonical_hash",
                "queue_receipt_digest": "queue_receipt_digest",
                "conflict_category": "conflict_category",
            }
            for key, value in fields.items():
                if key not in column_map:
                    raise InvalidStateTransition("unsupported_transition_field")
                assignments.append(f"{column_map[key]}=?")
                values.append(value)
            values.extend([op_key, expected_version])
            cursor = conn.execute(
                f"UPDATE deliveries SET {', '.join(assignments)} WHERE operation_key=? AND state_version=?",
                tuple(values),
            )
            if cursor.rowcount != 1:
                raise ConcurrentStateChange("state_version_mismatch")

            if "stable_draft_id" in fields:
                conn.execute(
                    "UPDATE logical_bindings SET draft_id=?, updated_at=? WHERE logical_key=? AND operation_key=?",
                    (fields["stable_draft_id"], now, current.logical_key, op_key),
                )
            conn.execute(
                "INSERT INTO delivery_events (record_id, prior_state, new_state, category, run_correlation_id, "
                "state_version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    current.record_id,
                    current.state.value,
                    new_state.value,
                    _normalized_text(category),
                    current.owner_correlation_id,
                    next_version,
                    now,
                ),
            )
            updated = self._load_operation(conn, op_key)
            if updated is None:
                raise LedgerUnavailableError("ledger_invariant_missing")
            return updated

        return self._transaction(work)

    def record_draft_created(
        self,
        operation_key: str,
        *,
        draft_id: str,
        note_host: str,
        expected_version: int,
    ) -> DeliveryRecord:
        draft_id = _normalized_text(draft_id)
        note_host = _normalized_text(note_host)
        if not draft_id or not note_host:
            raise InvalidStateTransition("draft_identity_required")
        return self._transition(
            operation_key,
            new_state=DeliveryState.DRAFT_CREATED,
            expected_version=expected_version,
            category="draft_created",
            fields={"stable_draft_id": draft_id, "note_host": note_host},
        )

    def record_verified(
        self,
        operation_key: str,
        *,
        canonical_sha256: str,
        expected_version: int,
    ) -> DeliveryRecord:
        return self._transition(
            operation_key,
            new_state=DeliveryState.DRAFT_VERIFIED,
            expected_version=expected_version,
            category="draft_verified",
            fields={"last_verified_canonical_hash": _normalized_text(canonical_sha256)},
        )

    def record_queue_pending(
        self,
        operation_key: str,
        *,
        category: str,
        expected_version: int,
    ) -> DeliveryRecord:
        return self._transition(
            operation_key,
            new_state=DeliveryState.QUEUE_CONFIRMATION_PENDING,
            expected_version=expected_version,
            category=category,
            fields={"conflict_category": _normalized_text(category)},
        )

    def record_queue_confirmed(
        self,
        operation_key: str,
        *,
        receipt_digest: str,
        expected_version: int,
    ) -> DeliveryRecord:
        return self._transition(
            operation_key,
            new_state=DeliveryState.QUEUE_CONFIRMED,
            expected_version=expected_version,
            category="queue_confirmed",
            fields={"queue_receipt_digest": _normalized_text(receipt_digest), "conflict_category": None},
        )

    def record_blocked(
        self,
        operation_key: str,
        *,
        state: DeliveryState,
        category: str,
        expected_version: int,
    ) -> DeliveryRecord:
        if state not in {
            DeliveryState.CREATION_UNKNOWN,
            DeliveryState.VERIFICATION_BLOCKED,
            DeliveryState.CONFLICT,
            DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
        }:
            raise InvalidStateTransition("blocked_state_required")
        return self._transition(
            operation_key,
            new_state=state,
            expected_version=expected_version,
            category=category,
            fields={"conflict_category": _normalized_text(category)},
        )
