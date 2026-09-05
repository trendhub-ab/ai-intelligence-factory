"""Zero-model Source ROI profile/allocation policy extracted from pipeline.py (Run241)."""


def source_roi_smoothed_rate(success: float, total: float, prior_rate: float, prior_weight: float) -> float:
    total = max(0.0, float(total or 0.0))
    success = max(0.0, float(success or 0.0))
    return max(0.0, min(1.0, (success + prior_rate * prior_weight) / (total + prior_weight)))


def compute_source_roi_profile(state: dict | None, *, sources, history_runs: int, recency_decay: float,
                               stock_weight: float, ready_weight: float, efficiency_weight: float,
                               min_screened: int, min_deep_dive_attempts: int, exploration_weight: float,
                               enable_learning: bool, min_mature_sources: int, smoothed_rate=source_roi_smoothed_rate) -> dict[str, dict]:
    runs = list((state or {}).get("runs", []))[-max(1, history_runs):]
    aggregate = {
        src: {"screened": 0.0, "stock_saved": 0.0, "deep_dive_attempted": 0.0,
              "generation_requests": 0.0, "ready": 0.0, "review": 0.0}
        for src in sources
    }
    decay = max(0.0, min(1.0, recency_decay))
    for age, run in enumerate(reversed(runs)):
        weight = decay ** age
        metrics = run.get("sources", {}) if isinstance(run, dict) else {}
        for src in sources:
            row = metrics.get(src, {}) if isinstance(metrics, dict) else {}
            for key in aggregate[src]:
                try:
                    aggregate[src][key] += max(0.0, float(row.get(key, 0) or 0)) * weight
                except (TypeError, ValueError):
                    pass

    result: dict[str, dict] = {}
    mature_count = 0
    for src, row in aggregate.items():
        stock_rate = smoothed_rate(row["stock_saved"], row["screened"], 0.35, 20.0)
        ready_rate = smoothed_rate(row["ready"], row["deep_dive_attempted"], 0.25, 6.0)
        efficiency_rate = smoothed_rate(row["ready"], row["generation_requests"], 0.18, 6.0)
        total_weight = max(1e-9, stock_weight + ready_weight + efficiency_weight)
        score = 100.0 * (
            stock_rate * stock_weight + ready_rate * ready_weight + efficiency_rate * efficiency_weight
        ) / total_weight
        mature = (
            row["screened"] >= max(1, min_screened)
            and row["deep_dive_attempted"] >= max(1, min_deep_dive_attempts)
        )
        if mature:
            mature_count += 1
        exploration = min(1.0, 1.0 / ((1.0 + row["screened"] / max(1, min_screened)) ** 0.5))
        allocation_weight = max(
            0.05,
            (1.0 - max(0.0, min(0.5, exploration_weight))) * (score / 100.0)
            + max(0.0, min(0.5, exploration_weight)) * exploration,
        )
        result[src] = {
            **row, "stock_yield": round(stock_rate, 4), "ready_yield": round(ready_rate, 4),
            "generation_efficiency": round(efficiency_rate, 4), "roi_score": round(score, 2),
            "allocation_weight": round(allocation_weight, 6), "mature": mature,
        }
    learning_active = enable_learning and mature_count >= max(1, min_mature_sources)
    for row in result.values():
        row["learning_active"] = learning_active
    return result


def allocate_source_fetch_limits(profile: dict[str, dict] | None, total_limit: int | None = None, *,
                                 base: dict[str, int], enable_learning: bool, max_screening_candidates: int,
                                 max_fetch_by_source: dict[str, int], sources, min_fetch_per_source: int) -> dict[str, int]:
    if not enable_learning or not profile or not any(row.get("learning_active") for row in profile.values()):
        return dict(base)
    total = max(0, int(max_screening_candidates if total_limit is None else total_limit))
    caps = {
        src: max(base.get(src, 0), max(0, int(max_fetch_by_source.get(src, base.get(src, 0)))))
        for src in sources
    }
    floors = {src: min(caps[src], max(0, min_fetch_per_source)) for src in sources}
    if sum(floors.values()) > total:
        return {src: min(base[src], max(0, total // len(sources))) for src in sources}

    allocation = dict(floors)
    remaining = min(total, sum(caps.values())) - sum(allocation.values())
    while remaining > 0:
        available = [src for src in sources if allocation[src] < caps[src]]
        if not available:
            break
        weight_sum = sum(max(0.0001, float((profile.get(src) or {}).get("allocation_weight", 0.5))) for src in available)
        proposed = {}
        fractions = []
        for src in available:
            weight = max(0.0001, float((profile.get(src) or {}).get("allocation_weight", 0.5)))
            exact = remaining * weight / weight_sum
            room = caps[src] - allocation[src]
            add = min(room, int(exact))
            proposed[src] = add
            fractions.append((exact - int(exact), weight, src))
        used = sum(proposed.values())
        for src, add in proposed.items():
            allocation[src] += add
        remaining -= used
        if remaining <= 0:
            break
        progressed = False
        for _frac, _weight, src in sorted(fractions, reverse=True):
            if remaining <= 0:
                break
            if allocation[src] < caps[src]:
                allocation[src] += 1
                remaining -= 1
                progressed = True
        if not progressed and used == 0:
            break
    return allocation


def build_source_roi_run_metrics(screened: list[dict] | None, funnel, *, sources,
                                 reason_code_model_unavailable: str,
                                 reason_code_budget_exhausted: str,
                                 article_status_ready: str,
                                 article_status_needs_editorial_review: str,
                                 content_status_quality_failed: str,
                                 content_status_pending_retry: str) -> dict:
    metrics = {
        src: {"screened": 0, "stock_saved": 0, "deep_dive_attempted": 0,
              "generation_requests": 0, "ready": 0, "review": 0,
              "quality_failed": 0, "pending_retry": 0}
        for src in sources
    }
    for item in screened or []:
        src = item.get("repo", {}).get("source")
        if src not in metrics or item.get("screening_status") != "completed":
            continue
        metrics[src]["screened"] += 1
        if item.get("notion_page_id"):
            metrics[src]["stock_saved"] += 1
    for record in (funnel.records if funnel else []):
        src = record.get("source")
        if src not in metrics:
            continue
        reason_codes = {row.get("reason_code") for row in record.get("reason_codes", []) if isinstance(row, dict)}
        provider_or_budget_failure = bool(reason_codes & {
            reason_code_model_unavailable, reason_code_budget_exhausted
        }) or record.get("error_category") in {"provider_unavailable", "quota", "timeout", "budget"}
        if not provider_or_budget_failure:
            metrics[src]["deep_dive_attempted"] += 1
            metrics[src]["generation_requests"] += max(0, int(record.get("generation_request_count", 0) or 0))
        status = record.get("final_status")
        if status == article_status_ready:
            metrics[src]["ready"] += 1
        elif status == article_status_needs_editorial_review:
            metrics[src]["review"] += 1
        elif status == content_status_quality_failed:
            metrics[src]["quality_failed"] += 1
        elif status == content_status_pending_retry:
            metrics[src]["pending_retry"] += 1
    return metrics
