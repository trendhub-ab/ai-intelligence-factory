from __future__ import annotations

import hashlib
from typing import Mapping

from local_skills.production_canary import build_snapshot

from .cases import ReplayCase
from .contract import VARIANTS


def build_current_writer_snapshot(item: ReplayCase) -> dict:
    repo = {
        "name": item.case.title,
        "url": item.primary_url,
        "source": item.source,
    }
    grounding = {"evidence_urls": list(item.case.sources)}
    return build_snapshot(
        repo,
        item.management,
        source=item.source,
        primary_url=item.primary_url,
        grounding=grounding,
    )


def build_blind_package(case_id: str, outputs: Mapping[str, str]) -> tuple[dict, dict[str, str]]:
    missing = [variant for variant in VARIANTS if not str(outputs.get(variant) or "").strip()]
    if missing:
        raise ValueError(f"missing Phase 0 outputs: {missing!r}")

    ordered = sorted(
        VARIANTS,
        key=lambda variant: hashlib.sha256(f"{case_id}|{variant}".encode("utf-8")).hexdigest(),
    )
    labels = ("X", "Y", "Z")
    mapping = dict(zip(labels, ordered, strict=True))
    package = {
        "case_id": case_id,
        "candidates": [
            {"label": label, "article": str(outputs[variant]).strip()}
            for label, variant in mapping.items()
        ],
    }
    return package, mapping
