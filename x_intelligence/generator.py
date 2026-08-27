"""Generate reviewable X drafts from existing Factory intelligence.

Phase 0 constraints:
- zero Gemini calls;
- zero X API calls;
- no automatic posting;
- no mutation of the article-generation pipeline.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_MAX_CHARS = 280


def _first(item: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return default


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _trim(text: str, limit: int) -> str:
    text = _clean(text)
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit == 1:
        return "…"
    return text[: limit - 1].rstrip("、。,. ") + "…"


def _compose(item: Mapping[str, Any]) -> tuple[str, str, str, str, str]:
    title = _clean(_first(item, "name", "Name", "title", "Title"))
    summary = _clean(
        _first(
            item,
            "source_summary",
            "Source Summary",
            "screening_reason",
            "summary",
            "reason",
            "Reason",
        )
    )
    why = _clean(_first(item, "decision_reason", "Decision Reason", "reason", "Reason"))
    action = _clean(_first(item, "action", "Action", "recommended_action", "Recommended Action"))
    source = _clean(_first(item, "source", "Source"))
    url = _clean(_first(item, "x_primary_url", "url", "URL", "source_url", "primary_url"))

    hook = title or summary or "AI最新情報"
    importance = why if why and why != summary else ""
    implication = action
    return hook, summary, importance, implication, source, url


def build_x_post(item: Mapping[str, Any], *, max_chars: int = DEFAULT_MAX_CHARS) -> dict[str, Any]:
    """Build a deterministic Japanese X draft for human review."""

    if max_chars < 80:
        raise ValueError("max_chars must be at least 80")

    hook, summary, importance, implication, source, url = _compose(item)
    if not url:
        raise ValueError("primary source URL is required")

    if source:
        hook = f"【{source}】{hook}"

    sections: list[str] = [_trim(hook, 95)]
    if summary and summary != hook:
        sections.append(_trim(summary, 105))
    if importance:
        sections.append("重要：" + _trim(importance, 70))
    if implication:
        sections.append("見るべき点：" + _trim(implication, 60))

    suffix = f"一次情報：{url}"
    body = "\n\n".join(sections)
    candidate = f"{body}\n\n{suffix}"

    if len(candidate) > max_chars:
        room = max_chars - len(suffix) - 2
        if room <= 0:
            raise ValueError("source URL leaves no room for post body")
        body = _trim(body, room)
        candidate = f"{body}\n\n{suffix}"

    return {
        "status": "X Pending Review",
        "post": candidate,
        "characters": len(candidate),
        "max_characters": max_chars,
        "primary_url": url,
        "source": source,
        "generator_mode": "deterministic_zero_api",
        "gemini_calls": 0,
        "x_api_calls": 0,
        "auto_posted": False,
    }


def render_markdown(draft: Mapping[str, Any]) -> str:
    return (
        "# X Pending Review\n\n"
        f"- Generator: `{draft.get('generator_mode', '')}`\n"
        f"- Characters: {draft.get('characters', 0)} / {draft.get('max_characters', DEFAULT_MAX_CHARS)}\n"
        f"- Gemini calls: {draft.get('gemini_calls', 0)}\n"
        f"- X API calls: {draft.get('x_api_calls', 0)}\n"
        f"- Auto posted: {str(bool(draft.get('auto_posted'))).lower()}\n\n"
        "## Draft\n\n"
        f"{draft.get('post', '')}\n"
    )


def save_pending_post(
    draft: Mapping[str, Any],
    *,
    output_dir: str | Path = "artifacts/x_posts/pending",
    stem: str | None = None,
) -> tuple[Path, Path]:
    """Save JSON + Markdown review artifacts locally only."""

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    safe_stem = stem or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", safe_stem).strip("-") or "x-post"

    json_path = target / f"{safe_stem}.json"
    md_path = target / f"{safe_stem}.md"
    json_path.write_text(json.dumps(dict(draft), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(draft), encoding="utf-8")
    return json_path, md_path
