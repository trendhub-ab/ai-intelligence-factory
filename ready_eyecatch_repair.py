#!/usr/bin/env python3
"""Repair missing/stale eyecatches for current Ready manuscripts without regenerating articles.

This is the production generalization of the proven 2026-09-27 eyecatch-only repair path.

Safety boundary:
- only Content Intelligence rows already in Ready are considered;
- the latest persisted manuscript must already satisfy the *current* publication contract;
- article bytes are never regenerated, rewritten, or restamped;
- only missing/stale eyecatch assets are rendered and patched;
- the current eyecatch asset contract binds image URL to public title + eyecatch policy;
- note.com is never opened or mutated here;
- public release is impossible;
- bounded to a small number of newest current Ready rows.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image

import eyecatch_publication_contract as eyecatch_contract
import note_ready_sync as ready_sync
import pipeline
import production_pipeline
import run179_eyecatch_font_refinement as run179


DEFAULT_LIMIT = 1
OUTPUT_DIR = Path(".runtime/ready_eyecatch_repair")


class ReadyEyecatchRepairError(RuntimeError):
    pass


def _normalize_page_id(value: str) -> str:
    return re.sub(r"[^0-9a-fA-F]", "", str(value or "")).lower()


def _reader_summary(manuscript: str) -> str:
    match = re.search(
        r"(?ms)^##\s+どんな内容？\s*\n+(.+?)(?=\n##\s|\n###\s|\Z)",
        str(manuscript or ""),
    )
    text = str(match.group(1) if match else "")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#*_\`>]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        raise ReadyEyecatchRepairError("current Ready manuscript has no reader summary")
    return text[:500]


def _source_pages(target_sync_id: str = "") -> list[dict]:
    payload: dict = {
        "filter": {
            "property": ready_sync.SOURCE_ARTICLE_STATUS,
            "select": {"equals": ready_sync.SOURCE_READY},
        },
        "sorts": [{"timestamp": "last_edited_time", "direction": "descending"}],
    }
    pages = ready_sync._query_db(
        ready_sync.SOURCE_DATA_SOURCE_ID,
        ready_sync.SOURCE_DATABASE_ID,
        payload=payload,
    )
    target = _normalize_page_id(target_sync_id)
    if target_sync_id:
        pages = [
            page for page in pages
            if _normalize_page_id(page.get("id") or "") == target
        ]
        if len(pages) != 1:
            raise ReadyEyecatchRepairError("exact Ready eyecatch target is missing or ambiguous")
    return pages


def _repair_candidate(page: dict) -> tuple[dict, str] | None:
    state = ready_sync._source_state(page)
    if not state:
        return None
    manuscript = ready_sync._source_current_ready_manuscript(state["sync_id"])
    if not manuscript:
        return None
    url = str(state.get("eyecatch_url") or "")
    if url and eyecatch_contract.current_asset_url(url, state["title"]):
        return None
    return state, manuscript


def _patch_source_eyecatch(sync_id: str, title: str, image_url: str) -> None:
    eyecatch_contract.require_current_asset_url(image_url, title)
    response = ready_sync._request(
        "PATCH",
        f"https://api.notion.com/v1/pages/{sync_id}",
        json={
            "properties": {
                ready_sync.SOURCE_EYECATCH: {
                    "files": [{
                        "name": Path(image_url).name,
                        "type": "external",
                        "external": {"url": image_url},
                    }]
                }
            }
        },
    )
    if response.status_code != 200:
        raise ReadyEyecatchRepairError(
            f"Ready eyecatch patch failed: HTTP {response.status_code}"
        )


def _install_runtime_once() -> None:
    pipeline.EYECATCH_GITHUB_BRANCH = "runtime-state"
    run179.ensure_google_font_assets(
        enabled=True,
        logger=getattr(pipeline, "logger", None),
    )
    run179.require_production_japanese_font()
    production_pipeline.install_runtime_layers(pipeline)


def _repair_one(state: dict, manuscript: str) -> dict:
    sync_id = state["sync_id"]
    title = str(state["title"] or "").strip()
    if not title:
        raise ReadyEyecatchRepairError("Ready article has no public title")

    before_sha = hashlib.sha256(manuscript.encode("utf-8")).hexdigest()
    summary = _reader_summary(manuscript)
    category = pipeline.infer_editorial_category(
        title,
        summary,
        str(state.get("source") or ""),
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{sync_id}.png"
    date_label = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y.%m")

    pipeline.generate_note_editorial_eyecatch(
        title,
        summary,
        str(output),
        category=category,
        date_label=date_label,
    )
    with Image.open(output) as image:
        if image.size != (1280, 670) or image.mode != "RGB":
            raise ReadyEyecatchRepairError(
                f"unexpected eyecatch geometry: size={image.size} mode={image.mode}"
            )

    base_filename = f"ready-{sync_id}.png"
    image_url = eyecatch_contract.upload_current_asset_pair(
        pipeline.upload_eyecatch_to_github,
        output,
        base_filename,
        title,
    )
    if not image_url:
        raise ReadyEyecatchRepairError("eyecatch image/manifest upload failed")
    eyecatch_contract.require_current_asset_url(image_url, title)

    _patch_source_eyecatch(sync_id, title, image_url)

    after_manuscript = ready_sync._source_current_ready_manuscript(sync_id)
    after_sha = hashlib.sha256(after_manuscript.encode("utf-8")).hexdigest()
    if not after_manuscript or after_sha != before_sha:
        raise ReadyEyecatchRepairError("manuscript bytes changed during eyecatch-only repair")

    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{sync_id}")
    if response.status_code != 200:
        raise ReadyEyecatchRepairError(
            f"repaired Ready page fetch failed: HTTP {response.status_code}"
        )
    updated = ready_sync._source_state(response.json())
    if not updated:
        raise ReadyEyecatchRepairError("repaired source page is no longer Ready")
    persisted_url = str(updated.get("eyecatch_url") or "")
    if persisted_url != image_url:
        raise ReadyEyecatchRepairError("Ready eyecatch URL did not persist")
    eyecatch_contract.require_current_asset_url(persisted_url, title)

    return {
        "sync_id": sync_id,
        "title": title,
        "category": category,
        "image_url": image_url,
        "body_unchanged": True,
        "body_sha256": after_sha,
        "current_asset": True,
        "article_regeneration": False,
        "article_restamp": False,
        "note_mutation": False,
        "public_release": False,
    }


def repair_current_ready_eyecatches(
    *,
    limit: int = DEFAULT_LIMIT,
    target_sync_id: str = "",
) -> dict:
    limit = max(1, min(3, int(limit)))
    pages = _source_pages(target_sync_id)
    candidates: list[tuple[dict, str]] = []
    stale_or_ineligible = 0
    already_current = 0

    for page in pages:
        state = ready_sync._source_state(page)
        if not state:
            stale_or_ineligible += 1
            continue
        manuscript = ready_sync._source_current_ready_manuscript(state["sync_id"])
        if not manuscript:
            stale_or_ineligible += 1
            continue
        url = str(state.get("eyecatch_url") or "")
        if url and eyecatch_contract.current_asset_url(url, state["title"]):
            already_current += 1
            continue
        candidates.append((state, manuscript))
        if len(candidates) >= limit:
            break

    if target_sync_id and not candidates:
        raise ReadyEyecatchRepairError(
            "exact Ready target does not require a current-policy eyecatch repair"
        )

    repaired: list[dict] = []
    failures: list[dict] = []
    if candidates:
        if not os.environ.get("GEMINI_API_KEY"):
            raise ReadyEyecatchRepairError("GEMINI_API_KEY is required when a repair candidate exists")
        if not os.environ.get("GH_PAT"):
            raise ReadyEyecatchRepairError("GH_PAT is required when a repair candidate exists")
        _install_runtime_once()

    for state, manuscript in candidates:
        try:
            repaired.append(_repair_one(state, manuscript))
        except Exception as exc:
            failures.append({
                "sync_id": state.get("sync_id", ""),
                "error": f"{type(exc).__name__}: {exc}",
            })
            logger = getattr(pipeline, "logger", None)
            if logger is not None:
                logger.warning(
                    "[POST-READY EYECATCH REPAIR FAILED] %s: %s",
                    state.get("sync_id", ""),
                    exc,
                )

    return {
        "status": "post_ready_eyecatch_repair_complete",
        "limit": limit,
        "candidates": len(candidates),
        "repaired": len(repaired),
        "failed": len(failures),
        "already_current": already_current,
        "stale_or_ineligible": stale_or_ineligible,
        "repairs": repaired,
        "failures": failures,
        "article_regeneration": False,
        "article_restamp": False,
        "note_mutation": False,
        "public_release": False,
    }


def main() -> None:
    if not ready_sync.NOTION_API_KEY:
        raise ReadyEyecatchRepairError("NOTION_API_KEY is required")
    if not (ready_sync.SOURCE_DATA_SOURCE_ID or ready_sync.SOURCE_DATABASE_ID):
        raise ReadyEyecatchRepairError("Content Intelligence source DB is not configured")
    limit = int(os.environ.get("READY_EYECATCH_REPAIR_LIMIT", str(DEFAULT_LIMIT)))
    target = os.environ.get("READY_EYECATCH_TARGET_SYNC_ID", "").strip()
    print(json.dumps(
        repair_current_ready_eyecatches(limit=limit, target_sync_id=target),
        ensure_ascii=False,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
