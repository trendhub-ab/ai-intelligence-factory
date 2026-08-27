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
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DEFAULT_MAX_CHARS = 280
_TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "source",
}


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


def _contains_japanese(text: str) -> bool:
    return bool(re.search(r"[ぁ-んァ-ン一-龯]", text or ""))


def _clean_source_url(url: str) -> str:
    """Strip tracking noise without breaking functional query parameters."""

    value = _clean(url)
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        return value

    # Product Hunt redirect URLs work without their API campaign query and are
    # dramatically shorter that way.
    if parsed.netloc.lower() == "www.producthunt.com" and parsed.path.startswith("/r/"):
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))

    kept = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        lower = key.lower()
        if lower.startswith("utm_") or lower in _TRACKING_KEYS:
            continue
        kept.append((key, val))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(kept), ""))


def _source_label(item: Mapping[str, Any]) -> str:
    raw = _first(item, "source", "Source")
    aliases = {
        "HackerNews": "HN",
        "Hacker News": "HN",
        "ProductHunt": "Product Hunt",
        "Product Hunt": "Product Hunt",
        "ArXiv": "arXiv",
        "GitHub": "GitHub",
    }
    return aliases.get(raw, raw or "AI")


def _topic_label(item: Mapping[str, Any]) -> str:
    topic = _first(item, "portfolio_topic", "raw_portfolio_topic", "Portfolio Topic").upper()
    return {
        "AGENT": "AIエージェント",
        "MODEL": "AIモデル",
        "DEVTOOLS": "開発ツール",
        "DATA": "AI・データ",
        "SECURITY": "AI・セキュリティ",
        "INFRA": "AIインフラ",
    }.get(topic, "AI")


def _compose(item: Mapping[str, Any]) -> tuple[str, str, str, str]:
    title = _clean(_first(item, "name", "Name", "title", "Title"))
    summary = _clean(
        _first(
            item,
            "source_summary",
            "Source Summary",
            "summary",
            "screening_reason",
            "reason",
            "Reason",
        )
    )
    why = _clean(_first(item, "reason", "Reason", "decision_reason", "Decision Reason"))
    action = _clean(_first(item, "action", "Action", "recommended_action", "Recommended Action"))
    url = _clean_source_url(_first(item, "x_primary_url", "url", "URL", "source_url", "primary_url"))
    return title or "AI最新情報", summary, why, action, url


def _signal_line(item: Mapping[str, Any]) -> str:
    screening = float(item.get("x_screening_score") or 0)
    engagement = float(_first(item, "engagement", "Engagement", default="0") or 0)
    shelf_life = _first(item, "shelf_life", "Shelf Life").upper()

    if engagement >= 300:
        return "海外で大きく反応されている話題です。"
    if screening >= 75:
        return "実務への影響が大きい更新として要チェック。"
    if shelf_life == "FLASH":
        return "速報性が高く、早めに確認したい話題です。"
    return "今後の動きを追う価値がある話題です。"


def build_x_post(item: Mapping[str, Any], *, max_chars: int = DEFAULT_MAX_CHARS) -> dict[str, Any]:
    """Build a deterministic Japanese X draft for human review."""

    if max_chars < 80:
        raise ValueError("max_chars must be at least 80")

    title, summary, why, action, url = _compose(item)
    if not url:
        raise ValueError("primary source URL is required")

    source = _source_label(item)
    topic = _topic_label(item)

    if summary and _contains_japanese(summary):
        hook = f"【{topic}】{summary.rstrip('。')}"
        sections: list[str] = [_trim(hook, 96)]
        if title and _contains_japanese(title) and title not in summary:
            sections.append(_trim(title, 70))
    else:
        sections = [_trim(f"【{topic}】{title}", 96)]
        if summary:
            sections.append(_trim(summary.rstrip("。") + "。", 82))

    sections.append(_signal_line(item))

    if why and why != summary:
        sections.append("注目点：" + _trim(why, 58))
    elif action:
        sections.append("見るべき点：" + _trim(action, 58))

    suffix = f"一次情報（{source}）：{url}"
    body = "\n".join(sections)
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
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    safe_stem = stem or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", safe_stem).strip("-") or "x-post"

    json_path = target / f"{safe_stem}.json"
    md_path = target / f"{safe_stem}.md"
    json_path.write_text(json.dumps(dict(draft), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(draft), encoding="utf-8")
    return json_path, md_path
