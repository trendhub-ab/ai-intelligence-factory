"""Fail-closed per-run limits for the fixed-Evidence experiment.

This local policy is not a substitute for a shared project reservation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Callable


class ProbeStopped(RuntimeError):
    pass


@dataclass
class ProbePolicy:
    max_attempts: int = 4
    project_spacing: float = 25
    model_window: float = 60
    model_limit: int = 3
    attempts: list[tuple[str, float]] = field(default_factory=list)
    failed_models: set[str] = field(default_factory=set)
    consecutive_503: int = 0
    stopped: bool = False
    pending: str | None = None

    def reserve(self, model: str, now: float) -> None:
        if self.stopped or self.pending is not None:
            raise ProbeStopped("Experiment stopped or previous request has no outcome")
        if model in self.failed_models:
            raise ProbeStopped(f"Model stopped after 503: {model}")
        if len(self.attempts) >= self.max_attempts:
            raise ProbeStopped("Four provider attempts exhausted")
        if self.attempts and now - self.attempts[-1][1] < self.project_spacing:
            raise ProbeStopped("Project-wide send spacing not elapsed")
        recent = sum(name == model and now - timestamp < self.model_window
                     for name, timestamp in self.attempts)
        if recent >= self.model_limit:
            raise ProbeStopped(f"Model rolling-window limit: {model}")
        self.attempts.append((model, now))
        self.pending = model

    def record(self, outcome: str) -> None:
        if self.pending is None:
            raise ProbeStopped("Cannot record outcome without a reserved attempt")
        model = self.pending
        self.pending = None
        if outcome == "503":
            self.failed_models.add(model)
            self.consecutive_503 += 1
            self.stopped = self.consecutive_503 >= 2
        elif outcome == "429":
            self.stopped = True
            self.consecutive_503 = 0
        elif outcome == "success":
            self.consecutive_503 = 0
        else:
            self.stopped = True


def run_bounded_cases(
    cases: list[dict], *, send: Callable[[dict], str],
    assess: Callable[[dict, str], dict],
    before_send: Callable[[dict], None] | None = None,
    on_result: Callable[[dict], None] | None = None,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    policy: ProbePolicy | None = None,
) -> list[dict]:
    """Consume at most four provider attempts with one owner for all sends.

    ``send`` must perform exactly one provider-visible attempt, without fallback
    or SDK retry. A feedback case returned by ``assess`` reenters this same queue.
    """
    limiter = policy or ProbePolicy()
    queue = list(cases)
    results: list[dict] = []
    while queue and not limiter.stopped and len(limiter.attempts) < limiter.max_attempts:
        case = queue.pop(0)
        model = case["model"]
        if model in limiter.failed_models:
            continue
        if limiter.attempts:
            remaining = limiter.project_spacing - (clock() - limiter.attempts[-1][1])
            if remaining > 0:
                sleep(remaining)
        try:
            limiter.reserve(model, clock())
        except ProbeStopped:
            break
        try:
            if before_send is not None:
                before_send(case)
        except Exception as exc:
            limiter.record("error")
            row = {"case": case, "outcome": "error", "provider_attempted": False,
                   "error": {"type": type(exc).__name__, "message": str(exc)[:1000]}}
            results.append(row)
            if on_result is not None:
                on_result(row)
            break
        try:
            raw = send(case)
        except Exception as exc:
            code = getattr(exc, "code", None)
            if code is None and getattr(exc, "response", None) is not None:
                code = getattr(exc.response, "status_code", None)
            outcome = str(code) if code in (429, 503) else "error"
            limiter.record(outcome)
            row = {"case": case, "outcome": outcome, "provider_attempted": True,
                   "error": {"type": type(exc).__name__, "message": str(exc)[:1000]}}
        else:
            limiter.record("success")
            try:
                assessment = assess(case, raw)
            except Exception:
                # The provider request already consumed quota. Never retry it
                # because a local parser/Gate/postprocessor failed.
                limiter.stopped = True
                raise
            row = {"case": case, "outcome": "success", "provider_attempted": True,
                   "assessment": assessment}
            feedback = assessment.get("feedback")
            if feedback and len(limiter.attempts) < limiter.max_attempts:
                queue.insert(0, feedback)
        results.append(row)
        if on_result is not None:
            on_result(row)
    return results
