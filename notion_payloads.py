"""Pure Notion payload shaping extracted from pipeline.py (Run242).

This module performs no network, filesystem, provider, credential, or Notion API access.
Runtime property/status names are supplied explicitly so pipeline.py remains the live policy owner.
"""

import re
from collections.abc import Callable, Mapping
from typing import Any


def _cfg(config: Mapping[str, Any], name: str) -> Any:
    try:
        return config[name]
    except KeyError as exc:
        raise KeyError(f"missing Notion payload config: {name}") from exc


def safe_chunk_text(text: str, limit: int) -> list[str]:
    """Split text at paragraph/sentence boundaries, using hard slicing only as a last resort."""
    if not text:
        return []

    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(line) <= limit:
            current = line
            continue
        sentences = re.findall(r"[^。！？]*[。！？]|[^。！？]+$", line)
        buf = ""
        for sentence in sentences:
            cand = buf + sentence
            if len(cand) <= limit:
                buf = cand
                continue
            if buf:
                chunks.append(buf)
                buf = ""
            if len(sentence) <= limit:
                buf = sentence
            else:
                for i in range(0, len(sentence), limit):
                    chunks.append(sentence[i:i + limit])
        current = buf
    if current:
        chunks.append(current)
    return chunks


def notion_date_property(iso_datetime: str | None) -> dict:
    if not iso_datetime:
        return {"date": None}
    return {"date": {"start": iso_datetime}}


def build_notion_properties(
    repo_name, repo_url, score, score_breakdown_text, what_text,
    why_important_text, why_not_important_text, action_text, spdx_id,
    paradigm_shift_text="", alternative_comparison_text="", migration_cost_text="",
    source: str = "GitHub", engagement: int = 0, title_text: str = "",
    eyecatch_url: str = "", published_at: str | None = None,
    analyzed_at: str | None = None, report_meta: dict | None = None,
    screening_score: int | None = None, screening_reason: str = "",
    *, config: Mapping[str, Any],
) -> dict:
    meta = report_meta or {}
    props = {
        _cfg(config, "PROP_NAME"): {"title": [{"text": {"content": repo_name}}]},
        _cfg(config, "PROP_URL"): {"url": repo_url},
        _cfg(config, "PROP_SOURCE"): {"select": {"name": source}},
        _cfg(config, "PROP_ENGAGEMENT"): {"number": engagement},
        _cfg(config, "PROP_SCORE"): {"number": score},
        _cfg(config, "PROP_STATUS"): {"select": {"name": _cfg(config, "STATUS_DEEP_DIVE")}},
        _cfg(config, "PROP_CONTENT_STATUS"): {"select": {"name": _cfg(config, "CONTENT_STATUS_DEEP_DIVE")}},
        _cfg(config, "PROP_ARTICLE_STATUS"): {"select": {"name": _cfg(config, "ARTICLE_STATUS_READY")}},
        _cfg(config, "PROP_SUBSCRIPTION_VISIBILITY"): {"select": {"name": _cfg(config, "VISIBILITY_SUBSCRIBER_ONLY")}},
        _cfg(config, "PROP_SCORE_BREAKDOWN"): {"rich_text": [{"text": {"content": score_breakdown_text[:2000]}}]},
        _cfg(config, "PROP_WHAT"): {"rich_text": [{"text": {"content": what_text[:2000]}}]},
        _cfg(config, "PROP_WHY_IMPORTANT"): {"rich_text": [{"text": {"content": why_important_text[:2000]}}]},
        _cfg(config, "PROP_WHY_NOT_IMPORTANT"): {"rich_text": [{"text": {"content": why_not_important_text[:2000]}}]},
        _cfg(config, "PROP_WHO"): {"rich_text": [{"text": {"content": "PM / テックリード / 開発チーム"}}]},
        _cfg(config, "PROP_ACTION"): {"rich_text": [{"text": {"content": action_text[:2000]}}]},
        _cfg(config, "PROP_LICENSE"): {"rich_text": [{"text": {"content": spdx_id}}]},
        _cfg(config, "PROP_PARADIGM_SHIFT"): {"rich_text": [{"text": {"content": paradigm_shift_text[:2000]}}]},
        _cfg(config, "PROP_ALTERNATIVE_COMPARISON"): {"rich_text": [{"text": {"content": alternative_comparison_text[:2000]}}]},
        _cfg(config, "PROP_MIGRATION_COST"): {"rich_text": [{"text": {"content": migration_cost_text[:2000]}}]},
        _cfg(config, "PROP_TITLE"): {"rich_text": [{"text": {"content": (title_text or "（タイトル抽出失敗）")[:2000]}}]},
        _cfg(config, "PROP_EYECATCH"): {
            "files": ([{"type": "external", "name": f"{repo_name}.png", "external": {"url": eyecatch_url}}]
                      if eyecatch_url else [])
        },
        _cfg(config, "PROP_PUBLISHED_AT"): notion_date_property(published_at),
        _cfg(config, "PROP_ANALYZED_AT"): notion_date_property(analyzed_at),
        _cfg(config, "PROP_SOURCE_SUMMARY"): {"rich_text": [{"text": {"content": str(meta.get("source_summary_text", ""))[:2000]}}]},
        _cfg(config, "PROP_DECISION"): {"select": {"name": meta.get("decision_text", "WATCH") if meta.get("decision_text") in _cfg(config, "ALLOWED_DECISIONS") else "WATCH"}},
        _cfg(config, "PROP_DECISION_REASON"): {"rich_text": [{"text": {"content": str(meta.get("decision_reason_text", ""))[:2000]}}]},
        _cfg(config, "PROP_WHO_SHOULD_USE"): {"rich_text": [{"text": {"content": str(meta.get("who_should_use_text", ""))[:2000]}}]},
        _cfg(config, "PROP_WHO_SHOULD_NOT_USE"): {"rich_text": [{"text": {"content": str(meta.get("who_should_not_use_text", ""))[:2000]}}]},
        _cfg(config, "PROP_FUTURE_SCENARIO"): {"rich_text": [{"text": {"content": str(meta.get("future_scenario_text", ""))[:2000]}}]},
        _cfg(config, "PROP_ARTICLE_VALUE"): {"number": int(meta.get("article_value", 0) or 0)},
        _cfg(config, "PROP_GROUNDING_STATUS"): {"select": {"name": meta.get("grounding_status", _cfg(config, "GROUNDING_METADATA_ONLY"))}},
        _cfg(config, "PROP_EVIDENCE_URLS"): {"rich_text": [{"text": {"content": str(meta.get("evidence_urls_text", ""))[:2000]}}]},
    }
    if screening_score is not None:
        props[_cfg(config, "PROP_SCREENING_SCORE")] = {"number": screening_score}
    if screening_reason:
        props[_cfg(config, "PROP_SCREENING_REASON")] = {"rich_text": [{"text": {"content": screening_reason[:2000]}}]}
    return props


def build_notion_manuscript_children(
    clean_manuscript: str,
    caption: str,
    *,
    chunker: Callable[[str], list[str]],
) -> list:
    chunks = chunker(clean_manuscript)
    return [{
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [{"type": "text", "text": {"content": chunk}} for chunk in chunks],
            "language": "markdown",
            "caption": [{"type": "text", "text": {"content": caption}}],
        },
    }]


def build_notion_payload(
    repo_name, repo_url, score, score_breakdown_text, what_text,
    why_important_text, why_not_important_text, action_text, spdx_id,
    clean_manuscript, paradigm_shift_text="", alternative_comparison_text="",
    migration_cost_text="", source: str = "GitHub", engagement: int = 0,
    title_text: str = "", eyecatch_url: str = "", published_at: str | None = None,
    analyzed_at: str | None = None, report_meta: dict | None = None,
    screening_score: int | None = None, screening_reason: str = "",
    *, parent: dict,
    build_properties: Callable[..., dict],
    build_children: Callable[[str], list],
) -> dict:
    return {
        "parent": parent,
        "properties": build_properties(
            repo_name, repo_url, score, score_breakdown_text, what_text,
            why_important_text, why_not_important_text, action_text,
            spdx_id, paradigm_shift_text, alternative_comparison_text,
            migration_cost_text, source, engagement, title_text, eyecatch_url,
            published_at, analyzed_at, report_meta, screening_score, screening_reason,
        ),
        "children": build_children(clean_manuscript),
    }


def build_metadata_notion_properties(
    repo_name, repo_url, score, reason, source: str = "GitHub", engagement: int = 0,
    published_at: str | None = None, analyzed_at: str | None = None,
    source_summary: str = "", spdx_id: str = "", *, config: Mapping[str, Any],
) -> dict:
    props = {
        _cfg(config, "PROP_NAME"): {"title": [{"text": {"content": repo_name}}]},
        _cfg(config, "PROP_URL"): {"url": repo_url},
        _cfg(config, "PROP_SOURCE"): {"select": {"name": source}},
        _cfg(config, "PROP_ENGAGEMENT"): {"number": engagement},
        _cfg(config, "PROP_SCORE"): {"number": score},
        _cfg(config, "PROP_STATUS"): {"select": {"name": _cfg(config, "STATUS_STOCKED")}},
        _cfg(config, "PROP_CONTENT_STATUS"): {"select": {"name": _cfg(config, "CONTENT_STATUS_STOCKED")}},
        _cfg(config, "PROP_ARTICLE_STATUS"): {"select": {"name": _cfg(config, "ARTICLE_STATUS_NOT_PLANNED")}},
        _cfg(config, "PROP_SUBSCRIPTION_VISIBILITY"): {"select": {"name": _cfg(config, "VISIBILITY_SUBSCRIBER_ONLY")}},
        _cfg(config, "PROP_SCREENING_SCORE"): {"number": score},
        _cfg(config, "PROP_SCREENING_REASON"): {"rich_text": [{"text": {"content": reason[:2000]}}]},
        _cfg(config, "PROP_SOURCE_SUMMARY"): {"rich_text": [{"text": {"content": (source_summary or "")[:2000]}}]},
        _cfg(config, "PROP_GROUNDING_STATUS"): {"select": {"name": _cfg(config, "GROUNDING_METADATA_ONLY")}},
        _cfg(config, "PROP_SCORE_BREAKDOWN"): {"rich_text": [{"text": {"content": reason[:2000]}}]},
        _cfg(config, "PROP_PUBLISHED_AT"): notion_date_property(published_at),
        _cfg(config, "PROP_ANALYZED_AT"): notion_date_property(analyzed_at),
    }
    if spdx_id:
        props[_cfg(config, "PROP_LICENSE")] = {"rich_text": [{"text": {"content": spdx_id[:2000]}}]}
    return props
