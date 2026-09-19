"""Run226 compatibility layer for the canonical AIIF article contract.

Run226 remains the historical installation point for Editorial Blueprint behavior, but the
article-quality policy itself now lives in canonical_article_contract.py.  This module adds
no provider call, changes no output schema, and relaxes no gate.
"""
from __future__ import annotations

from typing import Any

from canonical_article_contract import (
    CANONICAL_ARTICLE_CONTRACT_MARKER,
    canonical_writer_contract,
    deconflict_legacy_writer_rules,
    ensure_writer_contract,
)
from editorial_quality_memory import QUALITY_MEMORY_MARKER, quality_memory_contract


RUN226_MARKER = "RUN226_READER_DELIGHT_PLANNING"
EDITORIAL_BLUEPRINT_MARKER = CANONICAL_ARTICLE_CONTRACT_MARKER
_INSTALL_FLAG = "_run226_reader_delight_planning_installed"


def deconflict_writer_prompt(prompt: str) -> str:
    """Compatibility wrapper around the canonical legacy-quota deconflicter."""
    return deconflict_legacy_writer_rules(prompt)


def editorial_planning_contract() -> str:
    """Return the canonical article contract through the historical Run226 API."""
    return canonical_writer_contract()


def augment_prompt(prompt: str) -> str:
    """Install the canonical Writer contract plus compact historical compatibility markers."""
    base = ensure_writer_contract(prompt).rstrip()
    if RUN226_MARKER not in base:
        base += f"\n\n[{RUN226_MARKER} — compatibility layer]"
    if QUALITY_MEMORY_MARKER not in base:
        base += "\n\n" + quality_memory_contract()
    return base.rstrip() + "\n"


def install(pipeline_module: Any) -> None:
    """Install Run226 on a pipeline-like module, idempotently."""
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return

    original = pipeline_module.build_decision_prompt

    def wrapped_build_decision_prompt(*args: Any, **kwargs: Any) -> str:
        return augment_prompt(original(*args, **kwargs))

    pipeline_module.build_decision_prompt = wrapped_build_decision_prompt
    setattr(pipeline_module, _INSTALL_FLAG, True)
    setattr(pipeline_module, RUN226_MARKER, True)
    setattr(pipeline_module, EDITORIAL_BLUEPRINT_MARKER, True)
