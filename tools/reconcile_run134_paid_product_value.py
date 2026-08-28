#!/usr/bin/env python3
"""Surgically reconcile Run134 paid-product value diagnostics onto latest main.

This script is intentionally narrow and fail-closed. It preserves all existing
Run130/131 portfolio logic and only adds the deterministic Run134 diagnostics.
"""
from pathlib import Path


PATH = Path("inventory_bootstrap.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")

    constants_anchor = 'DEFAULT_RECENT_DAYS = int(os.environ.get("INVENTORY_BOOTSTRAP_RECENT_DAYS", "30"))\n\nNEWS_HOSTS = {'
    constants_replacement = '''DEFAULT_RECENT_DAYS = int(os.environ.get("INVENTORY_BOOTSTRAP_RECENT_DAYS", "30"))
# Run134: paid-product value-density diagnostics. Diagnostic only; does not hard-block launch yet.
DEFAULT_MIN_HIGH_UTILITY = int(os.environ.get("INVENTORY_BOOTSTRAP_MIN_HIGH_UTILITY", "8"))
DEFAULT_MIN_MEDIUM_PLUS_UTILITY = int(os.environ.get("INVENTORY_BOOTSTRAP_MIN_MEDIUM_PLUS_UTILITY", "18"))

GENERIC_UTILITY_PATTERNS = (
    r"導入には注意(?:が)?必要", r"AIを活用したい", r"慎重な(?:企業|チーム)",
    r"状況に応じて", r"ケースバイケース", r"検討が必要", r"一般的な",
    r"teams? that need this capability", r"teams? that cannot accept",
)

NEWS_HOSTS = {'''
    text = replace_once(text, constants_anchor, constants_replacement, "Run134 constants")

    function_anchor = '''def _recent(record: TechnologyRecord, now: datetime, recent_days: int) -> bool:
    dt = _parse_dt(record.last_reviewed)
    return bool(dt and (now - dt).days <= recent_days)
'''
    function_replacement = '''def paid_product_utility(record: TechnologyRecord) -> dict[str, Any]:
    """Deterministic member-value diagnostic; never changes Adoption status or score."""
    fields = {
        "main_risk": (record.main_risk or "").strip(),
        "best_for": (record.best_for or "").strip(),
        "avoid_for": (record.avoid_for or "").strip(),
        "short_rationale": (record.short_rationale or "").strip(),
    }
    score = 0
    reasons: list[str] = []
    # Concrete decision text: enough substance, not a generic placeholder.
    for name, value in fields.items():
        if len(value) >= 18:
            score += 12
        else:
            reasons.append(f"{name}_too_thin")
        if any(re.search(pattern, value, re.I) for pattern in GENERIC_UTILITY_PATTERNS):
            score -= 8
            reasons.append(f"{name}_generic")
    if record.primary_evidence_urls.strip():
        score += 14
    else:
        reasons.append("evidence_url_missing")
    if record.evidence_confidence == "HIGH":
        score += 14
    elif record.evidence_confidence == "MEDIUM":
        score += 10
    if record.production_readiness in {"HIGH", "MEDIUM", "LOW"}:
        score += 8
    if record.adoption_status in {"ADOPT", "TEST", "WATCH", "AVOID"}:
        score += 8
    # Best-for and Avoid-for should communicate different audiences/conditions.
    bf = fields["best_for"].lower()
    af = fields["avoid_for"].lower()
    if bf and af and bf != af:
        score += 6
    else:
        reasons.append("best_avoid_not_differentiated")
    score = max(0, min(100, score))
    band = "HIGH" if score >= 80 else "MEDIUM" if score >= 60 else "LOW"
    return {"score": score, "band": band, "reasons": sorted(set(reasons))}


def _recent(record: TechnologyRecord, now: datetime, recent_days: int) -> bool:
    dt = _parse_dt(record.last_reviewed)
    return bool(dt and (now - dt).days <= recent_days)
'''
    text = replace_once(text, function_anchor, function_replacement, "paid_product_utility insertion")

    signature_anchor = '''                       min_confidence_ratio: float = DEFAULT_MIN_CONFIDENCE_RATIO,
                       min_recent_ratio: float = DEFAULT_MIN_RECENT_RATIO,
                       recent_days: int = DEFAULT_RECENT_DAYS,
                       subscriber_visible_count: int | None = None,
'''
    signature_replacement = '''                       min_confidence_ratio: float = DEFAULT_MIN_CONFIDENCE_RATIO,
                       min_recent_ratio: float = DEFAULT_MIN_RECENT_RATIO,
                       recent_days: int = DEFAULT_RECENT_DAYS,
                       min_high_utility: int = DEFAULT_MIN_HIGH_UTILITY,
                       min_medium_plus_utility: int = DEFAULT_MIN_MEDIUM_PLUS_UTILITY,
                       subscriber_visible_count: int | None = None,
'''
    text = replace_once(text, signature_anchor, signature_replacement, "evaluate_readiness signature")

    calculation_anchor = '''    confidence_ratio = confident / n if n else 0.0
    recent_ratio = recent / n if n else 0.0

    blockers: list[str] = []
'''
    calculation_replacement = '''    confidence_ratio = confident / n if n else 0.0
    recent_ratio = recent / n if n else 0.0
    utility = [paid_product_utility(r) for r in sellable]
    high_utility = sum(x["band"] == "HIGH" for x in utility)
    medium_plus_utility = sum(x["band"] in {"HIGH", "MEDIUM"} for x in utility)
    utility_scores = [x["score"] for x in utility]
    utility_avg = (sum(utility_scores) / len(utility_scores)) if utility_scores else 0.0
    utility_blockers: list[str] = []
    if high_utility < min_high_utility:
        utility_blockers.append(f"high_utility<{min_high_utility} ({high_utility})")
    if medium_plus_utility < min_medium_plus_utility:
        utility_blockers.append(f"medium_plus_utility<{min_medium_plus_utility} ({medium_plus_utility})")

    blockers: list[str] = []
'''
    text = replace_once(text, calculation_anchor, calculation_replacement, "utility calculations")

    output_anchor = '''        "recent_review_ratio": round(recent_ratio, 4),
        "recent_days": recent_days,
        "inventory_ready": inventory_ready,
'''
    output_replacement = '''        "recent_review_ratio": round(recent_ratio, 4),
        "recent_days": recent_days,
        "paid_product_value": {
            "status": "STRONG" if not utility_blockers else "NEEDS_STRENGTHENING",
            "diagnostic_only": True,
            "high_utility_count": high_utility,
            "medium_plus_utility_count": medium_plus_utility,
            "average_utility_score": round(utility_avg, 2),
            "min_high_utility": min_high_utility,
            "min_medium_plus_utility": min_medium_plus_utility,
            "blockers": utility_blockers,
        },
        "inventory_ready": inventory_ready,
'''
    text = replace_once(text, output_anchor, output_replacement, "paid_product_value output")

    PATH.write_text(text, encoding="utf-8")
    print("Run134 paid-product value diagnostics reconciled successfully")


if __name__ == "__main__":
    main()
