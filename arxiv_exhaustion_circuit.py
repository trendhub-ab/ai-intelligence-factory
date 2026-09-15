"""Run373 close the remaining arXiv bounded-retry exhaustion gap.

Run371 already opens a same-Actions-run circuit immediately on arXiv 429/503.
Production Run #60 proved a narrower gap: two consecutive ReadTimeouts exhausted the
bounded retry, returned ``None``, but did not open the circuit. Later Evidence Health
or Product Review could therefore spend the same two network waits again.

This wrapper never adds a request. It observes the already-bounded Run371 result and,
only after transport/5xx exhaustion, opens the existing same-run circuit so later
callers fail fast. Permanent client responses such as 404 remain uncircuited.
"""
from __future__ import annotations

from functools import wraps
from typing import Any


_TRANSIENT_HTTP_STATUSES = frozenset({500, 502, 504})
_INSTALL_FLAG = "_aiif_arxiv_exhaustion_circuit_installed"


def _same_run_circuit_open(controller: Any) -> bool:
    run_id = str(getattr(controller, "run_id", "") or "")
    state = getattr(controller, "_state", {}) or {}
    if run_id:
        return str(state.get("circuit_run_id") or "") == run_id
    return str(state.get("circuit_run_id") or "") == "process-local"


def install(pipeline_module: Any) -> Any:
    """Open the existing arXiv circuit after the bounded transport retry is exhausted."""
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return pipeline_module

    original = getattr(pipeline_module, "_fetch_arxiv_with_retry", None)
    controller = getattr(pipeline_module, "_ARXIV_STABILITY_CONTROLLER", None)
    open_circuit = getattr(controller, "_open_circuit", None) if controller is not None else None
    if not callable(original) or controller is None or not callable(open_circuit):
        return pipeline_module

    @wraps(original)
    def fetch_with_exhaustion_circuit(url: str, params: dict | None):
        response = original(url, params)
        if response is not None or _same_run_circuit_open(controller):
            return response

        state = getattr(controller, "_state", {}) or {}
        error_type = str(state.get("last_error_type") or "").strip()
        try:
            last_status = int(state.get("last_status") or 0)
        except (TypeError, ValueError):
            last_status = 0

        if error_type:
            # 0 means transport exhaustion rather than a fabricated HTTP status.
            open_circuit(0)
            logger = getattr(pipeline_module, "logger", None)
            if logger is not None:
                logger.warning(
                    "[ARXIV STABILITY EXHAUSTION CIRCUIT] transport=%s run_id=%s",
                    error_type,
                    getattr(controller, "run_id", "") or "process-local",
                )
        elif last_status in _TRANSIENT_HTTP_STATUSES:
            open_circuit(last_status)
            logger = getattr(pipeline_module, "logger", None)
            if logger is not None:
                logger.warning(
                    "[ARXIV STABILITY EXHAUSTION CIRCUIT] status=%s run_id=%s",
                    last_status,
                    getattr(controller, "run_id", "") or "process-local",
                )
        return response

    pipeline_module._fetch_arxiv_with_retry = fetch_with_exhaustion_circuit
    setattr(pipeline_module, _INSTALL_FLAG, True)
    return pipeline_module
