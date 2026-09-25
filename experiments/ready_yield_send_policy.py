"""Fail-closed per-run limits for the fixed-Evidence experiment.

This local policy is not a substitute for a shared project reservation.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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
