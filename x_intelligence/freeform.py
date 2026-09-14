"""History-aware, zero-API free composition for Chip.

Free composition stays stylistically flexible, but every publishable candidate
must carry a grounded, conclusion-like Japanese statement from existing Factory
data. We never promote a topic label or headline-like noun phrase into a
"conclusion" just because it came from screening.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .persona import CHIP_PERSONA, validate_chip_text

ANGLES = ("reaction", "plain", "work", "skeptic", "future", "analogy", "question", "observation")
DOG_METAPHORS = tuple(CHIP_PERSONA["allowed_dog_metaphors"])

_STRONG_CONCLUSION_FIELDS = (
    "core_conclusion", "Core Conclusion",
    "source_conclusion", "Source Conclusion",
    "decision_conclusion", "Decision Conclusion",
)
_SUMMARY_FIELDS = ("source_summary", "Source Summary", "summary", "Summary")
_SCREENING_FIELDS = ("screening_reason", "reason", "Reason")

# These patterns require an outcome/predicate, not merely a noun such as
# 「提供」「向上」「破棄」inside a headline-like phrase.
_OUTCOME_PATTERNS = (
    r"できる", r"できた", r"可能にな", r"可能である", r"可能です",
    r"された", r"される", r"している", r"していく", r"となる", r"になった", r"になる",
    r"を公開(?:した|している|する)", r"が公開(?:された|される)",
    r"を提供(?:した|している|する)", r"が提供(?:された|される)",
    r"を追加(?:した|している|する)", r"が追加(?:された|される)",
    r"を廃止(?:した|する)", r"が終了(?:した|する)", r"を開始(?:した|する)",
    r"に変更(?:した|された|する)", r"へ移行(?:した|する)", r"を統合(?:した|する)",
    r"が改善(?:した|する)", r"を削減(?:した|する)", r"が増加(?:した|する)", r"が減少(?:した|する)",
    r"を実行できる", r"で動作(?:した|する)", r"を破棄(?:した|している|する)",
    r"引き下げ(?:られ|た)", r"引き上げ(?:られ|た)", r"整備(?:していく|される|する)",
    r"使える", r"使えない", r"必要になる", r"不要になる",
)


def _first(item: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return default


def _jp(text: str) -> bool:
    return bool(re.search(r"[ぁ-んァ-ン一-龯]", text or ""))


def _clean_sentence(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().rstrip("。")


def _topic(item: Mapping[str, Any]) -> str:
    for key in ("name", "Name", "title", "Title"):
        value = _clean_sentence(_first(item, key))
        if value and _jp(value):
            return value
    return ""


def _is_conclusion_like(value: str) -> bool:
    """Accept only a concrete outcome statement, never a headline-like noun phrase."""
    value = _clean_sentence(value)
    if not value or not _jp(value) or len(value) < 10:
        return False
    return any(re.search(pattern, value) for pattern in _OUTCOME_PATTERNS)


def extract_core_conclusion(item: Mapping[str, Any]) -> tuple[str, str]:
    """Return a grounded Japanese conclusion and its source field.

    Explicit conclusion fields are trusted Factory conclusions. Summary/screening
    fields must contain a concrete outcome predicate. A title or topic label alone
    is never accepted as a conclusion.
    """
    for key in _STRONG_CONCLUSION_FIELDS:
        value = _clean_sentence(_first(item, key))
        if value and _jp(value) and len(value) >= 8:
            return value, key
    for key in _SUMMARY_FIELDS + _SCREENING_FIELDS:
        value = _clean_sentence(_first(item, key))
        if _is_conclusion_like(value):
            return value, key
    raise ValueError("grounded core conclusion is required for Chip free composition")


def _clean_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        return value
    if parsed.netloc.lower() == "www.producthunt.com" and parsed.path.startswith("/r/"):
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    kept = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        low = key.lower()
        if low.startswith("utm_") or low in {"fbclid", "gclid", "ref", "referrer", "source"}:
            continue
        kept.append((key, val))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(kept), ""))


def _url(item: Mapping[str, Any]) -> str:
    return _clean_url(_first(item, "x_primary_url", "url", "URL", "source_url", "primary_url"))


def _pick(options: tuple[str, ...], seed: str, blocked: set[str]) -> str:
    digest = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    ordered = list(options)
    start = digest % len(ordered)
    ordered = ordered[start:] + ordered[:start]
    return next((x for x in ordered if x not in blocked), ordered[0])


def choose_angle(item: Mapping[str, Any], recent: list[Mapping[str, Any]] | None = None) -> str:
    recent = recent or []
    blocked = {str(x.get("angle")) for x in recent[-3:]}
    conclusion, _ = extract_core_conclusion(item)
    lower = conclusion.lower()
    engagement = float(_first(item, "engagement", "Engagement", default="0") or 0)
    screening = float(item.get("x_screening_score") or _first(item, "final_screening_score", "Screening Score", default="0") or 0)
    if any(word in lower for word in ("倫理", "監視", "surveillance", "defcon", "危険", "問題")):
        preferred = ("reaction", "observation", "skeptic", "plain")
    elif any(word in lower for word in ("ロードマップ", "標準", "規格", "protocol", "mcp")):
        preferred = ("future", "analogy", "work", "plain")
    elif any(word in lower for word in ("エージェント", "agent", "ツール", "tool", "アプリ", "機能")):
        preferred = ("work", "question", "plain", "skeptic")
    elif engagement >= 300:
        preferred = ("reaction", "observation", "skeptic", "plain")
    elif screening >= 75:
        preferred = ("work", "plain", "future", "analogy")
    else:
        preferred = ANGLES
    return _pick(preferred, _url(item) + conclusion + str(len(recent)), blocked)


def _dog_flavor(recent: list[Mapping[str, Any]], seed: str) -> str:
    if any(bool(x.get("dog_flavor_used")) for x in recent[-12:]):
        return ""
    digest = int(hashlib.sha256((seed + "dog").encode("utf-8")).hexdigest(), 16)
    if digest % 9 != 0:
        return ""
    return DOG_METAPHORS[digest % len(DOG_METAPHORS)]


def _link_mode(seed: str) -> str:
    digest = int(hashlib.sha256((seed + "link").encode("utf-8")).hexdigest(), 16)
    return "inline" if digest % 5 in {0, 1} else "reference_only"


def _apply_dog_flavor(lines: list[str], dog: str) -> list[str]:
    if not dog:
        return lines
    if dog == "ちょっと耳が立ちました":
        return ["この話、ちょっと耳が立ちました。", *lines]
    if dog == "くんくん調べてみると":
        return ["くんくん調べてみると、思ったより面白い話でした。", *lines]
    if dog == "これは追っておきたい匂いがします":
        return [*lines, "これは追っておきたい匂いがします。"]
    return ["散歩中に拾ったAIニュースです。", *lines]


def _content_lines(angle: str, topic: str, conclusion: str) -> list[str]:
    c = conclusion + "。"
    t = topic + "。" if topic and topic != conclusion else ""
    by_angle = {
        "reaction": ["これはちょっと考えさせられます。", t, c, "ここまで分かると、ニュースの見え方が変わります。"],
        "plain": [t, c, "難しい話でも、結論はここです。"],
        "work": ["仕事目線だと、ここは気になります。", t, c, "自分の作業がどう変わるかで見ると分かりやすいです。"],
        "skeptic": [t, c, "新しい＝使うべき、ではないので、実際のメリットまで見たいところです。"],
        "future": ["数年後に振り返ると、こういう地味な話の方が効いているかもしれません。", t, c, "仕組み側の変化は長く残ります。"],
        "analogy": [t, c, "派手な新製品というより、土台のルールが変わるタイプの話です。"],
        "question": [t, c, "これ、自分の仕事に入れるならどこでしょう。", "使う場面まで考えると見え方が変わります。"],
        "observation": ["最近のAI界隈、性能競争とは別の変化が増えています。", t, c, "結論まで追うと、ニュースはずっと分かりやすいです。"],
    }
    return [line for line in by_angle[angle] if line]


def build_free_chip_post(item: Mapping[str, Any], *, recent: list[Mapping[str, Any]] | None = None, max_chars: int = 280) -> dict[str, Any]:
    recent = list(recent or [])
    conclusion, conclusion_source = extract_core_conclusion(item)
    topic = _topic(item)
    url = _url(item)
    if not url:
        raise ValueError("primary source URL is required")
    angle = choose_angle(item, recent)
    seed = url + conclusion
    dog = _dog_flavor(recent, seed)
    lines = _apply_dog_flavor(_content_lines(angle, topic, conclusion), dog)
    body = "\n\n".join(lines)
    link_mode = _link_mode(seed)
    candidate = body if link_mode == "reference_only" else body + f"\n\n元ネタ（英語）：{url}"
    if len(candidate) > max_chars:
        essential = conclusion + "。"
        if link_mode == "inline":
            source_line = f"元ネタ（英語）：{url}"
            room = max_chars - len(source_line) - 2
            if room < len(essential):
                link_mode = "reference_only"
                candidate = essential
            else:
                candidate = essential + "\n\n" + source_line
        else:
            candidate = essential
    if len(candidate) > max_chars:
        raise ValueError("grounded core conclusion does not fit X character limit")
    validate_chip_text(candidate)
    if conclusion not in candidate:
        raise ValueError("grounded core conclusion was lost during composition")
    return {
        "status": "X Pending Review",
        "character": CHIP_PERSONA["name"],
        "composition_mode": "free_history_aware_zero_api",
        "angle": angle,
        "dog_flavor_used": bool(dog),
        "source_delivery": link_mode,
        "core_conclusion": conclusion,
        "core_conclusion_source": conclusion_source,
        "grounded_conclusion": True,
        "post": candidate,
        "characters": len(candidate),
        "max_characters": max_chars,
        "primary_url": url,
        "gemini_calls": 0,
        "x_api_calls": 0,
        "auto_posted": False,
    }
