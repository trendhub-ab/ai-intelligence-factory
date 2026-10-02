"""Narrow zero-API rescue for Product Review market-standard overclaims.

This module is installed only in the explicit Product Review runtime. It never changes
Evidence, score semantics, model routing, request budgets, or the strict Decision
Intelligence validator. If persistence rejects an otherwise structured assessment only
because subscriber-facing prose claims a current de facto/industry-standard status that
verified Evidence does not support, the unsupported market-standard wording is weakened
substractively and the unchanged persistence validator is run once more.
"""
from __future__ import annotations

import re
from typing import Any

_INSTALL_MARKER = "_aiif_product_review_assessment_rescue_installed"
_MARKET_STANDARD_PREFIX = "unsupported market-standard claim:"
_MARKET_STANDARD_RE = re.compile(r"(?:デファクト(?:スタンダード)?|業界標準)")
_RESCUE_FIELDS = (
    "main_risk_text",
    "best_for_text",
    "avoid_for_text",
    "short_rationale_text",
    "main_risk",
    "best_for",
    "avoid_for",
    "short_rationale",
)


def _only_market_standard_failures(failures: list[str] | tuple[str, ...] | None) -> bool:
    rows = [str(row or "").strip() for row in (failures or []) if str(row or "").strip()]
    return bool(rows) and all(row.startswith(_MARKET_STANDARD_PREFIX) for row in rows)


def _weaken_market_standard_claims(parsed: dict) -> tuple[dict, list[str]]:
    rescued = dict(parsed or {})
    changed: list[str] = []
    for field in _RESCUE_FIELDS:
        value = rescued.get(field)
        if not isinstance(value, str) or not value:
            continue
        weakened = _MARKET_STANDARD_RE.sub("選択肢", value)
        if weakened != value:
            rescued[field] = weakened
            changed.append(field)
    return rescued, changed


def install(pipeline_module: Any) -> Any:
    """Wrap DI persistence with one narrow, validator-preserving rescue."""
    if bool(getattr(pipeline_module, _INSTALL_MARKER, False)):
        return pipeline_module

    original = getattr(pipeline_module, "persist_decision_intelligence_assessment", None)
    if not callable(original):
        raise RuntimeError("Product Review assessment rescue requires DI persistence")

    def persist_with_market_standard_rescue(
        repo: dict,
        parsed: dict,
        source_info: dict,
        evidence_result: dict,
        reviewed_at: str,
        *args,
        **kwargs,
    ):
        first = original(
            repo, parsed, source_info, evidence_result, reviewed_at, *args, **kwargs
        )
        if first.get("saved") or first.get("reason") != "assessment_invalid":
            return first

        failures = list(first.get("failures") or [])
        if not _only_market_standard_failures(failures):
            return first

        rescued, changed_fields = _weaken_market_standard_claims(parsed)
        if not changed_fields:
            return first

        logger = getattr(pipeline_module, "logger", None)
        if logger is not None:
            logger.info(
                "[PRODUCT REVIEW ZERO-API ASSESSMENT RESCUE] %s fields=%s failures=%s",
                repo.get("nameWithOwner"),
                ",".join(changed_fields),
                " / ".join(failures)[:500],
            )

        # The same strict validator/persistence path runs again. If any unsupported
        # claim remains, this second call stays fail-closed and no write is accepted.
        second = original(
            repo, rescued, source_info, evidence_result, reviewed_at, *args, **kwargs
        )
        if second.get("saved") and logger is not None:
            logger.info(
                "[PRODUCT REVIEW ZERO-API ASSESSMENT RESCUE RECOVERED] %s",
                repo.get("nameWithOwner"),
            )
        return second

    pipeline_module.persist_decision_intelligence_assessment = persist_with_market_standard_rescue
    setattr(pipeline_module, _INSTALL_MARKER, True)
    return pipeline_module
