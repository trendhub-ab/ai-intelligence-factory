#!/usr/bin/env python3
"""Finalize only the eyecatch for one already-current Ready article.

This is the generic Production form of the 2026-09-27 proven eyecatch-only lane:
- the Ready manuscript must already satisfy the current Publication Contract;
- manuscript bytes, title, article status and publication state are never rewritten;
- only the current eyecatch image/manifest pair is generated and the source Notion
  `アイキャッチ` property is patched;
- no note draft is created or published here.

A separate note-cover apply step may consume the resulting current asset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from PIL import Image

import eyecatch_publication_contract as eyecatch_contract
import note_ready_sync as ready_sync
import pipeline
import production_pipeline
import run179_eyecatch_font_refinement as run179

OUTPUT_DIR = Path(".runtime/ready-eyecatch")
ASSET_PREFIX = "ready-eyecatch"


class ReadyEyecatchError(RuntimeError):
    pass


def _normalize_sync_id(value: str) -> str:
    sync_id = re.sub(r"[^0-9a-fA-F]", "", str(value or "")).lower()
    if len(sync_id) != 32:
        raise ReadyEyecatchError("sync_id must be exactly 32 hex characters")
    return sync_id


def _reader_summary(manuscript: str) -> str:
    match = re.search(r"(?ms)^## どんな内容？\s*\n+(.+?)(?=\n## |\n### )", manuscript)
    text = re.sub(r"\s+", " ", (match.group(1) if match else "")).strip()
    if not text:
        raise ReadyEyecatchError("reader summary could not be extracted from current Ready manuscript")
    return text[:500]


def _source_page(sync_id: str) -> dict[str, Any]:
    response = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{sync_id}")
    if response.status_code != 200:
        raise ReadyEyecatchError(f"Content Intelligence source fetch failed: HTTP {response.status_code}")
    page = response.json()
    state = ready_sync._source_state(page)
    if state is None or state.get("sync_id") != sync_id:
        raise ReadyEyecatchError("target is not an exact Ready source row")
    return page


def _patch_source_eyecatch(sync_id: str, image_url: str, title: str) -> None:
    eyecatch_contract.require_current_asset_url(image_url, title)
    payload = {
        "properties": {
            "アイキャッチ": {
                "files": [{
                    "name": Path(image_url).name,
                    "type": "external",
                    "external": {"url": image_url},
                }]
            }
        }
    }
    response = ready_sync._request(
        "PATCH",
        f"https://api.notion.com/v1/pages/{sync_id}",
        json=payload,
    )
    if response.status_code != 200:
        raise ReadyEyecatchError(f"Notion eyecatch-only update failed: HTTP {response.status_code}")


def finalize_ready_eyecatch(sync_id: str) -> dict[str, Any]:
    sync_id = _normalize_sync_id(sync_id)
    if not os.environ.get("NOTION_API_KEY"):
        raise ReadyEyecatchError("NOTION_API_KEY is required")
    if not os.environ.get("GH_PAT"):
        raise ReadyEyecatchError("GH_PAT is required")

    page_before = _source_page(sync_id)
    state_before = ready_sync._source_state(page_before)
    assert state_before is not None
    title = str(state_before["title"])

    manuscript_before = ready_sync._source_current_ready_manuscript(sync_id)
    if not manuscript_before:
        raise ReadyEyecatchError(
            "current Ready manuscript is required; refusing to restamp or regenerate article bytes"
        )
    body_sha_before = hashlib.sha256(manuscript_before.encode("utf-8")).hexdigest()
    summary = _reader_summary(manuscript_before)

    existing_url = str(state_before.get("eyecatch_url") or "")
    if existing_url and eyecatch_contract.current_asset_url(existing_url, title):
        return {
            "status": "ready_eyecatch_already_current",
            "sync_id": sync_id,
            "public_title": title,
            "image_url": existing_url,
            "current_asset": True,
            "body_unchanged": True,
            "title_unchanged": True,
            "article_regeneration": False,
            "note_mutation": False,
            "public_release": False,
        }

    pipeline.EYECATCH_GITHUB_BRANCH = "runtime-state"
    font_status = run179.ensure_google_font_assets(
        enabled=True,
        logger=getattr(pipeline, "logger", None),
    )
    if not font_status.get(str(run179.NOTO_SANS_JP_PATH)):
        raise ReadyEyecatchError("Noto Sans JP production font bootstrap failed")
    run179.require_production_japanese_font()
    production_pipeline.install_runtime_layers(pipeline)

    category = pipeline.infer_editorial_category(title, summary, str(state_before.get("source") or ""))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{sync_id}.png"
    pipeline.generate_note_editorial_eyecatch(
        title,
        summary,
        str(output),
        category=category,
    )

    with Image.open(output) as image:
        if image.size != (1280, 670) or image.mode != "RGB":
            raise ReadyEyecatchError(
                f"unexpected eyecatch geometry: size={image.size} mode={image.mode}"
            )

    image_url = eyecatch_contract.upload_current_asset_pair(
        pipeline.upload_eyecatch_to_github,
        output,
        f"{ASSET_PREFIX}-{sync_id}.png",
        title,
    )
    if not image_url:
        raise ReadyEyecatchError("current eyecatch image/manifest pair upload failed")
    eyecatch_contract.require_current_asset_url(image_url, title)

    _patch_source_eyecatch(sync_id, image_url, title)

    page_after = _source_page(sync_id)
    state_after = ready_sync._source_state(page_after)
    assert state_after is not None
    if str(state_after.get("title") or "") != title:
        raise ReadyEyecatchError("public title changed during eyecatch-only finalization")
    if str(state_after.get("eyecatch_url") or "") != image_url:
        raise ReadyEyecatchError("Notion eyecatch URL did not persist")
    eyecatch_contract.require_current_asset_url(str(state_after["eyecatch_url"]), title)

    manuscript_after = ready_sync._source_current_ready_manuscript(sync_id)
    body_sha_after = hashlib.sha256(manuscript_after.encode("utf-8")).hexdigest()
    if manuscript_after != manuscript_before or body_sha_after != body_sha_before:
        raise ReadyEyecatchError("manuscript bytes changed during eyecatch-only finalization")

    return {
        "status": "ready_eyecatch_finalized",
        "sync_id": sync_id,
        "public_title": title,
        "category": category,
        "image_url": image_url,
        "current_asset": True,
        "size": [1280, 670],
        "body_unchanged": True,
        "body_sha256": body_sha_after,
        "title_unchanged": True,
        "article_regeneration": False,
        "note_mutation": False,
        "public_release": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", default=os.environ.get("TARGET_SYNC_ID", ""))
    args = parser.parse_args()
    print(json.dumps(finalize_ready_eyecatch(args.sync_id), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
