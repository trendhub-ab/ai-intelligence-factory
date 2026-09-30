"""Hard per-Fresh provider-send-slot cap that preserves model fallback.

Every pipeline._generate_via_chat invocation routes through this guard only in
local_skills_canary_validation. It is deliberately installed after Production's
normal runtime layers, so their model health routing, 503/429 handling and
per-model persistent quota controls remain authoritative.

A reserved slot is a conservative upper bound on a provider transport attempt:
a downstream pre-send rejection can consume a slot without HTTP. This guard
does not claim to measure current Gemini RPM/RPD or SDK-internal retries.
The pinned SDK runtime is separately configured for a single SDK attempt.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

# At most two Screening batches and one Calibration batch are logical work.
# Reserve capacity for transient provider fallback before the one article.
MAX_PRE_ARTICLE_SEND_SLOTS = 6
# Four ranked article models can be attempted, subject to earlier per-model
# health checks. This is not a promise that all four will be tried.
MAX_ARTICLE_SEND_SLOTS = 4
MAX_TOTAL_SEND_SLOTS = MAX_PRE_ARTICLE_SEND_SLOTS + MAX_ARTICLE_SEND_SLOTS


class FreshProviderBudgetExhausted(RuntimeError):
    """Stop before any excess model call; an unmeasured operational outcome."""


class FreshModelSendBudget:
    def __init__(self) -> None:
        self.pre_article_slots = 0
        self.article_slots = 0
        self.model_attempts: list[dict[str, str]] = []

    @property
    def total_slots(self) -> int:
        return self.pre_article_slots + self.article_slots

    def wrapped(self, original: Callable[..., Any]) -> Callable[..., Any]:
        if not callable(original):
            raise RuntimeError("Fresh provider budget requires a callable Production send path")

        def limited_send(
            model_name: str,
            prompt: str,
            config: dict | None = None,
            request_kind: str = "other",
            reserve: int = 0,
            request_context: str = "",
            count_as_deep_dive: bool = False,
            request_origin: str = "new",
        ) -> Any:
            if type(count_as_deep_dive) is not bool:
                raise RuntimeError("Fresh provider send classification is invalid")
            if self.total_slots >= MAX_TOTAL_SEND_SLOTS:
                raise FreshProviderBudgetExhausted(
                    f"Fresh provider-send hard cap reached: {MAX_TOTAL_SEND_SLOTS}"
                )
            if count_as_deep_dive:
                if self.article_slots >= MAX_ARTICLE_SEND_SLOTS:
                    raise FreshProviderBudgetExhausted(
                        f"Fresh article fallback cap reached: {MAX_ARTICLE_SEND_SLOTS}"
                    )
                self.article_slots += 1
            else:
                # Screening/Calibration or any other unexpected non-article
                # model calls must still remain under the shared pre-article cap.
                if self.pre_article_slots >= MAX_PRE_ARTICLE_SEND_SLOTS:
                    raise FreshProviderBudgetExhausted(
                        f"Fresh pre-article model cap reached: {MAX_PRE_ARTICLE_SEND_SLOTS}"
                    )
                self.pre_article_slots += 1
            self.model_attempts.append({
                "model": str(model_name),
                "phase": "article" if count_as_deep_dive else "pre_article",
                "kind": str(request_kind),
            })
            return original(
                model_name,
                prompt,
                config=config,
                request_kind=request_kind,
                reserve=reserve,
                request_context=request_context,
                count_as_deep_dive=count_as_deep_dive,
                request_origin=request_origin,
            )

        return limited_send

    def snapshot(self) -> dict[str, Any]:
        return {
            "scope": "one_source_stratified_fresh_run",
            "max_total_send_slots": MAX_TOTAL_SEND_SLOTS,
            "max_pre_article_send_slots": MAX_PRE_ARTICLE_SEND_SLOTS,
            "max_article_send_slots": MAX_ARTICLE_SEND_SLOTS,
            "total_slots_reserved": self.total_slots,
            "pre_article_slots_reserved": self.pre_article_slots,
            "article_slots_reserved": self.article_slots,
            "model_attempts": list(self.model_attempts),
            "actual_provider_rpm_rpd_remaining": "NOT_MEASURED",
            "slot_count_note": "Conservative send-slot reservations, not verified HTTP transport count",
        }
