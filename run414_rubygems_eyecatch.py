#!/usr/bin/env python3
"""Run414: exact RubyGems eyecatch bridge.

One Gemini 3.5 request produces only a bounded public headline. The image itself is
rendered with the existing deterministic editorial eyecatch renderer, uploaded to
Notion, and attached to the exact approved Content Intelligence page.
No article body bytes are changed and Gemini 3.8 is intentionally untouched.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import requests

from editorial_eyecatch import generate_note_editorial_eyecatch

PAGE_ID = "3d9479ff-dca9-819a-814c-e4a0aeb3263f"
EXPECTED_TITLE = "OpenAI agents carried out an undisclosed attack on RubyGems"
MODEL = "gemini-3.5-flash"
NOTION_VERSION = "2026-03-11"
CONFIRM = "RUN414_ONEOFF_RUBYGEMS_EYECATCH"
OUTPUT = Path("note_eyecatch_images/run414-rubygems.png")


def _notion_headers(json_content: bool = True) -> dict[str, str]:
    token = (os.getenv("NOTION_API_KEY") or os.getenv("NOTION_DECISION_INTELLIGENCE_API_KEY") or "").strip()
    if not token:
        raise RuntimeError("Notion token required")
    h = {"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION}
    if json_content:
        h["Content-Type"] = "application/json"
    return h


def _plain(values: list[dict] | None) -> str:
    return "".join(str(x.get("plain_text") or ((x.get("text") or {}).get("content")) or "") for x in (values or []))


def _fetch_target() -> dict:
    r = requests.get(f"https://api.notion.com/v1/pages/{PAGE_ID}", headers=_notion_headers(), timeout=30)
    r.raise_for_status()
    page = r.json()
    props = page.get("properties") or {}
    title = _plain((props.get("記事名") or {}).get("title"))
    status = str((((props.get("記事状態") or {}).get("select") or {}).get("name")) or "")
    existing = (props.get("アイキャッチ") or {}).get("files") or []
    if title != EXPECTED_TITLE or status != "Ready":
        raise RuntimeError(f"Run414 exact target mismatch title={title!r} status={status!r}")
    if existing:
        raise RuntimeError("Run414 refuses to overwrite an existing eyecatch")
    return page


def _gemini_headline() -> str:
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY required")
    prompt = f"""You are creating the public eyecatch headline for one Japanese technology-news note article.
Use ONLY this source title; do not invent facts, numbers, names, outcomes, or urgency.
Source title: {EXPECTED_TITLE}
Return JSON only: {{\"headline\":\"...\"}}
Rules: Japanese, 14-26 characters, understandable to a non-specialist, security-news tone, no clickbait, no score, no emoji, no quotation marks, no unsupported claim. Preserve the core fact that AI agents/OpenAI and RubyGems attack are the topic, but do not claim the attack succeeded.
"""
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 120,
            "responseMimeType": "application/json",
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Gemini 3.5 eyecatch brief failed HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        headline = str(json.loads(text).get("headline") or "").strip()
    except Exception as exc:
        raise RuntimeError("Gemini 3.5 eyecatch JSON parse failed") from exc
    headline = re.sub(r"[\r\n\t]+", " ", headline).strip()
    if not (8 <= len(headline) <= 30):
        raise RuntimeError(f"Run414 headline length invalid: {headline!r}")
    forbidden = ("Decision", "Score", "成功", "侵害完了", "緊急", "今すぐ", "100")
    if any(x.lower() in headline.lower() for x in forbidden):
        raise RuntimeError(f"Run414 headline contains forbidden overclaim/internal token: {headline!r}")
    return headline


def _render(headline: str) -> Path:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    generate_note_editorial_eyecatch(
        title=headline,
        summary="OpenAIのAIエージェントとRubyGemsを巡るセキュリティ事例",
        output_path=str(OUTPUT),
        category="SECURITY",
    )
    if not OUTPUT.exists() or OUTPUT.stat().st_size < 10_000:
        raise RuntimeError("Run414 eyecatch render missing or unexpectedly small")
    return OUTPUT


def _upload_to_notion(path: Path) -> str:
    filename = path.name
    create = requests.post(
        "https://api.notion.com/v1/file_uploads",
        headers=_notion_headers(),
        json={"mode": "single_part", "filename": filename, "content_type": "image/png"},
        timeout=30,
    )
    if create.status_code not in (200, 201):
        raise RuntimeError(f"Notion file upload create failed HTTP {create.status_code}: {create.text[:400]}")
    upload_id = str((create.json() or {}).get("id") or "").strip()
    if not upload_id:
        raise RuntimeError("Notion file upload id missing")
    with path.open("rb") as fh:
        send = requests.post(
            f"https://api.notion.com/v1/file_uploads/{upload_id}/send",
            headers=_notion_headers(json_content=False),
            files={"file": (filename, fh, "image/png")},
            timeout=60,
        )
    if send.status_code not in (200, 201):
        raise RuntimeError(f"Notion file upload send failed HTTP {send.status_code}: {send.text[:400]}")
    patch = requests.patch(
        f"https://api.notion.com/v1/pages/{PAGE_ID}",
        headers=_notion_headers(),
        json={"properties": {"アイキャッチ": {"files": [{"name": filename, "type": "file_upload", "file_upload": {"id": upload_id}}]}}},
        timeout=30,
    )
    if patch.status_code != 200:
        raise RuntimeError(f"Notion eyecatch attach failed HTTP {patch.status_code}: {patch.text[:400]}")
    files = (((patch.json().get("properties") or {}).get("アイキャッチ") or {}).get("files") or [])
    if not files:
        raise RuntimeError("Run414 Notion eyecatch postcondition failed")
    return upload_id


def main() -> None:
    if os.getenv("RUN414_CONFIRM", "").strip() != CONFIRM:
        raise RuntimeError("Run414 explicit confirmation missing")
    _fetch_target()
    headline = _gemini_headline()  # exactly one intended Gemini 3.5 request
    path = _render(headline)
    upload_id = _upload_to_notion(path)
    print(json.dumps({
        "run": 414,
        "page_id": PAGE_ID,
        "model": MODEL,
        "gemini_3_8_calls": 0,
        "gemini_3_5_calls": 1,
        "headline": headline,
        "eyecatch_bytes": path.stat().st_size,
        "notion_upload_id": upload_id,
        "attached": True,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
