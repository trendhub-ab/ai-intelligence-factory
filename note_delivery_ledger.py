from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import unicodedata
from typing import Iterable

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
DESTINATION_SURFACE = "private_note_draft"


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


def _normalized_text(value: object) -> str:
    return unicodedata.normalize("NFC", str(value or "")).strip()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
