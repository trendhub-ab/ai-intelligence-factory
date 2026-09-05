"""Paid-product delivery and Evidence Health maintenance orchestration.

Run237 extracts this operational maintenance surface from ``pipeline.py`` without
changing its policy.  The module deliberately receives provider/network/runtime
objects as dependencies: importing it must never create credentials, clients,
Gemini calls, Notion calls, or other side effects.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Callable


def previous_month_id(today) -> str:
    """Return the YYYY-MM period immediately preceding ``today``."""
    first = today.replace(day=1)
    prev = first - timedelta(days=1)
    return f"{prev.year:04d}-{prev.month:02d}"


def current_month_id(today) -> str:
    """Return ``today`` as a YYYY-MM period id."""
    return f"{today.year:04d}-{today.month:02d}"


def monthly_digest_targets(local_today) -> list[str]:
    """Return the exact monthly periods reconciled by the paid-product runner.

    The most recent three completed periods are always re-checked.  On the last
    local calendar day, the current month is appended so its idempotent history
    digest can be materialized before the month rolls over.
    """
    targets: list[str] = []
    cursor = local_today.replace(day=1)
    for _ in range(3):
        cursor = (cursor - timedelta(days=1)).replace(day=1)
        targets.append(f"{cursor.year:04d}-{cursor.month:02d}")

    tomorrow = local_today + timedelta(days=1)
    if tomorrow.month != local_today.month:
        targets.append(current_month_id(local_today))

    # Preserve insertion order while retaining the historical de-duplication
    # contract used by pipeline.py.
    return list(dict.fromkeys(targets))


def run_evidence_health_maintenance(
    *,
    evidence_ledger: Any,
    decision_intelligence: Any,
    requests_module: Any,
    logger: Any,
    github_repo_name_from_url: Callable[[str], Any],
    fetch_github_readme_context: Callable[[str], str],
    extract_arxiv_id: Callable[[str], Any],
    fetch_arxiv_api_context: Callable[[str], tuple[str, dict]],
    http_get_health_limited: Callable[[str, int], tuple[int, str, str]],
    readable_html_text_parser: Any,
    web_context_max_bytes: int,
    now_iso: Callable[[], str],
) -> dict:
    """Run zero-Gemini evidence health checks with historical behavior intact.

    A material change only accelerates Technology ``Next Review`` and records the
    health result.  It never performs model work and never changes publication or
    quality gates.
    """
    result = {
        "enabled": evidence_ledger.ENABLE_EVIDENCE_LEDGER,
        "checked": 0,
        "material": 0,
        "missing": 0,
        "cosmetic": 0,
        "moved": 0,
        "errors": 0,
    }
    if not evidence_ledger.ENABLE_EVIDENCE_LEDGER:
        return result

    token = decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY
    for state in evidence_ledger.query_health_candidates(token):
        try:
            def fetcher(url: str):
                source_type = str(state.get("source_type") or "").lower()
                if source_type == "github":
                    repo_name = github_repo_name_from_url(url)
                    if repo_name:
                        text = fetch_github_readme_context(repo_name)
                        return (200 if text else 0), text, url
                if source_type == "arxiv":
                    arxiv_id = extract_arxiv_id(url)
                    if arxiv_id:
                        text, details = fetch_arxiv_api_context(arxiv_id)
                        final = details.get("arxiv_versioned_url") or url
                        return (200 if text else 0), text, final

                status, text, final = http_get_health_limited(
                    url, min(web_context_max_bytes, 1_500_000)
                )
                if status == 200 and (
                    "<html" in text[:1200].lower()
                    or "<!doctype html" in text[:1200].lower()
                ):
                    parser = readable_html_text_parser()
                    try:
                        parser.feed(text)
                        text = parser.text()
                    except Exception:
                        pass
                return status, text, final

            health = evidence_ledger.check_health(state, fetcher)
            result["checked"] += 1
            health_state = health.get("health")
            if health_state == "COSMETIC_CHANGE":
                result["cosmetic"] += 1
            elif health_state == "MOVED":
                result["moved"] += 1
            elif health_state == "MISSING":
                result["missing"] += 1

            if health.get("material"):
                result["material"] += 1
                tech_page = state.get("tech_page_id")
                if tech_page:
                    patch = requests_module.patch(
                        f"https://api.notion.com/v1/pages/{tech_page}",
                        json={
                            "properties": {
                                decision_intelligence.TECH_PROP_NEXT_REVIEW: {
                                    "date": {"start": now_iso()}
                                }
                            }
                        },
                        headers=decision_intelligence._headers(),
                        timeout=10,
                    )
                    if patch.status_code != 200:
                        raise RuntimeError(
                            f"Technology Next Review acceleration failed: {patch.status_code}"
                        )
                evidence_ledger.update_health(
                    state["page_id"], health, token, rereview_triggered=True
                )
            else:
                evidence_ledger.update_health(
                    state["page_id"], health, token, rereview_triggered=False
                )
        except Exception as exc:
            result["errors"] += 1
            logger.warning(
                "[EVIDENCE HEALTH FAILED] %s: %s", state.get("url"), exc
            )

    logger.info("[EVIDENCE HEALTH] %s", result)
    return result


def run_product_delivery_maintenance(
    *,
    enabled: bool,
    decision_intelligence: Any,
    logger: Any,
    evidence_health_runner: Callable[[], dict],
    today=None,
    today_factory: Callable[[], Any],
) -> dict:
    """Run paid-product maintenance without changing its historical contracts."""
    result = {"subscriber": None, "monthly": [], "evidence_health": None}
    if not (enabled and decision_intelligence.ENABLE_DECISION_INTELLIGENCE_DB):
        return result

    try:
        result["evidence_health"] = evidence_health_runner()
    except Exception as exc:
        logger.error("[EVIDENCE HEALTH MAINTENANCE FAILED] %s", exc)

    try:
        result["subscriber"] = decision_intelligence.sync_subscriber_technology_db()
        if result["subscriber"] and result["subscriber"].get("enabled"):
            logger.info("[SUBSCRIBER TECH SYNC] %s", result["subscriber"])
    except Exception as exc:
        logger.error("[SUBSCRIBER TECH SYNC FAILED] %s", exc)

    if decision_intelligence.ENABLE_DECISION_MONTHLY_DIGEST:
        local_today = today or today_factory()
        for period in monthly_digest_targets(local_today):
            try:
                row = decision_intelligence.create_history_monthly_digest(period)
                result["monthly"].append(row)
                if row.get("created"):
                    logger.info(
                        "[DECISION MONTHLY CREATED] %s events=%s",
                        period,
                        row.get("events"),
                    )
            except Exception as exc:
                logger.error("[DECISION MONTHLY FAILED] %s: %s", period, exc)

    return result
