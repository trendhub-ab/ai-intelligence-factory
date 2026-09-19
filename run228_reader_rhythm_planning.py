"""Run228 compatibility layer for canonical reader rhythm planning.

The independent long-form Reader Rhythm policy was folded into
canonical_article_contract.py so Fresh Writer prompts have one article-quality source.
This layer keeps its historical installation marker and ensures the canonical last-mile
Reader check without adding a provider call.
"""
from __future__ import annotations

from typing import Any

from canonical_article_contract import (
    CANONICAL_ARTICLE_CONTRACT_MARKER,
    CANONICAL_FINAL_READER_CHECK_MARKER,
    ensure_final_reader_check,
)


RUN228_MARKER = "RUN228_READER_RHYTHM_PLANNING"
RUN368_FINAL_READER_CHECK_MARKER = CANONICAL_FINAL_READER_CHECK_MARKER
_INSTALL_FLAG = "_run228_reader_rhythm_planning_installed"


def reader_rhythm_contract() -> str:
    return f"""
[{RUN228_MARKER} — compatibility layer]
Reader Rhythm is governed by the canonical article contract V1; this layer adds no independent article philosophy.
Historical reader diagnostics remain mapped to that contract: dense_report_cluster, repetitive_insight, non_engineer_access_failure.
The intended flow remains 理解→意味→判断, without leaving a 報告書の塊.
Evidence上重要な数値・条件・反証・制約は削らない。新しいFact、数字、人物、会話、利用実績、因果、競合情報を作ることは禁止する。
正式名称・略語・実装名・フラグ名は判断に必要な場合だけ残し、段落数で機械的に切り替えたりしない。回数ノルマを設けない。
""".strip()

def final_reader_check_contract() -> str:
    """Compatibility API for callers that used the historical Run368 helper."""
    from canonical_article_contract import canonical_final_reader_check
    return canonical_final_reader_check()


def augment_prompt(prompt: str) -> str:
    base = str(prompt or "").rstrip()
    if RUN228_MARKER not in base:
        base += "\n\n" + reader_rhythm_contract()
    return ensure_final_reader_check(base)


def install(pipeline_module: Any) -> None:
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return

    original = pipeline_module.build_decision_prompt

    def wrapped_build_decision_prompt(*args: Any, **kwargs: Any) -> str:
        return augment_prompt(original(*args, **kwargs))

    pipeline_module.build_decision_prompt = wrapped_build_decision_prompt
    setattr(pipeline_module, _INSTALL_FLAG, True)
    setattr(pipeline_module, RUN228_MARKER, True)
    setattr(pipeline_module, RUN368_FINAL_READER_CHECK_MARKER, True)
