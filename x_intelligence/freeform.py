"""History-aware, zero-API free composition for Chip.

This module deliberately avoids fixed post templates. It selects a conversational
angle and surface structure from existing Factory signals while remembering the
recent batch to reduce repetition.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

from .persona import CHIP_PERSONA, validate_chip_text

ANGLES = ("reaction", "plain", "work", "skeptic", "future", "analogy", "question", "observation")
DOG_METAPHORS = tuple(CHIP_PERSONA["allowed_dog_metaphors"])


def _first(item: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return default


def _jp(text: str) -> bool:
    return bool(re.search(r"[ぁ-んァ-ン一-龯]", text or ""))


def _fact(item: Mapping[str, Any]) -> str:
    for key in ("source_summary", "Source Summary", "summary", "screening_reason", "reason", "Reason", "name", "Name", "title", "Title"):
        value = _first(item, key)
        if value and _jp(value):
            return value.rstrip("。")
    return _first(item, "name", "Name", "title", "Title", default="AIの新しい動き").rstrip("。")


def _url(item: Mapping[str, Any]) -> str:
    return _first(item, "x_primary_url", "url", "URL", "source_url", "primary_url")


def _pick(options: tuple[str, ...], seed: str, blocked: set[str]) -> str:
    digest = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16)
    ordered = list(options)
    start = digest % len(ordered)
    ordered = ordered[start:] + ordered[:start]
    return next((x for x in ordered if x not in blocked), ordered[0])


def choose_angle(item: Mapping[str, Any], recent: list[Mapping[str, Any]] | None = None) -> str:
    recent = recent or []
    blocked = {str(x.get("angle")) for x in recent[-3:]}
    engagement = float(_first(item, "engagement", "Engagement", default="0") or 0)
    screening = float(item.get("x_screening_score") or _first(item, "final_screening_score", "Screening Score", default="0") or 0)
    preferred: tuple[str, ...]
    if engagement >= 300:
        preferred = ("reaction", "question", "observation", "skeptic")
    elif screening >= 75:
        preferred = ("work", "plain", "future", "analogy")
    else:
        preferred = ANGLES
    seed = _url(item) + _fact(item) + str(len(recent))
    return _pick(preferred, seed, blocked)


def _dog_flavor(recent: list[Mapping[str, Any]], seed: str) -> str:
    # At most once per 12 recent posts; never a dog-like sentence ending.
    if any(bool(x.get("dog_flavor_used")) for x in recent[-12:]):
        return ""
    digest = int(hashlib.sha256((seed + "dog").encode("utf-8")).hexdigest(), 16)
    if digest % 7 != 0:
        return ""
    return DOG_METAPHORS[digest % len(DOG_METAPHORS)]


def build_free_chip_post(
    item: Mapping[str, Any], *, recent: list[Mapping[str, Any]] | None = None, max_chars: int = 280
) -> dict[str, Any]:
    recent = list(recent or [])
    fact = _fact(item)
    url = _url(item)
    if not url:
        raise ValueError("primary source URL is required")
    angle = choose_angle(item, recent)
    seed = url + fact
    dog = _dog_flavor(recent, seed)

    lines_by_angle = {
        "reaction": ["これはちょっと気になりました。", fact + "。", "話題の派手さより、この先どこに効いてくるかを見たいです。"],
        "plain": [fact + "。", "難しく見えますが、要するに『何が変わるのか』だけ押さえれば十分です。"],
        "work": ["仕事目線で見ると、ここはチェックしておきたいです。", fact + "。", "新機能そのものより、自分の作業が1つ減るかで見ると分かりやすい。"],
        "skeptic": ["これ、本当に必要？という目線で見ています。", fact + "。", "新しい＝使うべき、ではないので、実際に何が楽になるかが本題です。"],
        "future": ["数年後に振り返ると、こういう話の方が効いているかもしれません。", fact + "。", "今は地味でも、仕組み側の変化は追っておきたいです。"],
        "analogy": [fact + "。", "たとえるなら、新しい家電より『コンセントの規格が変わる』タイプの話に近いかもしれません。"],
        "question": ["これ、みなさんなら使いますか？", fact + "。", "便利そう、で終わらず、自分の仕事に置き換えると見え方が変わります。"],
        "observation": ["最近のAIニュースを見ていて感じるのですが、主役が少しずつ変わっています。", fact + "。", "性能競争だけ追うより、使われ方の変化を見る方が面白いです。"],
    }
    lines = list(lines_by_angle[angle])
    if dog:
        lines.insert(1, dog + "。")
    source_line = f"元ネタ（英語）：{url}"
    body = "\n\n".join(lines)
    candidate = body + "\n\n" + source_line
    if len(candidate) > max_chars:
        room = max_chars - len(source_line) - 2
        body = body[: max(0, room - 1)].rstrip("、。,. ") + "…"
        candidate = body + "\n\n" + source_line
    if len(candidate) > max_chars:
        raise ValueError("source URL leaves no room for free-form post")
    validate_chip_text(candidate)
    return {
        "status": "X Pending Review",
        "character": CHIP_PERSONA["name"],
        "composition_mode": "free_history_aware_zero_api",
        "angle": angle,
        "dog_flavor_used": bool(dog),
        "post": candidate,
        "characters": len(candidate),
        "max_characters": max_chars,
        "primary_url": url,
        "gemini_calls": 0,
        "x_api_calls": 0,
        "auto_posted": False,
    }
