#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from PIL import Image

import eyecatch_publication_contract as eyecatch_contract
import note_ready_sync as ready_sync
import pipeline
import production_pipeline
import publication_contract
import run179_eyecatch_font_refinement as run179
from notion_payloads import build_notion_manuscript_children

SYNC_ID = "3e8479ffdca9811db058ccf7d711dd88"
EXPECTED_TITLE = "AIが「目的のために手段を選ばず」セキュリティを突破した日。OpenAIが直面した自律モデルの暴走。"
OUTPUT = Path(".runtime/run169-ready-eyecatch.png")
ASSET_BASE = "run169-ready-eyecatch.png"


class RepairError(RuntimeError):
    pass


def _source_page() -> dict:
    res = ready_sync._request("GET", f"https://api.notion.com/v1/pages/{SYNC_ID}")
    if res.status_code != 200:
        raise RepairError(f"source page fetch failed: HTTP {res.status_code}")
    page = res.json()
    state = ready_sync._source_state(page)
    if state is None:
        raise RepairError("source page is not a valid Ready article")
    if state["title"] != EXPECTED_TITLE:
        raise RepairError(f"unexpected public title: {state['title']!r}")
    return page


def _latest_exact_manuscript() -> str:
    candidates: list[str] = []
    for block in ready_sync._block_children(SYNC_ID):
        body = ready_sync._code_body(block)
        if body and body.startswith(f"# {EXPECTED_TITLE}\n"):
            candidates.append(body)
    if not candidates:
        raise RepairError("no exact stored manuscript found")
    manuscript = candidates[-1]
    if len(manuscript) < 1200:
        raise RepairError("stored manuscript is unexpectedly short")
    return manuscript


def _reader_summary(manuscript: str) -> str:
    match = re.search(r"(?ms)^## どんな内容？\s*\n+(.+?)(?=\n## |\n### )", manuscript)
    text = re.sub(r"\s+", " ", (match.group(1) if match else "")).strip()
    if not text:
        raise RepairError("reader summary could not be extracted")
    return text[:500]


def _patch_source_eyecatch(image_url: str) -> None:
    eyecatch_contract.require_current_asset_url(image_url, EXPECTED_TITLE)
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
    res = ready_sync._request("PATCH", f"https://api.notion.com/v1/pages/{SYNC_ID}", json=payload)
    if res.status_code != 200:
        raise RepairError(f"eyecatch patch failed: HTTP {res.status_code}")


def _restamp_exact_bytes(manuscript: str) -> bool:
    if ready_sync._source_current_ready_manuscript(SYNC_ID) == manuscript:
        return False
    caption = publication_contract.current_ready_caption(manuscript)
    chunks = lambda text: [text[i:i + 1800] for i in range(0, len(text), 1800)]
    children = build_notion_manuscript_children(manuscript, caption, chunker=chunks)
    res = ready_sync._request(
        "PATCH",
        f"https://api.notion.com/v1/blocks/{SYNC_ID}/children",
        json={"children": children},
    )
    if res.status_code != 200:
        raise RepairError(f"publication provenance restamp failed: HTTP {res.status_code}")
    if ready_sync._source_current_ready_manuscript(SYNC_ID) != manuscript:
        raise RepairError("exact manuscript bytes did not survive current-policy restamp")
    return True


def main() -> None:
    if not os.environ.get("NOTION_API_KEY"):
        raise RepairError("NOTION_API_KEY is required")
    if not os.environ.get("GH_PAT"):
        raise RepairError("GH_PAT is required")
    if not os.environ.get("GEMINI_API_KEY"):
        raise RepairError("GEMINI_API_KEY is required")

    _source_page()
    manuscript = _latest_exact_manuscript()
    body_sha_before = hashlib.sha256(manuscript.encode("utf-8")).hexdigest()
    summary = _reader_summary(manuscript)

    pipeline.EYECATCH_GITHUB_BRANCH = "runtime-state"
    run179.ensure_google_font_assets(enabled=True, logger=getattr(pipeline, "logger", None))
    run179.require_production_japanese_font()
    production_pipeline.install_runtime_layers(pipeline)

    category = pipeline.infer_editorial_category(EXPECTED_TITLE, summary, "HackerNews")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pipeline.generate_note_editorial_eyecatch(
        EXPECTED_TITLE,
        summary,
        str(OUTPUT),
        category=category,
        date_label="2026.09",
    )

    with Image.open(OUTPUT) as image:
        if image.size != (1280, 670) or image.mode != "RGB":
            raise RepairError(f"unexpected eyecatch geometry: size={image.size} mode={image.mode}")

    image_url = eyecatch_contract.upload_current_asset_pair(
        pipeline.upload_eyecatch_to_github,
        OUTPUT,
        ASSET_BASE,
        EXPECTED_TITLE,
    )
    if not image_url:
        raise RepairError("eyecatch image/manifest upload failed")
    eyecatch_contract.require_current_asset_url(image_url, EXPECTED_TITLE)

    _patch_source_eyecatch(image_url)
    restamped = _restamp_exact_bytes(manuscript)

    _source_page()
    manuscript_after = ready_sync._source_current_ready_manuscript(SYNC_ID)
    body_sha_after = hashlib.sha256(manuscript_after.encode("utf-8")).hexdigest()
    if body_sha_after != body_sha_before:
        raise RepairError("manuscript bytes changed during eyecatch repair")

    metrics = ready_sync.sync_note_ready_db(target_sync_id=SYNC_ID)
    if metrics.get("source_ready") != 1 or metrics.get("incomplete_publication_assets") != 0:
        raise RepairError(f"exact Ready sync did not become publish-complete: {metrics}")

    print(json.dumps({
        "status": "run169_ready_eyecatch_repaired",
        "sync_id": SYNC_ID,
        "title": EXPECTED_TITLE,
        "category": category,
        "image_url": image_url,
        "current_asset": True,
        "body_unchanged": True,
        "body_sha256": body_sha_after,
        "publication_restamped": restamped,
        "source_ready": metrics.get("source_ready"),
        "incomplete_publication_assets": metrics.get("incomplete_publication_assets"),
        "zero_article_regeneration": True,
        "public_release": False,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
