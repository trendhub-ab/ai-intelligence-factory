#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from PIL import Image

import eyecatch_publication_contract as contract
import pipeline
import production_pipeline
import run_vtcode_existing_draft_repair as repair

OUTPUT = Path(".runtime/vtcode-production-eyecatch.png")
ASSET_BASE = "vtcode-production-eyecatch.png"


def _reader_summary(manuscript: str) -> str:
    match = re.search(r"(?ms)^## どんな内容？\s*\n+(.+?)(?=\n## |\n### )", manuscript)
    text = re.sub(r"\s+", " ", (match.group(1) if match else "")).strip()
    if not text:
        raise RuntimeError("VT Code reader summary could not be extracted")
    return text[:500]


def main() -> None:
    target_branch = os.environ.get("TARGET_ASSET_BRANCH", "").strip()
    if not target_branch:
        raise RuntimeError("TARGET_ASSET_BRANCH is required")
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is required")
    if not os.environ.get("GH_PAT"):
        raise RuntimeError("GH_PAT is required")

    # Keep execution code and generated publication asset on separate branches.
    pipeline.EYECATCH_GITHUB_BRANCH = target_branch

    production_pipeline.install_runtime_layers(pipeline)

    title = repair.NEW_TITLE
    manuscript = repair.load_manuscript()
    summary = _reader_summary(manuscript)
    category = pipeline.infer_editorial_category(title, summary, "HackerNews")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pipeline.generate_note_editorial_eyecatch(
        title,
        summary,
        str(OUTPUT),
        category=category,
        date_label="2026.09",
    )

    with Image.open(OUTPUT) as image:
        if image.size != (1280, 670):
            raise RuntimeError(f"production eyecatch size mismatch: {image.size}")

    image_url = contract.upload_current_asset_pair(
        pipeline.upload_eyecatch_to_github,
        OUTPUT,
        ASSET_BASE,
        title,
    )
    if not image_url:
        raise RuntimeError("current eyecatch image/manifest pair upload failed")
    contract.require_current_asset_url(image_url, title)

    expected_filename = contract.versioned_image_filename(ASSET_BASE, title)
    if not image_url.endswith("/" + expected_filename):
        raise RuntimeError("uploaded image URL does not match current contract filename")

    print(json.dumps({
        "status": "vtcode_production_eyecatch_generated",
        "public_title": title,
        "category": category,
        "size": [1280, 670],
        "current_asset": True,
        "asset_branch": target_branch,
        "asset_filename": expected_filename,
        "manifest_filename": contract.manifest_filename(expected_filename),
        "image_url": image_url,
        "public_release": False,
        "note_mutation": False,
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
