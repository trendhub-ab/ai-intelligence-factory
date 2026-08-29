"""Run164 high-precision AI relevance vocabulary calibration.

This is a zero-provider policy overlay. It extends Run155 only with phrases that
were observed as deterministic false negatives in the expanded paid catalog.
Bare agent/model/GPU/ML tokens are intentionally excluded to preserve precision.
"""
from __future__ import annotations

from typing import Any

POLICY_VERSION = "run164-paid-db-launch-relevance-precision-v4"

HIGH_PRECISION_AI_PATTERNS = (
    r"coding[- ]agents?",
    r"research[- ]agents?",
    r"self[- ]improving[- ]agents?",
    r"vector (?:db|database)",
    r"distributed training",
    r"model serving",
    r"code generation",
    r"chain[- ]of[- ]thought",
    r"(?<![A-Za-z0-9_])CoT(?![A-Za-z0-9_])",
    r"(?<![A-Za-z0-9_])chatbots?(?![A-Za-z0-9_])",
    r"コーディングエージェント",
    r"(?:調査|リサーチ)Agent",
    r"(?:調査|リサーチ)エージェント",
    r"自己改善(?:型)?エージェント",
    r"コード生成",
    r"ベクトル(?:DB|データベース)",
    r"分散学習",
    r"推論ランタイム",
    r"データサイエンス",
)


def install_on(launch_module: Any) -> None:
    """Extend Run155's deterministic vocabulary idempotently."""
    current = tuple(getattr(launch_module, "AI_RELEVANCE_PATTERNS", ()))
    launch_module.AI_RELEVANCE_PATTERNS = current + tuple(
        pattern for pattern in HIGH_PRECISION_AI_PATTERNS if pattern not in current
    )
    launch_module.POLICY_VERSION = POLICY_VERSION
