from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlparse

import note_publication_reconcile as reconcile

from note_document_contract import parse_presentation_markdown
from note_delivery_ledger import (
    DeliveryLedgerError,
    DeliveryRecord,
    DeliverySnapshot,
    DeliveryState,
    SQLiteDeliveryLedger,
    build_delivery_snapshot,
)

RUN222_TRANSFORM_VERSION = "note-presentation-integrity-v1"
READY_PROVENANCE_VERSION = "ready-waiting-current-publication-v1"


@dataclass(frozen=True)
class PreparedDelivery:
    article: Mapping[str, Any]
    snapshot: DeliverySnapshot
    eyecatch_path: Path


def _note_target(base: Any) -> str:
    target = str(os.environ.get("NOTE_TARGET_IDENTITY", "")).strip()
    if not target:
        raise base.NoteDraftError("NOTE_TARGET_IDENTITY is required for durable delivery authority")
    return target


def _asset_identity(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme != "https" or not parsed.path:
        return ""
    return Path(parsed.path).name


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _queue_receipt_digest(binding: reconcile.QueueDraftBinding) -> str:
    material = "\x1f".join(
        (
            binding.page_id,
            binding.sync_id,
            binding.quality,
            binding.posting,
            binding.draft_id,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _prepared_from_article(base: Any, article: Mapping[str, Any]) -> PreparedDelivery:
    value = dict(article)
    sync_id = str(value.get("sync_id") or "").strip().lower()
    queue_page_id = str(value.get("destination_page_id") or "").strip()
    title = str(value.get("title") or "").strip()
    manuscript = str(value.get("manuscript") or "")
    manuscript_sha256 = str(value.get("manuscript_sha256") or "").strip().lower()
    policy_sha256 = str(value.get("publication_policy_sha256") or "").strip().lower()
    publication_contract = str(value.get("publication_contract") or "").strip()
    eyecatch_url = str(value.get("eyecatch_url") or "").strip()
    asset_id = _asset_identity(eyecatch_url)
    if not all((sync_id, queue_page_id, title, manuscript, manuscript_sha256, policy_sha256, publication_contract, asset_id)):
        raise base.NoteDraftError("Delivery source is missing immutable snapshot material")

    try:
        document = parse_presentation_markdown(manuscript)
    except Exception as exc:
        raise base.NoteDraftError("Transformed note manuscript violates the canonical document contract") from exc

    eyecatch_path = Path(base._download_eyecatch(eyecatch_url, sync_id, title))
    if not eyecatch_path.is_file():
        raise base.NoteDraftError("Downloaded eyecatch is unavailable for delivery snapshot")

    snapshot = build_delivery_snapshot(
        sync_id=sync_id,
        queue_page_id=queue_page_id,
        title=title,
        manuscript_sha256=manuscript_sha256,
        publication_policy_sha256=policy_sha256,
        document=document,
        transform_versions=(("run222", RUN222_TRANSFORM_VERSION),),
        eyecatch_sha256=_file_sha256(eyecatch_path),
        eyecatch_asset_id=asset_id,
        note_target=_note_target(base),
        ready_provenance=f"{READY_PROVENANCE_VERSION}:{publication_contract}",
    )
    return PreparedDelivery(MappingProxyType(value), snapshot, eyecatch_path)


def prepare_delivery(base: Any, requested_sync_id: str) -> PreparedDelivery:
    requested = str(requested_sync_id or "").strip().lower()
    article = base._prepare_article(requested)
    prepared = _prepared_from_article(base, article)
    if requested and prepared.snapshot.sync_id != requested:
        raise base.NoteDraftError("VM preparation returned a different sync_id")
    return prepared


def revalidate_before_mutation(base: Any, prepared: PreparedDelivery) -> None:
    current = prepare_delivery(base, prepared.snapshot.sync_id)
    if current.snapshot != prepared.snapshot:
        raise base.NoteDraftError("Delivery snapshot changed before note mutation")


def create_or_resume_delivery(
    base: Any,
    ledger: SQLiteDeliveryLedger,
    prepared: PreparedDelivery,
    *,
    run_correlation_id: str,
) -> DeliveryRecord:
    decision = ledger.begin_or_load(prepared.snapshot, run_correlation_id=run_correlation_id)
    if not decision.creation_authorized:
        return decision.record

    revalidate_before_mutation(base, prepared)
    record = decision.record
    durable_created: DeliveryRecord | None = None
    storage_path = base._decode_storage_state()

    def on_stable_draft_url(draft_url: str) -> None:
        nonlocal durable_created
        draft_id = reconcile.draft_identity_from_url(draft_url, error_type=base.NoteDraftError)
        host = str(urlparse(draft_url).hostname or "").lower()
        durable_created = ledger.record_draft_created(
            record.operation_key,
            draft_id=draft_id,
            note_host=host,
            expected_version=record.state_version,
        )

    try:
        returned_url = base._create_browser_draft(
            prepared.article["title"],
            prepared.article["manuscript"],
            prepared.eyecatch_path,
            storage_path,
            on_stable_draft_url=on_stable_draft_url,
        )
    except Exception:
        if durable_created is None:
            try:
                ledger.record_blocked(
                    record.operation_key,
                    state=DeliveryState.CREATION_UNKNOWN,
                    category="creation_result_ambiguous",
                    expected_version=record.state_version,
                )
            except DeliveryLedgerError:
                pass
        raise
    finally:
        storage_path.unlink(missing_ok=True)

    if durable_created is None:
        try:
            ledger.record_blocked(
                record.operation_key,
                state=DeliveryState.CREATION_UNKNOWN,
                category="stable_draft_identity_not_recorded",
                expected_version=record.state_version,
            )
        except DeliveryLedgerError:
            pass
        raise base.NoteDraftError("Stable note draft identity was not durably recorded")

    returned_id = reconcile.draft_identity_from_url(returned_url, error_type=base.NoteDraftError)
    if returned_id != durable_created.draft_id:
        raise base.NoteDraftError("Browser returned a different stable draft identity")

    verified = ledger.record_verified(
        record.operation_key,
        canonical_sha256=prepared.snapshot.canonical_document_sha256,
        expected_version=durable_created.state_version,
    )
    try:
        binding = reconcile.patch_and_readback_draft_binding(
            prepared.snapshot.queue_page_id,
            expected_sync_id=prepared.snapshot.sync_id,
            draft_id=returned_id,
            error_type=base.NoteDraftError,
        )
    except Exception:
        ledger.record_queue_pending(
            record.operation_key,
            category="queue_readback_unavailable",
            expected_version=verified.state_version,
        )
        raise

    if reconcile.queue_draft_binding_confirmed(
        binding,
        expected_sync_id=prepared.snapshot.sync_id,
        draft_id=returned_id,
    ):
        return ledger.record_queue_confirmed(
            record.operation_key,
            receipt_digest=_queue_receipt_digest(binding),
            expected_version=verified.state_version,
        )

    return ledger.record_queue_pending(
        record.operation_key,
        category="queue_binding_unconfirmed",
        expected_version=verified.state_version,
    )
