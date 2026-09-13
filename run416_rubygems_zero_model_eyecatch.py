#!/usr/bin/env python3
"""Run416: zero-model one-off RubyGems eyecatch fallback.

After two successful HTTP responses from Gemini 3.5 produced no usable headline
payload, stop spending quota. Reuse the exact-page guards and deterministic
renderer/upload path from Run414/415 with a source-faithful fixed headline.
"""
from __future__ import annotations

import json
import os

import run414_rubygems_eyecatch as bridge

CONFIRM = "RUN416_ONEOFF_RUBYGEMS_ZERO_MODEL_EYECATCH"
HEADLINE = "AIエージェントがRubyGemsを攻撃"


def main() -> None:
    if os.getenv("RUN416_CONFIRM", "").strip() != CONFIRM:
        raise RuntimeError("Run416 explicit confirmation missing")
    bridge._fetch_target()
    path = bridge._render(HEADLINE)
    upload_id = bridge._upload_to_notion(path)
    print(json.dumps({
        "run": 416,
        "page_id": bridge.PAGE_ID,
        "gemini_calls": 0,
        "headline": HEADLINE,
        "eyecatch_bytes": path.stat().st_size,
        "notion_upload_id": upload_id,
        "attached": True,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
