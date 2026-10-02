#!/usr/bin/env python3
"""Zero-model conversion-copy diagnostics for the free-note membership funnel.

Consumes subscription_attribution.py rollup output only. It never calls a model,
never fetches subscriber identities, never mutates public copy, and never changes
production ranking. Recommendations are deterministic hypotheses for human review.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

MIN_ARTICLE_VIEWS = 100
MIN_ARTICLE_CLICKS = 10
MIN_GROUP_VIEWS = 250
CTR_FLOOR = 0.005
POST_CLICK_CONVERSION_FLOOR = 0.03
RELATIVE_WEAK_RATIO = 0.60


def _finite_nonnegative(value: Any) -> float | None:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(num) or num < 0:
        return None
    return num


def _weak(value: float | None, baseline: float | None, absolute_floor: float) -> bool:
    if value is None:
        return False
    threshold = absolute_floor
    if baseline is not None and baseline > 0:
        threshold = max(threshold, baseline * RELATIVE_WEAK_RATIO)
    return value < threshold


def _opportunity(
    *,
    scope: str,
    key: str,
    views: float | None,
    clicks: float | None,
    subscribers: float | None,
    ctr: float | None,
    post_click: float | None,
    baseline_ctr: float | None,
    baseline_post_click: float | None,
    min_views: int,
) -> dict:
    if views is None or views < min_views:
        state = "INSUFFICIENT_DATA"
        action = "計測を継続する。コピー変更の判断材料がまだ不足しています。"
        reason = "views_below_threshold"
    elif clicks is None:
        state = "TRACKING_GAP"
        action = "CTAクリック計測を確認する。コピー評価の前に計測欠損を解消します。"
        reason = "cta_clicks_missing"
    elif _weak(ctr, baseline_ctr, CTR_FLOOR):
        state = "CTA_COPY_OR_PLACEMENT"
        action = "CTAの見出し・価値提案・配置を人間レビューする。LPはまだ主因と決めつけません。"
        reason = "weak_click_through_rate"
    elif subscribers is None:
        state = "POST_CLICK_UNMEASURED"
        action = "加入までの帰属計測を整える。クリック後の良否はまだ判定しません。"
        reason = "subscriber_attribution_missing"
    elif clicks < MIN_ARTICLE_CLICKS:
        state = "INSUFFICIENT_POST_CLICK_DATA"
        action = "クリック母数を増やしてからLP/オファーを評価する。"
        reason = "clicks_below_post_click_threshold"
    elif _weak(post_click, baseline_post_click, POST_CLICK_CONVERSION_FLOOR):
        state = "OFFER_OR_LP"
        action = "membership LPの価値説明・価格納得感・加入手順を人間レビューする。記事CTAは主因と決めつけません。"
        reason = "weak_post_click_conversion"
    else:
        state = "NO_COPY_CHANGE_INDICATED"
        action = "現行コピーを維持し、追加データを集める。"
        reason = "funnel_not_materially_weak"

    volume = max(0.0, views or 0.0)
    ctr_gap = 0.0
    if ctr is not None:
        target = max(CTR_FLOOR, (baseline_ctr or 0.0) * RELATIVE_WEAK_RATIO)
        ctr_gap = max(0.0, target - ctr)
    post_gap = 0.0
    if post_click is not None:
        target = max(POST_CLICK_CONVERSION_FLOOR, (baseline_post_click or 0.0) * RELATIVE_WEAK_RATIO)
        post_gap = max(0.0, target - post_click)
    priority = round(min(100.0, math.log10(volume + 1) * 18 + ctr_gap * 1200 + post_gap * 180), 2)

    return {
        "scope": scope,
        "key": key,
        "state": state,
        "reason": reason,
        "priority_score": priority,
        "views": views,
        "cta_clicks": clicks,
        "new_subscribers": subscribers,
        "cta_click_rate": ctr,
        "subscriber_conversion_per_click": post_click,
        "recommended_human_review": action,
        "copy_mutation_permitted": False,
        "model_calls": 0,
    }


def _group_rows(rows: list[dict], key_name: str, overall: dict) -> list[dict]:
    out = []
    for row in rows or []:
        metrics = row.get("metrics") or {}
        views = _finite_nonnegative(metrics.get("note_views"))
        clicks = _finite_nonnegative(metrics.get("cta_clicks"))
        subscribers = _finite_nonnegative(metrics.get("new_subscribers"))
        out.append(_opportunity(
            scope=key_name,
            key=str(row.get(key_name) or "UNKNOWN"),
            views=views,
            clicks=clicks,
            subscribers=subscribers,
            ctr=_finite_nonnegative(row.get("cta_click_rate")),
            post_click=(subscribers / clicks) if subscribers is not None and clicks and clicks > 0 else None,
            baseline_ctr=_finite_nonnegative(overall.get("overall_cta_click_rate")),
            baseline_post_click=_finite_nonnegative(overall.get("overall_subscriber_conversion_per_click")),
            min_views=MIN_GROUP_VIEWS,
        ))
    return out


def build_diagnostics(rollup: dict) -> dict:
    if not isinstance(rollup, dict):
        raise ValueError("rollup must be an object")
    if rollup.get("ranking_feedback_enabled") is not False:
        raise ValueError("conversion diagnostics require ranking feedback to remain disabled")
    if "articles" not in rollup or not isinstance(rollup.get("articles"), list):
        raise ValueError("rollup articles are required")

    baseline_ctr = _finite_nonnegative(rollup.get("overall_cta_click_rate"))
    baseline_post = _finite_nonnegative(rollup.get("overall_subscriber_conversion_per_click"))
    articles = []
    for row in rollup["articles"]:
        metrics = row.get("metrics") or {}
        views = _finite_nonnegative(metrics.get("note_views"))
        clicks = _finite_nonnegative(metrics.get("cta_clicks"))
        subscribers = _finite_nonnegative(metrics.get("new_subscribers"))
        articles.append(_opportunity(
            scope="article",
            key=str(row.get("article_id") or ""),
            views=views,
            clicks=clicks,
            subscribers=subscribers,
            ctr=_finite_nonnegative(row.get("cta_click_rate")),
            post_click=_finite_nonnegative(row.get("subscriber_conversion_per_click")),
            baseline_ctr=baseline_ctr,
            baseline_post_click=baseline_post,
            min_views=MIN_ARTICLE_VIEWS,
        ))

    groups = []
    groups.extend(_group_rows(rollup.get("performance_by_source") or [], "source", rollup))
    groups.extend(_group_rows(rollup.get("performance_by_topic") or [], "portfolio_topic", rollup))
    groups.extend(_group_rows(rollup.get("performance_by_cta_copy") or [], "cta_copy_id", rollup))

    opportunities = sorted(
        [x for x in articles + groups if x["state"] not in {"NO_COPY_CHANGE_INDICATED", "INSUFFICIENT_DATA"}],
        key=lambda x: (-x["priority_score"], x["scope"], x["key"]),
    )
    return {
        "schema_version": 1,
        "mode": "zero_model_human_review_only",
        "model_calls": 0,
        "copy_mutation_permitted": False,
        "publication_mutation_permitted": False,
        "ranking_feedback_enabled": False,
        "privacy": "aggregate metrics only; subscriber PII forbidden",
        "baseline": {
            "overall_cta_click_rate": baseline_ctr,
            "overall_subscriber_conversion_per_click": baseline_post,
        },
        "article_diagnostics": articles,
        "group_diagnostics": groups,
        "prioritized_opportunities": opportunities,
        "policy": (
            "Diagnostics identify likely funnel bottlenecks only. They do not generate or publish replacement copy. "
            "A human must approve any later copy experiment."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollup", type=Path, default=Path("subscription_attribution/metrics_rollup.json"))
    parser.add_argument("--output", type=Path, default=Path("subscription_attribution/conversion_copy_diagnostics.json"))
    args = parser.parse_args()
    data = json.loads(args.rollup.read_text(encoding="utf-8"))
    result = build_diagnostics(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "model_calls": 0,
        "copy_mutation_permitted": False,
        "prioritized_opportunities": len(result["prioritized_opportunities"]),
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
