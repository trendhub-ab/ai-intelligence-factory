"""Reader-first note manuscript shaping extracted from pipeline.py (Run241).

This module is deterministic and provider/network/persistence free. Pipeline-only dynamic
configuration is passed explicitly by thin compatibility wrappers.
"""

import hashlib
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from candidate_identity import canonicalize_url

DIVIDER_LINE = "\n\n---\n\n"
SOURCE_RIGHTS_NOTE = {
    "HackerNews": (
        "- **出典について**: 本文の技術的な事実・数値は、上記の公式リンクおよび参考情報で確認できる範囲を独自に分析・要約したものです。"
        "リンク先記事本文の著作権は原著作者に帰属します。\n"
    ),
    "ArXiv": (
        "- **出典について**: 本記事はarXivで公開されている論文の要旨・情報を基に"
        "独自に分析・要約したものです。論文本文の著作権は著者に帰属します。\n"
    ),
    "ProductHunt": (
        "- **出典について**: 本記事はProduct Huntで公開されているプロダクト情報を基に"
        "独自に分析・要約したものです。製品名・商標等は各権利者に帰属します。\n"
    ),
}
ARTICLE_DISCLAIMER = (
    "※本記事に含まれる見解・提案は筆者個人の意見であり、特定の効果・成果を保証するものではありません。"
    "導入・利用にあたっては、一次情報と自社の条件を確認してください。\n"
)
_READER_SOURCE_LABELS = {
    "GitHub": "GitHub",
    "HackerNews": "Hacker News",
    "ArXiv": "arXiv",
    "ProductHunt": "Product Hunt",
}
_JST = timezone(timedelta(hours=9))
_BOLD_BOUNDARY_BRACKET_FIXES = [
    (re.compile(r"\*\*「([^「」]+)」\*\*"), r"「**\1**」"),
    (re.compile(r"\*\*『([^『』]+)』\*\*"), r"『**\1**』"),
    (re.compile(r"\*\*（([^（）]+)）\*\*"), r"（**\1**）"),
    (re.compile(r'\*\*"([^"]+)"\*\*'), r'"**\1**"'),
    (re.compile(r"\*\*'([^']+)'\*\*"), r"'**\1**'"),
]


def _fix_bold_boundary_brackets(text: str) -> str:
    for pattern, repl in _BOLD_BOUNDARY_BRACKET_FIXES:
        text = pattern.sub(repl, text)
    return text


def _strip_internal_note_control_lines(text: str) -> tuple[str, int]:
    cleaned, count = re.subn(r"(?mi)^\s*={3,}\s*NOTE_DRAFT_(?:START|END)\s*={0,}\s*$\n?", "", text or "")
    return cleaned.strip(), count


def normalize_markdown_for_note(text: str) -> str:
    if not text:
        return ""
    stripped = text.strip()
    stripped, _ = _strip_internal_note_control_lines(stripped)
    fence_match = re.match(r"^```[a-zA-Z0-9]*\n(.*)\n```$", stripped, re.DOTALL)
    if fence_match:
        stripped = fence_match.group(1)
    stripped = re.sub(r"^\s*・\s*", "- ", stripped, flags=re.MULTILINE)
    stripped = _fix_bold_boundary_brackets(stripped)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()


def _normalize_note_title(title: str) -> str:
    title = re.sub(r"\s+", " ", (title or "").strip().lstrip("#").strip())
    title = title.strip('「」『』"')
    if title and not re.search(r"[。？]$", title):
        title += "。"
    return title


def build_article_attribution_id(source: str, repo_url: str) -> str:
    raw_url = (repo_url or "").strip()
    try:
        identity_url = canonicalize_url(raw_url) or raw_url
    except Exception:
        identity_url = raw_url
    identity = identity_url or f"source:{(source or 'Unknown').strip().lower()}"
    return "aif-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def build_subscription_tracking_url(
    article_id: str,
    landing_url: str | None = None,
    *,
    enabled: bool,
    default_landing_url: str,
    campaign_id: str,
) -> str:
    if not enabled:
        return ""
    base = (landing_url if landing_url is not None else default_landing_url).strip()
    if not base or not article_id:
        return ""
    try:
        parsed = urlparse(base)
    except Exception:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    reserved = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "aif_article_id"}
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in reserved]
    query.extend([
        ("utm_source", "note"),
        ("utm_medium", "free_article"),
        ("utm_campaign", campaign_id),
        ("utm_content", article_id),
        ("aif_article_id", article_id),
    ])
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query, doseq=True), parsed.fragment))


def build_subscription_cta(article_id: str, tracking_url: str = "") -> str:
    if not tracking_url:
        return ""
    return (
        f"{DIVIDER_LINE}"
        "### 調査と判断の時間を減らしたい方へ\n\n"
        "無料記事では重要テーマを最後まで公開しています。会員向けには、"
        "意思決定DBと月次サマリーで、追うべき情報・Evidence・Actionを継続的に整理します。\n\n"
        f"[会員向け意思決定DB＋月次サマリーを見る]({tracking_url})\n"
    )


def _reader_plain_text(text: str) -> str:
    value = normalize_markdown_for_note(str(text or ""))
    if not value:
        return ""
    value = re.sub(r"!\[([^]]*)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"(?m)^#{1,6}\s*", "", value)
    value = re.sub(r"(?m)^\s*[-*+]\s+", "", value)
    value = value.replace("**", "").replace("__", "").replace("`", "")
    value = re.sub(r"https?://\S+", "", value)
    return re.sub(r"\s+", " ", value).strip()


def _compact_reader_summary(text: str, max_chars: int = 110) -> str:
    value = _reader_plain_text(text)
    if not value:
        return ""
    sentences = [m.group(0).strip() for m in re.finditer(r"[^。！？!?]+[。！？!?]?", value) if m.group(0).strip()]
    if sentences:
        first = sentences[0]
        if len(first) <= max_chars:
            return first
    if len(value) <= max_chars:
        return value
    cut = value[:max_chars]
    for sep in ("。", "；", ";", "、", "，", ","):
        pos = cut.rfind(sep)
        if pos >= max_chars // 2:
            candidate = cut[:pos + 1].strip()
            if candidate.endswith(("され、", "して、", "おり、", "ため、", "ので、")):
                continue
            return candidate
    return cut.rstrip("、，, ") + "…"


def _reader_summary_complexity(text: str) -> tuple[int, int]:
    value = _reader_plain_text(text)
    if not value:
        return (10_000, 10_000)
    technical_ids = len(re.findall(r"\b(?:SEP|RFC|CVE)-?\d+\b|`[^`]+`|/[a-z][a-z0-9_-]+", value, re.I))
    ascii_terms = [
        token for token in re.findall(r"\b[A-Za-z][A-Za-z0-9.-]{2,}\b", value)
        if token.upper() not in {"AI", "LLM", "API", "MCP", "OSS", "GITHUB"}
    ]
    list_density = max(0, value.count("、") - 2)
    paren_density = len(re.findall(r"[（(][^）)]{8,}[）)]", value))
    return (technical_ids * 8 + len(ascii_terms) * 2 + list_density * 2 + paren_density, len(value))


def _pick_reader_summary_candidate(candidates: list[str]) -> str:
    usable = []
    for candidate in candidates:
        compact = _compact_reader_summary(candidate)
        if compact:
            usable.append(compact)
    if not usable:
        return ""
    return min(usable, key=_reader_summary_complexity)


def _find_reader_intro_fact_sentence(intro: str) -> str:
    value = _reader_plain_text(intro)
    if not value:
        return ""
    for match in re.finditer(r"[^。！？!?]+[。！？!?]?", value):
        sentence = match.group(0).strip()
        if re.search(r"公開|発表|公表|リリース|登場|策定|提示|示され", sentence):
            return sentence
    return ""


def _reader_decision_fallback(decision_text: str) -> str:
    return {
        "NOW": "現時点で、具体的な導入・検証判断を進める価値があります。",
        "TRY": "まずは限定した環境で小さく試し、条件を確かめる価値があります。",
        "WATCH": "今は導入を急がず、追加Evidenceと今後の動きを追うのが妥当です。",
        "WAIT": "現時点では導入を急がず、条件とEvidenceが整うまで待つのが妥当です。",
        "AVOID": "現時点では採用を見送り、代替手段を優先するのが妥当です。",
    }.get((decision_text or "").strip().upper(), "")


def build_reader_first_summary(
    parsed: dict,
    *,
    extract_section,
    display_heading_aliases,
    replace_public_decision_code_leaks,
) -> dict[str, str]:
    parsed = parsed or {}
    draft = str(parsed.get("note_draft") or "")
    intro = extract_section(draft, display_heading_aliases("intro"))
    conclusion = extract_section(draft, display_heading_aliases("conclusion"))
    final = extract_section(draft, display_heading_aliases("final"))
    what = _pick_reader_summary_candidate([
        parsed.get("source_summary_text", ""),
        _find_reader_intro_fact_sentence(intro),
        parsed.get("what_text", ""),
    ])
    why = _compact_reader_summary(parsed.get("why_important_text") or conclusion)
    decision = _compact_reader_summary(final or parsed.get("action_text") or parsed.get("decision_reason_text"))
    if not decision:
        decision = _reader_decision_fallback(str(parsed.get("decision_text") or ""))
    decision_code_phrases = {
        "NOW": "今すぐ着手する", "TRY": "限定的に試す", "WATCH": "今後の動きを注視する",
        "WAIT": "条件が整うまで待つ", "AVOID": "現時点では採用を見送る",
    }
    if decision:
        decision, _ = replace_public_decision_code_leaks(decision, decision_code_phrases)
        for code, phrase in decision_code_phrases.items():
            decision = re.sub(rf"\b{code}\b", phrase, decision)
        decision = re.sub(r"\s{2,}", " ", decision).strip()
    return {"what": what, "why": why, "decision": decision}


def _reader_published_date(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(_JST)
        return dt.date().isoformat()
    except ValueError:
        match = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
        return match.group(1) if match else ""


def build_reader_first_header(reader_summary: dict | None, repo_name: str, repo_url: str,
                              source: str = "GitHub", published_at: str | None = None) -> str:
    summary = reader_summary or {}
    rows = [
        ("何が出た？", _compact_reader_summary(summary.get("what", ""))),
        ("なぜ重要？", _compact_reader_summary(summary.get("why", ""))),
        ("結論は？", _compact_reader_summary(summary.get("decision", ""))),
    ]
    rows = [(label, value) for label, value in rows if value]
    if not rows and not repo_url:
        return ""
    lines: list[str] = []
    if rows:
        lines.extend(["## 30秒でわかるこの記事", ""])
        for idx, (label, value) in enumerate(rows):
            if idx:
                lines.append("")
            lines.extend([f"**{label}**  ", value])
    if repo_url:
        if lines:
            lines.append("")
        lines.extend(["### 元情報", f"- **主一次情報**: [{repo_name}]({repo_url})"])
        lines.append(f"- **発見経路**: {_READER_SOURCE_LABELS.get(source, source)}")
        published = _reader_published_date(published_at)
        if published:
            lines.append(f"- **公開・更新**: {published}")
    return "\n".join(lines).strip()


def _remove_markdown_sections(markdown_text: str, headings: list[str]) -> str:
    if not markdown_text or not headings:
        return markdown_text or ""
    alternatives = "|".join(re.escape(h) for h in sorted(set(headings), key=len, reverse=True))
    pattern = re.compile(rf"(?ms)^#{{2,6}}\s*(?:{alternatives})\s*$\n?.*?(?=^#{{2,6}}\s+|\Z)")
    return pattern.sub("", markdown_text).strip()


def _remove_reader_redundant_provenance(markdown_text: str) -> str:
    if not markdown_text:
        return ""
    pattern = re.compile(
        r"(?m)^[ \t]*(?:本記事|本稿|この記事)は、?[^\n。！？]{0,220}"
        r"(?:一次情報|公開情報|公式(?:ブログ|資料|ドキュメント|リポジトリ|情報))[^\n。！？]{0,160}"
        r"(?:基づいて|基づき|もとに)[^\n。！？]*[。！？][ \t]*$"
    )
    cleaned = pattern.sub("", markdown_text)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def _prepare_reader_first_body(markdown_text: str, reader_summary: dict | None, *, display_heading_aliases) -> str:
    body = markdown_text or ""
    if not reader_summary:
        return body
    body = _remove_reader_redundant_provenance(body)
    body = _remove_markdown_sections(body, display_heading_aliases("conclusion"))
    return body.strip()


def build_clean_note_manuscript(
    note_draft: str,
    repo_name: str,
    repo_url: str,
    spdx_id: str,
    source: str = "GitHub",
    evidence_urls: list[str] | None = None,
    title_text: str = "",
    discovery_url: str = "",
    reader_summary: dict | None = None,
    published_at: str | None = None,
    *,
    split_free_paid,
    display_heading_aliases,
    subscription_enabled: bool,
    subscription_landing_url: str,
    subscription_campaign_id: str,
) -> str:
    free_part, paid_part = split_free_paid(note_draft, repo_name)
    free_clean = normalize_markdown_for_note(free_part)
    paid_clean = normalize_markdown_for_note(paid_part)
    free_clean = _prepare_reader_first_body(free_clean, reader_summary, display_heading_aliases=display_heading_aliases)
    paid_clean = _prepare_reader_first_body(paid_clean, reader_summary, display_heading_aliases=display_heading_aliases)
    display_title = _normalize_note_title(title_text)
    manuscript_parts: list[str] = []
    if display_title:
        manuscript_parts.append(f"# {display_title}")
    reader_header = build_reader_first_header(reader_summary, repo_name, repo_url, source, published_at)
    if reader_header:
        manuscript_parts.append(reader_header)
    if free_clean:
        manuscript_parts.append(free_clean)
    if paid_clean:
        manuscript_parts.append(paid_clean)
    manuscript = "\n\n".join(manuscript_parts)
    if source == "GitHub":
        rights_line = (
            f"- **ライセンス**: {spdx_id}\n\n"
            f"※本記事はライセンスが公開・再利用可能な条件（MIT / Apache-2.0 / BSD / CC-BY-4.0等）"
            f"であることを確認した上で分析・要約しています。\n"
        )
    else:
        rights_line = SOURCE_RIGHTS_NOTE.get(source, "")
    source_label = _READER_SOURCE_LABELS.get(source, source)
    source_block = (
        f"{DIVIDER_LINE}"
        f"### Sources / Evidence\n"
        f"- **発見経路**: {source_label}\n"
        f"- **主一次情報**: [{repo_name}]({repo_url})\n"
        f"{rights_line}"
    )
    unique_evidence = []
    for item in evidence_urls or []:
        if not item or item == repo_url or item in unique_evidence:
            continue
        if item.startswith(("http://", "https://")):
            unique_evidence.append(item)
        if len(unique_evidence) >= 3:
            break
    if unique_evidence:
        source_block += "\n### 補助Evidence\n" + "\n".join(f"- {u}" for u in unique_evidence) + "\n"
    if discovery_url and discovery_url != repo_url:
        source_block += f"- **関連情報**: 発見元の[{source}投稿]({discovery_url})\n"
    article_id = build_article_attribution_id(source, repo_url)
    tracking_url = build_subscription_tracking_url(
        article_id,
        enabled=subscription_enabled,
        default_landing_url=subscription_landing_url,
        campaign_id=subscription_campaign_id,
    )
    subscription_cta = build_subscription_cta(article_id, tracking_url)
    if subscription_cta:
        manuscript += "\n\n" + subscription_cta
    manuscript += source_block + "\n" + ARTICLE_DISCLAIMER
    return manuscript.strip()
