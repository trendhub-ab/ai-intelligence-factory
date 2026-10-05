from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
import unicodedata
from urllib.parse import urlparse

import note_publication_reconcile as reconcile
from note_delivery_gcs import GCSDeliveryLedger

from note_document_contract import parse_presentation_markdown
from note_delivery_ledger import (
    DeliveryLedger,
    DeliveryLedgerError,
    DeliveryRecord,
    DeliverySnapshot,
    DeliveryState,
    SQLiteDeliveryLedger,
    build_delivery_snapshot,
    logical_delivery_key,
)

RUN222_TRANSFORM_VERSION = "note-presentation-integrity-v1"
READY_PROVENANCE_VERSION = "ready-waiting-current-publication-v1"
NOTE_DELIVERY_LEDGER_BACKEND_ENV = "NOTE_DELIVERY_LEDGER_BACKEND"
NOTE_DELIVERY_LEDGER_BUCKET_ENV = "NOTE_DELIVERY_LEDGER_BUCKET"
NOTE_DELIVERY_LEDGER_PREFIX_ENV = "NOTE_DELIVERY_LEDGER_PREFIX"
NOTE_DELIVERY_LEDGER_PATH_ENV = "NOTE_DELIVERY_LEDGER_PATH"
DEFAULT_GCS_PREFIX = "delivery/v1"


class InplaceUpdateBlocked(DeliveryLedgerError):
    pass


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
        raise base.NoteDraftError("Delivery preparation returned a different sync_id")
    return prepared


def revalidate_before_mutation(base: Any, prepared: PreparedDelivery) -> None:
    current = prepare_delivery(base, prepared.snapshot.sync_id)
    if current.snapshot != prepared.snapshot:
        raise base.NoteDraftError("Delivery snapshot changed before note mutation")


def _logical_key_for_identity(sync_id: str, note_target: str) -> str:
    """Derive the logical key without trusting mutable queue/source state."""
    normalized_sync = unicodedata.normalize("NFC", str(sync_id or "")).strip().lower()
    normalized_target = unicodedata.normalize("NFC", str(note_target or "")).strip()
    identity_only = DeliverySnapshot(
        schema_version="identity-only",
        sync_id=normalized_sync,
        queue_page_id="",
        title_digest="",
        manuscript_sha256="",
        publication_policy_sha256="",
        canonical_document_sha256="",
        canonical_contract_version="",
        normalization_policy_version="",
        transform_versions=(),
        eyecatch_sha256="",
        eyecatch_asset_id="",
        note_target=normalized_target,
        ready_provenance="",
    )
    return logical_delivery_key(identity_only)


def _reconcile_queue_projection(
    base: Any,
    ledger: DeliveryLedger,
    record: DeliveryRecord,
) -> DeliveryRecord:
    """Reconcile Notion as a projection; never grant new draft creation authority."""
    if record.state == DeliveryState.QUEUE_CONFIRMED:
        return record
    if record.state not in {DeliveryState.DRAFT_VERIFIED, DeliveryState.QUEUE_CONFIRMATION_PENDING}:
        return record
    if not record.draft_id:
        return record

    try:
        binding = reconcile.patch_and_readback_draft_binding(
            record.snapshot.queue_page_id,
            expected_sync_id=record.snapshot.sync_id,
            draft_id=record.draft_id,
            error_type=base.NoteDraftError,
        )
    except Exception:
        if record.state == DeliveryState.DRAFT_VERIFIED:
            return ledger.record_queue_pending(
                record.operation_key,
                category="queue_readback_unavailable",
                expected_version=record.state_version,
            )
        return record

    if reconcile.queue_draft_binding_confirmed(
        binding,
        expected_sync_id=record.snapshot.sync_id,
        draft_id=record.draft_id,
    ):
        return ledger.record_queue_confirmed(
            record.operation_key,
            receipt_digest=_queue_receipt_digest(binding),
            expected_version=record.state_version,
        )

    if record.state == DeliveryState.DRAFT_VERIFIED:
        return ledger.record_queue_pending(
            record.operation_key,
            category="queue_binding_unconfirmed",
            expected_version=record.state_version,
        )
    return record


def _resume_existing_delivery(
    base: Any,
    ledger: DeliveryLedger,
    record: DeliveryRecord,
) -> DeliveryRecord:
    """Ledger-first retry table. Existing/ambiguous state never falls through to create."""
    if record.state in {
        DeliveryState.DRAFT_VERIFIED,
        DeliveryState.QUEUE_CONFIRMATION_PENDING,
        DeliveryState.QUEUE_CONFIRMED,
    }:
        return _reconcile_queue_projection(base, ledger, record)
    return record


def delivery_ledger_from_environment() -> DeliveryLedger:
    backend = str(os.environ.get(NOTE_DELIVERY_LEDGER_BACKEND_ENV, "")).strip().lower()
    if not backend:
        raise LedgerUnavailableError("ledger_backend_required")

    if backend == "gcs":
        bucket = str(os.environ.get(NOTE_DELIVERY_LEDGER_BUCKET_ENV, "")).strip()
        if not bucket:
            raise LedgerUnavailableError("gcs_bucket_required")
        prefix = str(os.environ.get(NOTE_DELIVERY_LEDGER_PREFIX_ENV, DEFAULT_GCS_PREFIX)).strip()
        return GCSDeliveryLedger(bucket, prefix=prefix or DEFAULT_GCS_PREFIX)

    if backend == "sqlite":
        raw = str(os.environ.get(NOTE_DELIVERY_LEDGER_PATH_ENV, "")).strip()
        if not raw:
            raise LedgerUnavailableError("sqlite_ledger_path_required")
        return SQLiteDeliveryLedger(Path(raw).expanduser())

    raise LedgerUnavailableError("unsupported_ledger_backend")


def require_inplace_update_allowed(
    ledger: DeliveryLedger,
    *,
    sync_id: str,
    note_target: str,
    draft_id: str,
    current_canonical_sha256: str,
    private_state: bool,
    account_matches: bool,
) -> DeliveryRecord:
    """Authorize only an explicit update of the exact unchanged ledger-bound private draft."""
    logical_key = _logical_key_for_identity(sync_id, note_target)
    record = ledger.get_active_by_logical_key(logical_key)
    if record is None:
        raise InplaceUpdateBlocked("preledger_binding_requires_manual_reconciliation")
    expected_draft = str(record.draft_id or "").strip()
    supplied_draft = str(draft_id or "").strip()
    if not expected_draft or supplied_draft != expected_draft:
        raise InplaceUpdateBlocked("bound_draft_identity_mismatch")
    if record.state not in {
        DeliveryState.DRAFT_VERIFIED,
        DeliveryState.QUEUE_CONFIRMATION_PENDING,
        DeliveryState.QUEUE_CONFIRMED,
    }:
        raise InplaceUpdateBlocked("delivery_state_ambiguous")
    if not private_state:
        raise InplaceUpdateBlocked("bound_draft_not_private")
    if not account_matches:
        raise InplaceUpdateBlocked("bound_draft_foreign")
    verified_hash = str(record.last_verified_canonical_hash or "").strip().lower()
    current_hash = str(current_canonical_sha256 or "").strip().lower()
    if not verified_hash:
        raise InplaceUpdateBlocked("verified_canonical_hash_missing")
    if not current_hash or current_hash != verified_hash:
        raise InplaceUpdateBlocked("human_edit_detected")
    return record


def create_or_resume_delivery(
    base: Any,
    ledger: DeliveryLedger,
    prepared: PreparedDelivery,
    *,
    run_correlation_id: str,
) -> DeliveryRecord:
    decision = ledger.begin_or_load(prepared.snapshot, run_correlation_id=run_correlation_id)
    if not decision.creation_authorized:
        return _resume_existing_delivery(base, ledger, decision.record)

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


def reconcile_exact_delivery(
    base: Any,
    ledger: DeliveryLedger,
    *,
    sync_id: str,
    note_target: str,
) -> dict[str, Any]:
    """Reconstruct one exact delivery from durable authority without creating a draft."""
    logical_key = _logical_key_for_identity(sync_id, note_target)
    record = ledger.get_active_by_logical_key(logical_key)
    if record is None:
        return {
            "status": "manual_reconciliation_required",
            "record": None,
            "draft_id": None,
        }

    record = _resume_existing_delivery(base, ledger, record)
    status_by_state = {
        DeliveryState.QUEUE_CONFIRMED: "queue_confirmed",
        DeliveryState.QUEUE_CONFIRMATION_PENDING: "queue_confirmation_pending",
        DeliveryState.DRAFT_VERIFIED: "queue_confirmation_pending",
        DeliveryState.DRAFT_CREATED: "reconciled_existing",
        DeliveryState.CREATE_INTENT_RECORDED: "creation_unknown",
        DeliveryState.CREATION_UNKNOWN: "creation_unknown",
        DeliveryState.VERIFICATION_BLOCKED: "verification_blocked",
        DeliveryState.CONFLICT: "manual_reconciliation_required",
        DeliveryState.MANUAL_RECONCILIATION_REQUIRED: "manual_reconciliation_required",
    }
    return {
        "status": status_by_state.get(record.state, "manual_reconciliation_required"),
        "record": record,
        "draft_id": record.draft_id,
    }


def safe_delivery_result(
    *,
    status: str,
    telegram_notified: bool = False,
    success: bool = True,
) -> dict[str, Any]:
    return {
        "success": bool(success),
        "status": str(status or "manual_reconciliation_required"),
        "zero_gemini_calls": True,
        "telegram_notified": bool(telegram_notified),
        "public_release": False,
    }


def _status_for_record(record: DeliveryRecord) -> str:
    return {
        DeliveryState.QUEUE_CONFIRMED: "queue_confirmed",
        DeliveryState.QUEUE_CONFIRMATION_PENDING: "queue_confirmation_pending",
        DeliveryState.DRAFT_VERIFIED: "queue_confirmation_pending",
        DeliveryState.DRAFT_CREATED: "reconciled_existing",
        DeliveryState.CREATE_INTENT_RECORDED: "creation_unknown",
        DeliveryState.CREATION_UNKNOWN: "creation_unknown",
        DeliveryState.VERIFICATION_BLOCKED: "verification_blocked",
        DeliveryState.CONFLICT: "manual_reconciliation_required",
        DeliveryState.MANUAL_RECONCILIATION_REQUIRED: "manual_reconciliation_required",
    }.get(record.state, "manual_reconciliation_required")


def install(base: Any) -> Any:
    """Install P0-B last so no write-enabled draft path can bypass durable authority."""
    if getattr(base, "_p0b_durable_delivery_installed", False):
        return base

    def _run(*, confirm: str, requested_sync_id: str = "", prepare_only: bool = False) -> dict[str, Any]:
        if confirm != base.CONFIRM_TOKEN:
            raise base.NoteDraftError(f"Confirmation must equal {base.CONFIRM_TOKEN}")

        reconcile.validate_destination_contract(error_type=base.NoteDraftError)
        ledger = delivery_ledger_from_environment()
        ledger.initialize()
        requested = base._normalize_sync_id(requested_sync_id)
        note_target = _note_target(base)

        try:
            prepared = prepare_delivery(base, requested)
        except base.NoteDraftError:
            if requested and base.ready_sync.classify_exact_delivery_state(requested) == "already_delivered":
                existing = reconcile_exact_delivery(
                    base,
                    ledger,
                    sync_id=requested,
                    note_target=note_target,
                )
                return safe_delivery_result(status=str(existing["status"]))
            raise

        if prepare_only:
            return safe_delivery_result(status="prepared")

        record = create_or_resume_delivery(
            base,
            ledger,
            prepared,
            run_correlation_id=str(os.environ.get("GITHUB_RUN_ID", "local-run")).strip() or "local-run",
        )
        return safe_delivery_result(status=_status_for_record(record))

    base.run = _run
    base._p0b_durable_delivery_installed = True
    return base
