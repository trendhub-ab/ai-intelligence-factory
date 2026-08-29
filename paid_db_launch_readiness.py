"""Run155 — Paid DB Launch Relevance Precision.

This module keeps Run152's commercial launch-quality policy, but fixes AI
relevance false negatives exposed by the 100-record catalog.  Product Review
category remains evidence-grounded; AI-native categories can therefore act as a
strong taxonomy signal.  Mixed categories still require substantive AI evidence
from the record text so generic software cannot enter the AI core shelf merely
because boilerplate decision copy mentions AI.

The policy is deterministic and consumes zero Gemini requests.
"""
from __future__ import annotations

from collections import Counter
import os
import re
from typing import Any, Iterable

POLICY_VERSION = "run155-paid-db-launch-relevance-precision-v3"

DEFAULT_STRETCH_TARGET = int(os.environ.get("PAID_DB_STRETCH_TARGET", "60"))
DEFAULT_LAUNCH_MIN_SELLABLE = int(os.environ.get("PAID_DB_LAUNCH_MIN_SELLABLE", "50"))
DEFAULT_MIN_FRONT_SHELF = int(os.environ.get("PAID_DB_MIN_FRONT_SHELF", "15"))
DEFAULT_MAX_CATEGORY_SHARE = float(os.environ.get("PAID_DB_MAX_CATEGORY_SHARE", "0.35"))
DEFAULT_MAX_OTHER_SHARE = float(os.environ.get("PAID_DB_MAX_OTHER_SHARE", "0.20"))
DEFAULT_MAX_REFERENCE_SHARE = float(os.environ.get("PAID_DB_MAX_REFERENCE_SHARE", "0.20"))
DEFAULT_MIN_AI_RELEVANT_RATIO = float(os.environ.get("PAID_DB_MIN_AI_RELEVANT_RATIO", "0.85"))
DEFAULT_MIN_REQUIRED_CATEGORY_COUNT = int(os.environ.get("PAID_DB_MIN_REQUIRED_CATEGORY_COUNT", "2"))

REQUIRED_LAUNCH_CATEGORIES = (
    "MODEL",
    "AGENT",
    "DEVTOOLS",
    "SECURITY",
    "DATA",
    "INFRA",
    "MULTIMODAL",
    "PRODUCT",
)

# Product Review's closed taxonomy makes these categories intrinsically AI-native.
# Mixed categories (INFRA/DATA/DEVTOOLS/SECURITY/PRODUCT/OTHER) deliberately do
# not get this shortcut because they can contain useful but non-AI software.
AI_NATIVE_CATEGORIES = frozenset({"MODEL", "AGENT", "MULTIMODAL"})

# Reference material can remain searchable for members, but it must not make a
# thin catalog look like a broad decision product.
REFERENCE_ONLY_PATTERNS = (
    r"(?:^|[/_-])awesome(?:[/_-]|$)",
    r"interview",
    r"kaggle[-_ ]?solutions?",
    r"cookiecutter[-_ ]?data[-_ ]?science",
    r"curated (?:list|resources?)",
    r"resource list",
    r"link list",
    r"learning guide",
    r"reference material",
    r"参考資料",
    r"資料集",
    r"教材",
    r"面接対策",
    r"リンク集",
    r"学習ガイド",
    r"ソフトウェアそのものではない",
    r"システム製品ではない",
    r"導入するAI製品ではない",
    r"本番(?:システム|運用).{0,12}対象外",
)

AI_NEGATIVE_PATTERNS = (
    r"AI固有の技術ではない",
    r"AI技術そのものではない",
    r"not (?:an? )?AI[- ]specific",
    r"not (?:an? )?AI (?:tool|technology|product)",
)

# Do not use Unicode \b around ASCII acronyms.  In Python, Japanese characters
# are word characters, so patterns such as \bLLM\b miss ordinary Japanese text
# like "LLM推論" and "VLMの評価".  ASCII-only lookarounds retain token safety
# while allowing Japanese adjacency.
AI_RELEVANCE_PATTERNS = (
    r"(?<![A-Za-z0-9_])artificial intelligence(?![A-Za-z0-9_])",
    r"(?<![A-Za-z0-9_])machine learning(?![A-Za-z0-9_])",
    r"(?<![A-Za-z0-9_])deep learning(?![A-Za-z0-9_])",
    r"(?<![A-Za-z0-9_])MLOps(?![A-Za-z0-9_])",
    r"(?<![A-Za-z0-9_])LLMs?(?![A-Za-z0-9_])",
    r"large language model",
    r"(?<![A-Za-z0-9_])agentic(?![A-Za-z0-9_])",
    r"multi[- ]agent",
    r"(?<![A-Za-z0-9_])AI[ -]?agents?(?![A-Za-z0-9_])",
    r"(?<![A-Za-z0-9_])RAG(?![A-Za-z0-9_])",
    r"retrieval[- ]augmented",
    r"(?<![A-Za-z0-9_])embedding",
    r"vector (?:search|database|store)",
    r"(?<![A-Za-z0-9_])neural",
    r"(?<![A-Za-z0-9_])transformer",
    r"(?<![A-Za-z0-9_])multimodal",
    r"vision[- ]language",
    r"(?<![A-Za-z0-9_])VLMs?(?![A-Za-z0-9_])",
    r"federated (?:learning|ai)",
    r"fine[- ]?tun",
    r"(?<![A-Za-z0-9_])inference(?![A-Za-z0-9_])",
    r"(?<![A-Za-z0-9_])prompt(?:ing| management| optimization)?(?![A-Za-z0-9_])",
    r"recommender|recommendation system",
    r"data science",
    r"(?<![A-Za-z0-9_])AI(?![A-Za-z0-9_])",
    r"人工知能",
    r"機械学習",
    r"深層学習",
    r"言語モデル",
    r"大規模モデル",
    r"AIエージェント",
    r"マルチエージェント",
    r"生成AI",
    r"生成モデル",
    r"動画生成",
    r"画像生成",
    r"音声生成",
    r"音声認識",
    r"音声合成",
    r"顔認識",
    r"ベクトル検索",
    r"埋め込み",
    r"モデル(?:学習|推論|サービング|最適化|評価)",
    r"ニューラル",
)


def _record_text(record: Any) -> str:
    """Broad text used for reference-material classification."""
    values = (
        getattr(record, "name", ""),
        getattr(record, "source_summary", ""),
        getattr(record, "short_rationale", ""),
        getattr(record, "best_for", ""),
        getattr(record, "avoid_for", ""),
        getattr(record, "main_risk", ""),
    )
    return " ".join(str(v or "") for v in values)


def _ai_relevance_text(record: Any) -> str:
    """Use only descriptive evidence, never generic decision-copy boilerplate.

    Run153's Best For intentionally talks about an organisation's "AI導入" for
    many records.  Counting that field would make a generic library look AI-native.
    Name, source summary and short rationale describe what the technology actually
    is and are therefore the safe deterministic relevance surface.
    """
    values = (
        getattr(record, "name", ""),
        getattr(record, "source_summary", ""),
        getattr(record, "short_rationale", ""),
    )
    return " ".join(str(v or "") for v in values)


def _has_ai_signal(text: str) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in AI_RELEVANCE_PATTERNS)


def is_reference_only(record: Any) -> bool:
    text = _record_text(record)
    return any(re.search(pattern, text, re.I) for pattern in REFERENCE_ONLY_PATTERNS)


def is_ai_relevant(record: Any) -> bool:
    text = _ai_relevance_text(record)
    category = str(getattr(record, "category", "") or "OTHER").upper()
    negative = any(re.search(pattern, text, re.I) for pattern in AI_NEGATIVE_PATTERNS)

    if negative:
        # Explicit negative evidence is respected.  Remove only the negative
        # phrase, then require a separate substantive AI signal even for a
        # nominally AI-native category.
        stripped = text
        for pattern in AI_NEGATIVE_PATTERNS:
            stripped = re.sub(pattern, " ", stripped, flags=re.I)
        return _has_ai_signal(stripped)

    if category in AI_NATIVE_CATEGORIES:
        return True
    return _has_ai_signal(text)


def is_front_shelf(record: Any) -> bool:
    return (
        not is_reference_only(record)
        and is_ai_relevant(record)
        and getattr(record, "adoption_status", "") in {"ADOPT", "TEST"}
        and getattr(record, "production_readiness", "") in {"HIGH", "MEDIUM"}
        and getattr(record, "evidence_confidence", "") in {"HIGH", "MEDIUM"}
    )


def evaluate_launch_quality(
    sellable_records: Iterable[Any],
    *,
    launch_min_sellable: int = DEFAULT_LAUNCH_MIN_SELLABLE,
    min_front_shelf: int = DEFAULT_MIN_FRONT_SHELF,
    max_category_share: float = DEFAULT_MAX_CATEGORY_SHARE,
    max_other_share: float = DEFAULT_MAX_OTHER_SHARE,
    max_reference_share: float = DEFAULT_MAX_REFERENCE_SHARE,
    min_ai_relevant_ratio: float = DEFAULT_MIN_AI_RELEVANT_RATIO,
    min_required_category_count: int = DEFAULT_MIN_REQUIRED_CATEGORY_COUNT,
) -> dict[str, Any]:
    records = list(sellable_records)
    total = len(records)
    reference_only = [r for r in records if is_reference_only(r)]
    ai_relevant = [r for r in records if is_ai_relevant(r)]
    core = [r for r in records if is_ai_relevant(r) and not is_reference_only(r)]
    front_shelf = [r for r in core if is_front_shelf(r)]

    category_counts: Counter[str] = Counter((getattr(r, "category", "") or "OTHER") for r in core)
    core_count = len(core)
    reference_share = (len(reference_only) / total) if total else 0.0
    ai_relevant_ratio = (len(ai_relevant) / total) if total else 0.0
    other_share = (category_counts.get("OTHER", 0) / core_count) if core_count else 0.0

    dominant_category = ""
    dominant_category_count = 0
    if category_counts:
        dominant_category, dominant_category_count = max(category_counts.items(), key=lambda item: (item[1], item[0]))
    dominant_category_share = (dominant_category_count / core_count) if core_count else 0.0

    required_counts = {category: category_counts.get(category, 0) for category in REQUIRED_LAUNCH_CATEGORIES}
    missing_categories = [
        category for category, count in required_counts.items()
        if count < min_required_category_count
    ]

    blockers: list[str] = []
    if total < launch_min_sellable:
        blockers.append(f"launch_sellable<{launch_min_sellable} ({total})")
    if len(front_shelf) < min_front_shelf:
        blockers.append(f"front_shelf<{min_front_shelf} ({len(front_shelf)})")
    if ai_relevant_ratio < min_ai_relevant_ratio:
        blockers.append(f"ai_relevant_ratio<{min_ai_relevant_ratio:.2f} ({ai_relevant_ratio:.2f})")
    if reference_share > max_reference_share:
        blockers.append(f"reference_share>{max_reference_share:.2f} ({reference_share:.2f})")
    if dominant_category_share > max_category_share:
        blockers.append(
            f"category_share>{max_category_share:.2f} ({dominant_category}:{dominant_category_share:.2f})"
        )
    if other_share > max_other_share:
        blockers.append(f"other_share>{max_other_share:.2f} ({other_share:.2f})")
    if missing_categories:
        blockers.append(
            f"required_category_count<{min_required_category_count} ({','.join(missing_categories)})"
        )

    return {
        "policy_version": POLICY_VERSION,
        "stretch_target": DEFAULT_STRETCH_TARGET,
        "launch_min_sellable": launch_min_sellable,
        "sellable_count": total,
        "core_product_count": core_count,
        "front_shelf_count": len(front_shelf),
        "min_front_shelf": min_front_shelf,
        "ai_relevant_count": len(ai_relevant),
        "ai_relevant_ratio": round(ai_relevant_ratio, 4),
        "min_ai_relevant_ratio": min_ai_relevant_ratio,
        "reference_only_count": len(reference_only),
        "reference_share": round(reference_share, 4),
        "max_reference_share": max_reference_share,
        "category_counts": dict(sorted(category_counts.items())),
        "required_categories": list(REQUIRED_LAUNCH_CATEGORIES),
        "required_category_counts": required_counts,
        "min_required_category_count": min_required_category_count,
        "dominant_category": dominant_category,
        "dominant_category_share": round(dominant_category_share, 4),
        "max_category_share": max_category_share,
        "other_share": round(other_share, 4),
        "max_other_share": max_other_share,
        "ready": not blockers,
        "blockers": blockers,
    }


def _dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(v for v in values if v))


def install_on(inventory_bootstrap_module: Any) -> None:
    """Install the stricter launch gate on the operational bootstrap entry point.

    Idempotent by design. Existing inventory readiness and paid-product utility
    diagnostics are preserved; only launch readiness becomes stricter.
    """
    if getattr(inventory_bootstrap_module, "_run152_launch_readiness_installed", False):
        return

    original_evaluate = inventory_bootstrap_module.evaluate_readiness

    def evaluate_readiness_v2(records: Iterable[Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
        snapshot = list(records)
        result = original_evaluate(snapshot, *args, **kwargs)
        sellable = [r for r in snapshot if inventory_bootstrap_module.is_sellable(r)]
        quality = evaluate_launch_quality(sellable)

        launch_blockers = list(result.get("launch_blockers") or [])
        launch_blockers.extend(quality["blockers"])

        visible = result.get("subscriber_visible_count")
        if visible is not None and visible < DEFAULT_LAUNCH_MIN_SELLABLE:
            launch_blockers.append(
                f"subscriber_visible_launch_floor<{DEFAULT_LAUNCH_MIN_SELLABLE} ({visible})"
            )

        result["launch_policy_version"] = POLICY_VERSION
        result["launch_quality"] = quality
        result["launch_blockers"] = _dedupe(launch_blockers)
        result["launch_ready"] = not result["launch_blockers"]
        return result

    inventory_bootstrap_module.evaluate_readiness = evaluate_readiness_v2
    inventory_bootstrap_module.DEFAULT_TARGET = max(
        int(getattr(inventory_bootstrap_module, "DEFAULT_TARGET", 0)), DEFAULT_STRETCH_TARGET
    )
    inventory_bootstrap_module.DEFAULT_MIN_SELLABLE = max(
        int(getattr(inventory_bootstrap_module, "DEFAULT_MIN_SELLABLE", 0)), DEFAULT_LAUNCH_MIN_SELLABLE
    )
    inventory_bootstrap_module._run152_launch_readiness_installed = True
