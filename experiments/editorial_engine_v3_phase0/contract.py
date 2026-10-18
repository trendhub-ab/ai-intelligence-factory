from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Iterable, Mapping

MINIMUM_CASES = 3
VARIANTS = (
    "A_CURRENT_WRITER",
    "B_PERSONA_ONLY",
    "C_EDITORIAL_ENGINE",
)
EDITORIAL_STAGES = (
    "Writer Reaction",
    "Editorial Discovery",
    "Cognitive Shift",
    "Persona Article Generation",
    "Fact-Safe Review",
)


def validate_article_layout(article: str) -> None:
    """Reject unreadable Markdown articles, without rewriting provider output."""
    lines = article.strip().splitlines()
    if not lines or not re.match(r"^#\s+\S", lines[0]):
        raise ValueError("invalid article layout: missing Markdown H1 title")

    in_fence = False
    fence_char = ""
    fence_length = 0
    has_body = False
    for line in lines[1:]:
        fence = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence:
            token = fence.group(1)
            if not in_fence:
                in_fence = True
                fence_char, fence_length = token[0], len(token)
                continue
            if token[0] == fence_char and len(token) >= fence_length:
                in_fence = False
                continue
        if in_fence:
            continue

        # Literal backslash+n is valid in code examples, not as an article line break.
        outside_inline_code = re.sub(r"`+[^`]*`+", "", line)
        if r"\n" in outside_inline_code:
            raise ValueError("invalid article layout: literal escaped newline in prose")
        if outside_inline_code.strip() and not outside_inline_code.lstrip().startswith("#"):
            has_body = True

    if r"\n" in re.sub(r"`+[^`]*`+", "", lines[0]):
        raise ValueError("invalid article layout: literal escaped newline in title")
    if not has_body:
        raise ValueError("invalid article layout: missing article body")


@dataclass(frozen=True, slots=True)
class Phase0Case:
    """Immutable shared input for one Phase 0 Ready-article replay case."""

    case_id: str
    title: str
    evidence: tuple[str, ...]
    facts: tuple[str, ...]
    sources: tuple[str, ...]
    target_reader: str

    def __post_init__(self) -> None:
        if not self.case_id.strip():
            raise ValueError("case_id must not be blank")
        if not self.title.strip():
            raise ValueError("title must not be blank")
        if not self.evidence:
            raise ValueError("evidence must not be empty")
        if not self.facts:
            raise ValueError("facts must not be empty")
        if not self.sources:
            raise ValueError("sources must not be empty")
        if not self.target_reader.strip():
            raise ValueError("target_reader must not be blank")

    def shared_payload(self, variant: str) -> Mapping[str, object]:
        _validate_variant(variant)
        return MappingProxyType(
            {
                "case_id": self.case_id,
                "title": self.title,
                "evidence": self.evidence,
                "facts": self.facts,
                "sources": self.sources,
                "target_reader": self.target_reader,
                "variant": variant,
            }
        )

    def stages_for(self, variant: str) -> tuple[str, ...]:
        _validate_variant(variant)
        if variant == "A_CURRENT_WRITER":
            return ("Current Writer",)
        if variant == "B_PERSONA_ONLY":
            return ("Persona Narrative", "Article Writing")
        return EDITORIAL_STAGES

    def assert_generated_facts_are_allowed(self, generated_facts: Iterable[str]) -> None:
        allowed = set(self.facts)
        unexpected = tuple(fact for fact in generated_facts if fact not in allowed)
        if unexpected:
            raise ValueError(f"external facts are forbidden: {unexpected!r}")


def _validate_variant(variant: str) -> None:
    if variant not in VARIANTS:
        raise ValueError(f"unknown Phase 0 variant: {variant}")


def validate_phase0_cases(cases: Iterable[Phase0Case]) -> tuple[Phase0Case, ...]:
    materialized = tuple(cases)
    if len(materialized) < MINIMUM_CASES:
        raise ValueError("Phase 0 requires at least 3 Ready article cases")
    case_ids = tuple(case.case_id for case in materialized)
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Phase 0 case_id values must be unique")
    return materialized
