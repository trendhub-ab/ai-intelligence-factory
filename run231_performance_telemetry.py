"""Zero-API performance telemetry for the production pipeline.

This module is intentionally observational.  It does not change arguments, return
values, exception behavior, quota accounting, retry rules, Evidence gates, quality
gates, persistence conditions, or model-call counts.  It wraps only the final
production functions *after* all historical runtime layers have been installed.
"""
from __future__ import annotations

from collections import defaultdict
from functools import wraps
import os
from time import perf_counter


ENABLED = os.environ.get("PIPELINE_PERFORMANCE_TELEMETRY", "true").strip().lower() in {
    "1", "true", "yes", "on"
}

# High-level boundaries only.  Avoid profiling every Python call: the goal is useful
# production attribution with effectively negligible runtime overhead.
TARGETS = (
    ("initialize_runtime", "runtime.initialize"),
    ("check_stale_content", "maintenance.stale_check"),
    ("fetch_github_trending", "source.github"),
    ("fetch_hackernews_top", "source.hackernews"),
    ("fetch_arxiv_ai_ml", "source.arxiv"),
    ("fetch_producthunt_trending", "source.producthunt"),
    ("get_existing_repo_urls", "notion.dedupe_read"),
    ("repair_existing_multilingual_notion_titles", "notion.title_repair"),
    ("screen_candidates_in_batches", "screening.batch"),
    ("calibrate_candidates", "screening.calibration"),
    ("save_screening_metadata_to_notion", "notion.stock_write"),
    ("save_observed_history", "persistence.observed_history"),
    ("generate_intelligence_report", "article.deep_dive"),
    ("process_article_backlog", "article.backlog"),
    ("run_product_reviews", "product.review"),
    ("generate_monthly_digest", "product.monthly_digest"),
    ("run_product_delivery_maintenance", "product.delivery_maintenance"),
    ("finalize_deep_dive_observability", "observability.finalize"),
)


class PerformanceTelemetry:
    def __init__(self, logger=None):
        self.logger = logger
        self.total_seconds = defaultdict(float)
        self.calls = defaultdict(int)
        self.failures = defaultdict(int)

    def record(self, stage: str, elapsed: float, failed: bool = False) -> None:
        self.total_seconds[stage] += max(0.0, float(elapsed))
        self.calls[stage] += 1
        if failed:
            self.failures[stage] += 1

    def report(self, total_elapsed: float | None = None) -> dict:
        rows = []
        for stage, seconds in sorted(self.total_seconds.items(), key=lambda item: item[1], reverse=True):
            rows.append({
                "stage": stage,
                "seconds": round(seconds, 3),
                "calls": self.calls[stage],
                "failures": self.failures[stage],
            })
        result = {
            "total_seconds": None if total_elapsed is None else round(float(total_elapsed), 3),
            "stages": rows,
        }
        if self.logger is not None:
            self.logger.info("[PERFORMANCE] total_seconds=%s", result["total_seconds"])
            for row in rows:
                self.logger.info(
                    "[PERFORMANCE] %-30s %9.3fs calls=%d failures=%d",
                    row["stage"], row["seconds"], row["calls"], row["failures"],
                )
        return result


def _wrap(telemetry: PerformanceTelemetry, original, stage: str):
    if getattr(original, "__run231_performance_wrapped__", False):
        return original

    @wraps(original)
    def measured(*args, **kwargs):
        started = perf_counter()
        failed = False
        try:
            return original(*args, **kwargs)
        except BaseException:
            failed = True
            raise
        finally:
            telemetry.record(stage, perf_counter() - started, failed=failed)

    measured.__run231_performance_wrapped__ = True
    return measured


def install(pipeline_module):
    """Attach high-level timers after all production quality/reliability layers."""
    if not ENABLED:
        return None
    existing = getattr(pipeline_module, "RUN231_PERFORMANCE_TELEMETRY", None)
    if existing is not None:
        return existing

    telemetry = PerformanceTelemetry(getattr(pipeline_module, "logger", None))
    for attr_name, stage in TARGETS:
        original = getattr(pipeline_module, attr_name, None)
        if callable(original):
            setattr(pipeline_module, attr_name, _wrap(telemetry, original, stage))

    original_main = getattr(pipeline_module, "main", None)
    if callable(original_main) and not getattr(original_main, "__run231_performance_main_wrapped__", False):
        @wraps(original_main)
        def measured_main(*args, **kwargs):
            started = perf_counter()
            try:
                return original_main(*args, **kwargs)
            finally:
                telemetry.report(perf_counter() - started)
        measured_main.__run231_performance_main_wrapped__ = True
        pipeline_module.main = measured_main

    pipeline_module.RUN231_PERFORMANCE_TELEMETRY = telemetry
    return telemetry
