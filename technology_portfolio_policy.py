"""Technology portfolio policy for AI Intelligence Factory.

Run130 goal
===========
Keep the product differentiated as *technology decision intelligence* without
letting any discovery source (especially GitHub) become the product taxonomy.

This module is deliberately planning-only:
- it never changes Adoption Score/Status;
- it never bypasses Evidence or Product Review;
- it only changes which already-eligible legacy technologies are reviewed first.

The portfolio has three reader-facing layers:
1. APPLIED_AI      — directly usable products/services when the technical change matters;
2. PRACTICAL_TECH  — agents, security, data, infra, models, multimodal and tooling;
3. DEEP_TECH       — research / emerging mechanisms that may matter next.

There are no forced quotas. Quality can always stop the run. Diversification is
implemented as a marginal concentration penalty so a clearly stronger candidate
can still win.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse


STRATEGIC_TECH_TERMS = (
    "agent", "agentic", "mcp", "model context protocol", "rag", "retrieval",
    "inference", "serving", "reasoning", "multimodal", "vision", "speech",
    "security", "privacy", "governance", "guardrail", "sandbox",
    "vector", "embedding", "observability", "tracing", "eval", "evaluation",
    "gateway", "orchestration", "tool use", "memory", "fine-tun", "distill",
    "quantization", "latency", "gpu", "distributed", "on-device", "edge ai",
)

GENERIC_REPO_TERMS = (
    "awesome list", "tutorial", "beginners", "beginner", "boilerplate",
    "template", "examples", "cheatsheet", "roadmap", "learning resources",
)

PRODUCT_TERMS = (
    "product", "service", "platform", "app", "assistant", "workspace",
)

NEWS_EVENT_PATTERNS = (
    r"\bincident\b", r"\boutage\b", r"\bcompromise(?:d)?\b", r"\bhack(?:ed|ing)?\b",
    r"\bcharges?\b", r"\bprices?\b", r"\bjoining\b", r"\bacquired\b",
    r"\bask hn\b", r"\brant\b", r"\bfeels like\b",
)


def _text(record: Any) -> str:
    return f"{getattr(record, 'name', '')} {getattr(record, 'source_summary', '')}".lower()


def _sources(record: Any) -> set[str]:
    return {str(x) for x in (getattr(record, "source", ()) or ())}


def _age_days(record: Any, now: datetime) -> int | None:
    # Avoid depending on inventory_bootstrap private helpers. ISO dates are enough
    # for planning freshness and a parse failure simply means no freshness bonus.
    value = getattr(record, "published_at", None) or getattr(record, "analyzed_at", None)
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (now - dt.astimezone(timezone.utc)).days)
    except (TypeError, ValueError):
        return None


def technology_layer(record: Any, planning_category: str, lane: str) -> tuple[str, tuple[str, ...]]:
    """Classify the *portfolio layer*, never the Adoption outcome."""
    sources = _sources(record)
    text = _text(record)

    if lane == "RESEARCH" or ("ArXiv" in sources and lane != "PRACTICAL"):
        return "DEEP_TECH", ("technology_layer:DEEP_TECH",)

    # ProductHunt is only a discovery signal. It does not make something valuable,
    # but a concrete product/service belongs in the applied layer for diversification.
    if planning_category == "PRODUCT" or "ProductHunt" in sources:
        return "APPLIED_AI", ("technology_layer:APPLIED_AI",)
    if any(term in text for term in PRODUCT_TERMS) and any(term in text for term in STRATEGIC_TECH_TERMS):
        return "APPLIED_AI", ("technology_layer:APPLIED_AI_TECHNICAL_PRODUCT",)

    return "PRACTICAL_TECH", ("technology_layer:PRACTICAL_TECH",)


def portfolio_base_priority(record: Any, now: datetime | None = None) -> tuple[float, tuple[str, ...]]:
    """Source-neutral replacement for the old durable-source-heavy bootstrap score."""
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    screening = max(0.0, min(100.0, float(getattr(record, "screening_score", 0.0) or 0.0)))

    # Screening/reader relevance is the main signal. Discovery source is deliberately tiny.
    score = screening * 0.60
    reasons.append(f"screening_component={screening * 0.60:.1f}")

    sources = _sources(record)
    if "GitHub" in sources:
        score += 3; reasons.append("source_signal:GitHub:+3")
    if "ArXiv" in sources:
        score += 3; reasons.append("source_signal:ArXiv:+3")
    if "ProductHunt" in sources:
        score += 2; reasons.append("source_signal:ProductHunt:+2")
    if "HackerNews" in sources:
        score += 1; reasons.append("source_signal:HackerNews:+1")

    host = (urlparse(getattr(record, "primary_url", "") or "").hostname or "").lower()
    if host and any(h in host for h in ("github.com", "arxiv.org", "huggingface.co", "docs.", "developer.")):
        score += 4; reasons.append("inspectable_primary_source:+4")
    if host == "news.ycombinator.com":
        score -= 8; reasons.append("discussion_only_url:-8")

    summary_len = len((getattr(record, "source_summary", "") or "").strip())
    if summary_len >= 180:
        score += 8; reasons.append("rich_source_summary:+8")
    elif summary_len >= 70:
        score += 4; reasons.append("usable_source_summary:+4")
    elif summary_len < 20:
        score -= 6; reasons.append("thin_source_summary:-6")

    age = _age_days(record, now)
    if age is not None:
        if age <= 30:
            score += 10; reasons.append("fresh<=30d:+10")
        elif age <= 90:
            score += 7; reasons.append("fresh<=90d:+7")
        elif age <= 365:
            score += 3; reasons.append("fresh<=365d:+3")
        elif age > 730:
            score -= 5; reasons.append("stale>730d:-5")

    pattern_hits = sum(bool(re.search(p, _text(record), re.I)) for p in NEWS_EVENT_PATTERNS)
    if pattern_hits:
        penalty = min(18, 8 + (pattern_hits - 1) * 5)
        score -= penalty
        reasons.append(f"event_or_opinion_pattern:-{penalty}")

    return round(max(0.0, min(100.0, score)), 2), tuple(reasons)


def portfolio_utility_score(record: Any, planning_category: str, lane: str) -> tuple[float, tuple[str, ...]]:
    """Paid-product usefulness without rewarding a repository merely for being a repository."""
    text = _text(record)
    sources = _sources(record)
    layer, layer_reasons = technology_layer(record, planning_category, lane)
    reasons = list(layer_reasons)
    score = 0.0

    if layer == "PRACTICAL_TECH":
        score += 7; reasons.append("practical_technology:+7")
    elif layer == "APPLIED_AI":
        score += 5; reasons.append("applied_technical_product:+5")
    else:
        # Deep Tech is part of the differentiation and is no longer automatically deferred.
        score += 3; reasons.append("deep_tech_option_value:+3")

    strategic_hits = sum(1 for term in STRATEGIC_TECH_TERMS if term in text)
    if strategic_hits >= 3:
        score += 9; reasons.append("strategic_technology_signals:+9")
    elif strategic_hits >= 1:
        score += 5; reasons.append("strategic_technology_signals:+5")

    if planning_category == "OTHER":
        score -= 4; reasons.append("planning_category_other:-4")
    else:
        score += 3; reasons.append(f"planning_category_resolved:{planning_category}:+3")

    # This is the key anti-skew rule: GitHub is not a product category.
    # Generic DEVTOOLS/OTHER repos need an actual strategic-technology signal to compete.
    if "GitHub" in sources and planning_category in {"DEVTOOLS", "OTHER"} and strategic_hits == 0:
        score -= 10; reasons.append("generic_github_repo_without_decision_signal:-10")

    if any(term in text for term in GENERIC_REPO_TERMS) and strategic_hits == 0:
        score -= 8; reasons.append("generic_learning_or_template_repo:-8")

    return round(max(-25.0, min(25.0, score)), 2), tuple(reasons)


def balanced_plan_candidates(
    bootstrap_module: Any,
    records: Iterable[Any],
    limit: int = 30,
    max_source_share: float = 0.45,
    now: datetime | None = None,
) -> list[Any]:
    """Portfolio-aware replacement for inventory_bootstrap.plan_candidates.

    It preserves the original PlannedCandidate output contract and all eligibility gates.
    """
    now = now or datetime.now(timezone.utc)
    pool: list[dict[str, Any]] = []
    for record in records:
        if not bootstrap_module.is_bootstrap_eligible(record, now=now):
            continue
        base, base_reasons = portfolio_base_priority(record, now=now)
        pcat, cat_reasons = bootstrap_module.infer_planning_category(record)
        lane, lane_reasons = bootstrap_module.candidate_lane(record, pcat)
        utility, utility_reasons = portfolio_utility_score(record, pcat, lane)
        layer, layer_reasons = technology_layer(record, pcat, lane)
        pool.append({
            "record": record,
            "base": base,
            "utility": utility,
            "planning_category": pcat,
            "lane": lane,
            "layer": layer,
            "reasons": base_reasons + cat_reasons + lane_reasons + utility_reasons + layer_reasons,
        })

    if limit <= 0 or not pool:
        return []

    max_share = max(0.10, min(1.0, max_source_share))
    selected: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    lane_counts: Counter[str] = Counter()
    layer_counts: Counter[str] = Counter()
    remaining = list(pool)

    def source_bucket(record: Any) -> str:
        return record.source[0] if getattr(record, "source", ()) else "Unknown"

    while remaining and len(selected) < limit:
        position = len(selected) + 1
        prefix_cap = max(1, math.ceil(position * max_share))
        feasible = [x for x in remaining if source_counts[source_bucket(x["record"])] < prefix_cap]
        choice_pool = feasible or remaining

        def marginal(item: dict[str, Any]) -> tuple[float, float, float, str]:
            record = item["record"]
            source = source_bucket(record)
            pcat = item["planning_category"]
            lane = item["lane"]
            layer = item["layer"]

            # Source is penalized most strongly because source != product taxonomy.
            concentration_penalty = (
                source_counts[source] * 7.0
                + category_counts[pcat] * 3.0
                + lane_counts[lane] * 2.0
                + layer_counts[layer] * 4.0
            )
            if pcat == "OTHER":
                concentration_penalty += 3.0 + category_counts[pcat] * 2.0
            if source == "GitHub" and pcat in {"DEVTOOLS", "OTHER"}:
                concentration_penalty += source_counts[source] * 2.0

            score = item["base"] + item["utility"] - concentration_penalty
            return (score, item["base"] + item["utility"], getattr(record, "screening_score", 0.0) or 0.0, record.name.lower())

        chosen = max(choice_pool, key=marginal)
        chosen = dict(chosen)
        chosen["portfolio_priority"] = round(marginal(chosen)[0], 2)
        selected.append(chosen)
        record = chosen["record"]
        source_counts[source_bucket(record)] += 1
        category_counts[chosen["planning_category"]] += 1
        lane_counts[chosen["lane"]] += 1
        layer_counts[chosen["layer"]] += 1
        remaining.remove(next(x for x in remaining if x["record"] is record))

    return [
        bootstrap_module.PlannedCandidate(
            canonical_entity_id=x["record"].canonical_entity_id,
            name=x["record"].name,
            primary_url=x["record"].primary_url,
            source=x["record"].source,
            category=x["record"].category,
            planning_category=x["planning_category"],
            candidate_lane=x["lane"],
            screening_score=x["record"].screening_score,
            bootstrap_priority=x["base"],
            product_utility_score=x["utility"],
            portfolio_priority=x["portfolio_priority"],
            reasons=x["reasons"],
        )
        for x in selected[:limit]
    ]


def install_on(bootstrap_module: Any) -> None:
    """Install the policy as a reversible planning overlay."""
    original = bootstrap_module.plan_candidates

    def _plan(records: Iterable[Any], limit: int = 30, max_source_share: float = 0.45, now: datetime | None = None) -> list[Any]:
        return balanced_plan_candidates(bootstrap_module, records, limit, max_source_share, now)

    _plan.__name__ = "run130_balanced_plan_candidates"
    _plan.__doc__ = "Run130 technology-portfolio-aware planning policy."
    _plan._run130_original = original  # type: ignore[attr-defined]
    bootstrap_module.plan_candidates = _plan
