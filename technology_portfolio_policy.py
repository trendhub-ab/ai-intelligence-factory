"""Profit-aligned technology portfolio policy for AI Intelligence Factory.

Run131
======
Run130 correctly removed the large automatic GitHub advantage, but adversarial
review found two business defects: a hard source-share cap could force a much
weaker candidate upward, and the policy only affected the manual bootstrap.

Run131 keeps portfolio diversity as a *tie-breaker among competitive candidates*.
Quality / decision value always wins outside a configurable tolerance. Discovery
source is never treated as product taxonomy, Product Hunt alone never implies an
applied product, and multi-source records are handled without source-order bias.

This module remains planning-only:
- it never changes Adoption Score/Status;
- it never bypasses Evidence or Product Review;
- it never creates a model/API call;
- it only changes review order among already-eligible candidates.
"""
from __future__ import annotations

import os
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse


DEFAULT_PORTFOLIO_TOLERANCE = max(
    0.0, float(os.environ.get("PORTFOLIO_DIVERSITY_TOLERANCE", "8"))
)

STRATEGIC_TECH_TERMS = (
    "agent", "agentic", "mcp", "model context protocol", "rag", "retrieval",
    "inference", "serving", "reasoning", "multimodal", "vision", "speech",
    "security", "privacy", "governance", "guardrail", "sandbox",
    "vector", "embedding", "observability", "tracing", "eval", "evaluation",
    "gateway", "orchestration", "tool use", "memory", "fine-tune", "fine-tuning",
    "finetune", "finetuning", "distill", "distillation", "quantization",
    "latency", "gpu", "distributed", "on-device", "edge ai",
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
    return {str(x) for x in (getattr(record, "source", ()) or ()) if str(x)}


def _term_pattern(term: str) -> re.Pattern[str]:
    """Match technical terms as tokens/phrases, not accidental substrings."""
    escaped = re.escape(term).replace(r"\ ", r"\s+")
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.I)


def _has_term(text: str, term: str) -> bool:
    return bool(_term_pattern(term).search(text))


def _count_terms(text: str, terms: Iterable[str]) -> int:
    return sum(1 for term in terms if _has_term(text, term))


def _age_days(record: Any, now: datetime) -> int | None:
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


def infer_portfolio_category(bootstrap_module: Any, record: Any) -> tuple[str, tuple[str, ...]]:
    """Boundary-safe planning category; authoritative non-OTHER category always wins."""
    authoritative = str(getattr(record, "category", "") or "")
    if authoritative and authoritative != "OTHER":
        return authoritative, ("authoritative_category",)
    text = _text(record)
    scores: list[tuple[int, int, str]] = []
    patterns = getattr(bootstrap_module, "PLANNING_CATEGORY_PATTERNS", ())
    for order, (category, terms) in enumerate(patterns):
        hits = _count_terms(text, terms)
        if hits:
            scores.append((hits, -order, category))
    if not scores:
        return "OTHER", ("planning_category_unresolved",)
    _, _, category = max(scores)
    return category, (f"planning_category:{category}",)


def infer_portfolio_lane(bootstrap_module: Any, record: Any, planning_category: str) -> tuple[str, tuple[str, ...]]:
    """Boundary-safe equivalent of the legacy planning lane classifier."""
    text = _text(record)
    sources = _sources(record)
    risk_terms = getattr(bootstrap_module, "RISK_TERMS", ())
    opinion_terms = getattr(bootstrap_module, "OPINION_TERMS", ())
    practical_terms = getattr(bootstrap_module, "PRACTICAL_TERMS", ())
    research_terms = getattr(bootstrap_module, "RESEARCH_TERMS", ())

    if _count_terms(text, risk_terms):
        return "RISK", ("lane:RISK",)
    if any(re.search(p, text, re.I) for p in NEWS_EVENT_PATTERNS) or _count_terms(text, opinion_terms):
        return "DISCOVERY", ("lane:DISCOVERY",)
    if "ArXiv" in sources:
        has_artifact, artifact_reasons = bootstrap_module.has_implementation_artifact(record)
        if has_artifact:
            return "PRACTICAL", ("lane:PRACTICAL_ARXIV_IMPLEMENTATION", *artifact_reasons)
        return "RESEARCH", ("lane:RESEARCH_ARXIV_NO_IMPLEMENTATION", *artifact_reasons)
    if "GitHub" in sources or _count_terms(text, practical_terms):
        return "PRACTICAL", ("lane:PRACTICAL",)
    if _count_terms(text, research_terms):
        return "RESEARCH", ("lane:RESEARCH",)
    if planning_category and planning_category != "OTHER":
        return "PRACTICAL", ("lane:PRACTICAL_BY_CATEGORY",)
    return "DISCOVERY", ("lane:DISCOVERY_FALLBACK",)


def technology_layer(record: Any, planning_category: str, lane: str) -> tuple[str, tuple[str, ...]]:
    """Classify portfolio layer independently from discovery source and Adoption."""
    sources = _sources(record)
    text = _text(record)

    if lane == "RESEARCH" or ("ArXiv" in sources and lane != "PRACTICAL"):
        return "DEEP_TECH", ("technology_layer:DEEP_TECH",)

    # Product Hunt is discovery only. APPLIED_AI requires product taxonomy or an
    # explicit product/service term plus a strategic AI/technology signal.
    if planning_category == "PRODUCT":
        return "APPLIED_AI", ("technology_layer:APPLIED_AI_PRODUCT_CATEGORY",)
    if any(_has_term(text, term) for term in PRODUCT_TERMS) and any(
        _has_term(text, term) for term in STRATEGIC_TECH_TERMS
    ):
        return "APPLIED_AI", ("technology_layer:APPLIED_AI_TECHNICAL_PRODUCT",)

    return "PRACTICAL_TECH", ("technology_layer:PRACTICAL_TECH",)


def portfolio_base_priority(record: Any, now: datetime | None = None) -> tuple[float, tuple[str, ...]]:
    """Source-neutral planning score; never an Adoption Score."""
    now = now or datetime.now(timezone.utc)
    reasons: list[str] = []
    screening = max(0.0, min(100.0, float(getattr(record, "screening_score", 0.0) or 0.0)))

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
    """Estimate paid-product usefulness without rewarding a repo merely for being a repo."""
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
        score += 3; reasons.append("deep_tech_option_value:+3")

    strategic_hits = _count_terms(text, STRATEGIC_TECH_TERMS)
    if strategic_hits >= 3:
        score += 9; reasons.append("strategic_technology_signals:+9")
    elif strategic_hits >= 1:
        score += 5; reasons.append("strategic_technology_signals:+5")

    if planning_category == "OTHER":
        score -= 4; reasons.append("planning_category_other:-4")
    else:
        score += 3; reasons.append(f"planning_category_resolved:{planning_category}:+3")

    if "GitHub" in sources and planning_category in {"DEVTOOLS", "OTHER"} and strategic_hits == 0:
        score -= 10; reasons.append("generic_github_repo_without_decision_signal:-10")

    if any(_has_term(text, term) for term in GENERIC_REPO_TERMS) and strategic_hits == 0:
        score -= 8; reasons.append("generic_learning_or_template_repo:-8")

    return round(max(-25.0, min(25.0, score)), 2), tuple(reasons)


def _build_items(bootstrap_module: Any, records: Iterable[Any], now: datetime) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in records:
        base, base_reasons = portfolio_base_priority(record, now=now)
        pcat, cat_reasons = infer_portfolio_category(bootstrap_module, record)
        lane, lane_reasons = infer_portfolio_lane(bootstrap_module, record, pcat)
        utility, utility_reasons = portfolio_utility_score(record, pcat, lane)
        layer, _ = technology_layer(record, pcat, lane)
        items.append({
            "record": record,
            "base": base,
            "utility": utility,
            "planning_category": pcat,
            "lane": lane,
            "layer": layer,
            "reasons": base_reasons + cat_reasons + lane_reasons + utility_reasons,
        })
    return items


def rank_portfolio_records(
    bootstrap_module: Any,
    records: Iterable[Any],
    limit: int = 30,
    tolerance: float | None = None,
    now: datetime | None = None,
) -> list[Any]:
    """Rank a pre-filtered candidate pool with profit-protecting diversification.

    A diversity preference may reorder only candidates whose core score is within
    ``tolerance`` points of the strongest remaining candidate. Therefore diversity
    can never force a materially weaker record upward.
    """
    now = now or datetime.now(timezone.utc)
    tolerance = DEFAULT_PORTFOLIO_TOLERANCE if tolerance is None else max(0.0, float(tolerance))
    remaining = _build_items(bootstrap_module, records, now)
    if limit <= 0 or not remaining:
        return []

    selected: list[dict[str, Any]] = []
    source_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    lane_counts: Counter[str] = Counter()
    layer_counts: Counter[str] = Counter()

    def core(item: dict[str, Any]) -> float:
        return float(item["base"]) + float(item["utility"])

    def source_repeat(item: dict[str, Any]) -> float:
        names = sorted(_sources(item["record"])) or ["Unknown"]
        return sum(source_counts[x] for x in names) / len(names)

    def concentration_penalty(item: dict[str, Any]) -> float:
        pcat = item["planning_category"]
        lane = item["lane"]
        layer = item["layer"]
        repeat = source_repeat(item)
        penalty = (
            repeat * 2.5
            + category_counts[pcat] * 2.5
            + lane_counts[lane] * 1.5
            + layer_counts[layer] * 2.0
        )
        if pcat == "OTHER":
            penalty += 2.0 + category_counts[pcat] * 1.5
        if "GitHub" in _sources(item["record"]) and pcat in {"DEVTOOLS", "OTHER"}:
            penalty += repeat * 1.5
        return penalty

    def stable_key(item: dict[str, Any]) -> tuple[float, float, str]:
        record = item["record"]
        return (
            core(item),
            float(getattr(record, "screening_score", 0.0) or 0.0),
            str(getattr(record, "name", "")).lower(),
        )

    while remaining and len(selected) < limit:
        strongest = max(remaining, key=stable_key)
        strongest_core = core(strongest)
        competitive = [x for x in remaining if core(x) >= strongest_core - tolerance]

        def diversified_key(item: dict[str, Any]) -> tuple[float, float, float, str]:
            record = item["record"]
            adjusted = core(item) - concentration_penalty(item)
            return (
                adjusted,
                core(item),
                float(getattr(record, "screening_score", 0.0) or 0.0),
                str(getattr(record, "name", "")).lower(),
            )

        chosen = dict(max(competitive, key=diversified_key))
        penalty = concentration_penalty(chosen)
        chosen["portfolio_priority"] = round(core(chosen) - penalty, 2)
        chosen["reasons"] = chosen["reasons"] + (
            f"run131_competitive_tolerance:{tolerance:.1f}",
            f"run131_diversity_penalty:{penalty:.2f}",
        )
        selected.append(chosen)

        record = chosen["record"]
        for source in (sorted(_sources(record)) or ["Unknown"]):
            source_counts[source] += 1
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


def balanced_plan_candidates(
    bootstrap_module: Any,
    records: Iterable[Any],
    limit: int = 30,
    max_source_share: float = 0.60,
    now: datetime | None = None,
    tolerance: float | None = None,
) -> list[Any]:
    """Portfolio-aware bootstrap plan preserving the historical call contract.

    ``max_source_share`` is retained only so older callers do not break. Run131
    deliberately does not enforce a hard source cap; tolerance-protected diversity
    replaces it.
    """
    _ = max_source_share
    now = now or datetime.now(timezone.utc)
    eligible = [r for r in records if bootstrap_module.is_bootstrap_eligible(r, now=now)]
    return rank_portfolio_records(bootstrap_module, eligible, limit=limit, tolerance=tolerance, now=now)


def install_on(bootstrap_module: Any) -> None:
    """Install Run131 as a reversible planning overlay for manual Bootstrap."""
    original = bootstrap_module.plan_candidates

    def _plan(records: Iterable[Any], limit: int = 30, max_source_share: float = 0.60, now: datetime | None = None) -> list[Any]:
        return balanced_plan_candidates(
            bootstrap_module, records, limit=limit, max_source_share=max_source_share, now=now
        )

    _plan.__name__ = "run131_profit_aligned_plan_candidates"
    _plan.__doc__ = "Run131 tolerance-protected technology portfolio planning policy."
    _plan._run131_original = original  # type: ignore[attr-defined]
    bootstrap_module.plan_candidates = _plan
