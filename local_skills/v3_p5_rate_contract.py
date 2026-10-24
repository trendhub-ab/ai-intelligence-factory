"""P5-only physical-send budget guard; no network and no production rollout.

For a validation run use Gemini 3.8 Flash before 3.6 Flash. The 3.6
logical SDK send_message call is capped to 3 across ALL P5 calls in the
process, including the first management pass and internal pool retries.
Explicit non-retrying SDK client is required in the private new-proof path.
No impact to classic/other models.
"""
from __future__ import annotations

from dataclasses import dataclass, field

P5_MODELS = ("gemini-3.8-flash", "gemini-3.6-flash")
P5_36_SEND_LIMIT = 3


class P5SendLimitError(RuntimeError):
    """Refuse another Gemini 3.6 Flash send before touching the provider."""


@dataclass
class P5SendGuard:
    counts: dict[str, int] = field(default_factory=lambda: dict.fromkeys(P5_MODELS, 0))

    def pre_send(self, model: str, *, p5_active: bool) -> None:
        if not p5_active:
            return
        if model not in P5_MODELS:
            raise P5SendLimitError("P5 forbids Preview, Lite and non-3.8/3.6 models")
        if model == "gemini-3.6-flash" and self.counts[model] >= P5_36_SEND_LIMIT:
            raise P5SendLimitError("Gemini 3.6 Flash P5 three-send cap exhausted")
        self.counts[model] += 1

    def receipt(self) -> dict:
        return {
            "model_priority": list(P5_MODELS),
            "by_model": dict(self.counts),
            "gemini_3_6_limit": P5_36_SEND_LIMIT,
        }


def ordered_p5_pool(configured: object) -> list[str]:
    """Respect provider/session temporary exclusion while prioritizing 3.8."""
    available = set(configured or ())
    return [model for model in P5_MODELS if model in available]
