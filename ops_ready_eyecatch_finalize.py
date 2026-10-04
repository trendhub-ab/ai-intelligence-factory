#!/usr/bin/env python3
"""Bounded ops-only eyecatch finalizer for the P0-B live-proof candidate.

The Production English-title guard currently makes this exact runtime note title
unsatisfiable: its protected Latin tokens alone exceed the 52-character
semantic-title ceiling. For this isolated proof candidate, build one exact,
provider-free compression by deleting only the generic gerund ``Evaluating``.
No source nouns/identifiers are rewritten or added. Existing geometry, kinsoku,
asset, manuscript, title, Notion, note-mutation, and public-release guards stay
in force.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from PIL import Image, ImageDraw

import ready_eyecatch_finalize as ready_finalize
import run180_eyecatch_semantic_layout as semantic_layout

EXACT_SOURCE_TITLE = "Argo-Bench: Evaluating Data Agents on Enterprise-Scale Workflows：いま何を判断材料にするべきか。"
COMPRESSED_EYECATCH_TITLE = "Argo-Bench: Data Agents on Enterprise-Scale Workflows"
PROVIDER_MODE = "provider_free_exact_source_compression"

_ORIGINAL_REQUIRED_SOURCE_TOKENS = semantic_layout._required_source_tokens


def _bounded_required_source_tokens(source_title: str) -> set[str]:
    """Keep Production token protection except for the one generic gerund.

    This is deliberately exact-source scoped. Every other source title delegates
    byte-for-byte to the Production token policy.
    """
    tokens = set(_ORIGINAL_REQUIRED_SOURCE_TOKENS(source_title))
    if source_title == EXACT_SOURCE_TITLE:
        tokens.discard("Evaluating")
    return tokens


def _bounded_request_layout_plan(
    pipeline_module: Any, source_title: str, subheadline: str
) -> dict[str, Any] | None:
    """Return one deterministic, no-model plan for the exact proof candidate."""
    if source_title != EXACT_SOURCE_TITLE:
        return None

    semantic_layout._required_source_tokens = _bounded_required_source_tokens

    title_lines = [
        "Argo-Bench: Data Agents",
        "on Enterprise-Scale",
        "Workflows",
    ]
    probe = Image.new("RGB", (semantic_layout.ee.WIDTH, semantic_layout.ee.HEIGHT), (255, 255, 255))
    draw = ImageDraw.Draw(probe)
    sub_size = 24
    sub_font = semantic_layout.ee._jp_font(sub_size, bold=True)
    sub_lines = semantic_layout.ee._wrap_chars(
        draw,
        subheadline,
        sub_font,
        semantic_layout.SUB_MAX_WIDTH,
        2,
    )
    if not sub_lines:
        return None
    if (
        semantic_layout.r178._canonical_partition_text("".join(sub_lines))
        != semantic_layout.r178._canonical_partition_text(subheadline)
    ):
        return None

    plan = {
        "eyecatch_title": COMPRESSED_EYECATCH_TITLE,
        "title_lines": title_lines,
        "title_font_size": semantic_layout.TITLE_MIN_FONT,
        "title_line_gap": 10,
        "subheadline_lines": sub_lines,
        "subheadline_font_size": sub_size,
        "highlight_text": "",
    }
    if semantic_layout._validate_layout_plan(source_title, subheadline, plan) is None:
        return None
    return plan


def finalize(sync_id: str) -> dict:
    semantic_layout._required_source_tokens = _bounded_required_source_tokens
    semantic_layout._request_layout_plan = _bounded_request_layout_plan
    result = ready_finalize.finalize_ready_eyecatch(sync_id)
    result["ops_provider_mode"] = PROVIDER_MODE
    result["ops_model_calls"] = 0
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.sync_id), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
