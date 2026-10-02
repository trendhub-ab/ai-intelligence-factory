from __future__ import annotations

import os
from typing import Mapping


def enabled() -> bool:
    return str(os.environ.get("AIIF_PRODUCT_REVIEW_RUNTIME") or "").strip().lower() == "true"


def value(value: object) -> str:
    return "<redacted>" if enabled() else str(value or "")


def error(exc: BaseException) -> str:
    return exc.__class__.__name__ if enabled() else str(exc)


def detail(value: object, redacted_reason: str) -> object:
    return redacted_reason if enabled() else value


def public_contexts(by_context: Mapping[str, int], max_contexts: int) -> list[tuple[str, int]]:
    merged: dict[str, int] = {}
    for name, count in by_context.items():
        display = "product_review" if enabled() and str(name).startswith("product_review:") else str(name)
        merged[display] = merged.get(display, 0) + int(count)
    return sorted(merged.items(), key=lambda x: (-x[1], x[0]))[:max_contexts]


def log_evidence_ledger(logger, repo_name: object, ledger_result: Mapping[str, object]) -> None:
    if enabled():
        logger.info("[EVIDENCE LEDGER] saved=%s", int(ledger_result.get("saved", 0) or 0))
    else:
        logger.info("[EVIDENCE LEDGER] %s -> %s", repo_name, ledger_result)


def log_decision_saved(logger, repo_name: object, result: Mapping[str, object]) -> None:
    if enabled():
        logger.info(
            "[DECISION INTELLIGENCE SAVED] created=%s changed=%s history=%s",
            result.get("created"), result.get("changed"), bool(result.get("history_id")),
        )
    else:
        logger.info(
            "[DECISION INTELLIGENCE SAVED] %s -> entity=%s created=%s changed=%s history=%s",
            repo_name, result.get("entity_id"), result.get("created"), result.get("changed"), bool(result.get("history_id")),
        )
