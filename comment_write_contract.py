"""Fail-closed ownership contract for generated Notion comment-like properties.

This module is intentionally provider- and network-independent. It decides whether a
candidate value may enter a production mutation; it never calls Notion or an AI API.

Safety invariants:
- Existing non-empty values are immutable through this contract.
- Shadow output is never eligible for a production mutation.
- Blank-fill requires explicit property ownership.
- Product Review provider changes are blocked unless the configured provider matches
  the locked provider.
- Provider promotion requires both a passed quality gate and explicit approval.
- Promotion never grants permission to rewrite historical non-empty values.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class WriteDecision(str, Enum):
    PRESERVE = "preserve"
    BLANK_FILL = "blank_fill"
    SHADOW = "shadow"
    BLOCKED = "blocked"


class WriteMode(str, Enum):
    PRODUCTION = "production"
    SHADOW = "shadow"


@dataclass(frozen=True)
class CommentWriteRequest:
    property_name: str
    existing_value: Any
    candidate_value: Any
    owner_allowed: bool
    mode: WriteMode = WriteMode.PRODUCTION
    provider: str = ""
    locked_provider: str = ""
    provider_promotion_requested: bool = False
    quality_gate_passed: bool = False
    promotion_approved: bool = False


@dataclass(frozen=True)
class CommentWriteResult:
    decision: WriteDecision
    property_name: str
    value: Any
    reason: str
    provider: str

    @property
    def production_write_allowed(self) -> bool:
        return self.decision is WriteDecision.BLANK_FILL


def _is_blank(value: Any) -> bool:
    """Treat only None/empty-or-whitespace strings as blank.

    Non-string structured values are conservatively considered existing data so this
    guard never destroys content because of an overly broad emptiness test.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def decide_comment_write(request: CommentWriteRequest) -> CommentWriteResult:
    """Return the auditable decision for one generated property candidate."""
    if not _is_blank(request.existing_value):
        return CommentWriteResult(
            WriteDecision.PRESERVE,
            request.property_name,
            request.existing_value,
            "existing_non_empty_value_is_immutable",
            request.provider,
        )

    if request.mode is WriteMode.SHADOW:
        return CommentWriteResult(
            WriteDecision.SHADOW,
            request.property_name,
            request.candidate_value,
            "shadow_output_never_enters_production_mutation",
            request.provider,
        )

    if request.locked_provider and request.provider != request.locked_provider:
        return CommentWriteResult(
            WriteDecision.BLOCKED,
            request.property_name,
            request.existing_value,
            "provider_lock_mismatch",
            request.provider,
        )

    if request.provider_promotion_requested and not (
        request.quality_gate_passed and request.promotion_approved
    ):
        return CommentWriteResult(
            WriteDecision.BLOCKED,
            request.property_name,
            request.existing_value,
            "provider_promotion_requires_quality_pass_and_explicit_approval",
            request.provider,
        )

    if not request.owner_allowed:
        return CommentWriteResult(
            WriteDecision.BLOCKED,
            request.property_name,
            request.existing_value,
            "property_not_owned_for_blank_fill",
            request.provider,
        )

    if _is_blank(request.candidate_value):
        return CommentWriteResult(
            WriteDecision.BLOCKED,
            request.property_name,
            request.existing_value,
            "blank_candidate_is_not_a_write",
            request.provider,
        )

    return CommentWriteResult(
        WriteDecision.BLANK_FILL,
        request.property_name,
        request.candidate_value,
        "explicitly_owned_blank_property_may_be_filled",
        request.provider,
    )


def build_production_property_mutation(
    results: Mapping[str, CommentWriteResult],
) -> dict[str, Any]:
    """Build a mutation containing only explicitly authorized blank fills.

    PRESERVE, SHADOW and BLOCKED decisions are omitted by construction.
    """
    return {
        name: result.value
        for name, result in results.items()
        if result.production_write_allowed
    }


def apply_authorized_blank_fills(
    existing: Mapping[str, Any], results: Mapping[str, CommentWriteResult]
) -> dict[str, Any]:
    """Pure helper used to prove migration idempotency without network access."""
    merged = dict(existing)
    merged.update(build_production_property_mutation(results))
    return merged
