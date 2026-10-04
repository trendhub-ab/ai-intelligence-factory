from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import urlparse

from note_document_contract import parse_presentation_markdown
from note_delivery_ledger import DeliverySnapshot, build_delivery_snapshot

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
