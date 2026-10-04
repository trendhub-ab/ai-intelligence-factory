#!/usr/bin/env python3
"""Bounded ops-only eyecatch finalizer for the P0-B live-proof candidate.

This wrapper changes only the provider fallback sequence used by the existing
semantic eyecatch layout layer. All publication, canonical-body, title, asset,
Notion, note-mutation, and public-release guards remain owned by the existing
production implementation.
"""
from __future__ import annotations

import argparse
import json

import ready_eyecatch_finalize as ready_finalize
import run180_eyecatch_semantic_layout as semantic_layout

BOUNDED_LAYOUT_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
)


def finalize(sync_id: str) -> dict:
    # Keep the production layer and all existing validators intact; expand only
    # the bounded provider route for this isolated proof branch.
    semantic_layout.EYECATCH_LAYOUT_MODELS = BOUNDED_LAYOUT_MODELS
    semantic_layout.EYECATCH_LAYOUT_MODEL = BOUNDED_LAYOUT_MODELS[0]
    result = ready_finalize.finalize_ready_eyecatch(sync_id)
    result["ops_provider_route"] = list(BOUNDED_LAYOUT_MODELS)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.sync_id), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
