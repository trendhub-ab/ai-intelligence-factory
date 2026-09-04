"""Run225 active-review overlay for Screening Stock lifecycle.

Install after Run131.  It filters only lifecycle=Archive records before the
existing portfolio planner runs.  Fresh/Aging/Evergreen preserve the exact Run131
ranking policy.  No record is deleted or mutated and no Gemini call is made.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

import run225_stock_lifecycle as lifecycle


def install_on(bootstrap_module: Any) -> None:
    original = bootstrap_module.plan_candidates

    def _plan(
        records: Iterable[Any],
        limit: int = 30,
        max_source_share: float = 0.60,
        now: datetime | None = None,
    ) -> list[Any]:
        now_utc = now or datetime.now(timezone.utc)
        materialized = list(records)
        active = [record for record in materialized if lifecycle.active_for_review(record, now=now_utc)]
        result = original(
            active,
            limit=limit,
            max_source_share=max_source_share,
            now=now_utc,
        )
        return result

    _plan.__name__ = "run225_lifecycle_aware_plan_candidates"
    _plan.__doc__ = "Run225: exclude archived stock from active portfolio review planning."
    _plan._run225_original = original  # type: ignore[attr-defined]
    bootstrap_module.plan_candidates = _plan
