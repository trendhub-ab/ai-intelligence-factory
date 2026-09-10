"""Run343c one-shot recovery for the exact DeepSeek V4.1 Flash article.

The requested Quality Failed row was never article-saved, so generic regeneration
inventory is not authoritative. This temporary route binds to one exact Notion page and
re-verifies page id, title, canonical source URL, source, and lifecycle before any
provider call or mutation. The auxiliary primary-evidence URL is checked when the REST
payload exposes it as a URL; an absent/non-URL representation cannot override the exact
canonical source URL that uniquely identifies this Hacker News item.
"""
from __future__ import annotations

import os
from typing import Any

import article_revalidation

TARGET_PAGE_ID = "3d7479ff-dca9-81eb-9256-ca37b93d410f"
TARGET_NAME = "DeepSeek launching v4.1 flash cheaper and more capable than v4 pro"
TARGET_URL = "https://news.ycombinator.com/item?id=49624603"
TARGET_SOURCE = "HackerNews"


def _rich_text(prop: dict[str, Any] | None) -> str:
    value = prop or {}
    rows = value.get("title") or value.get("rich_text") or []
    return "".join(str(row.get("plain_text") or "") for row in rows).strip()


def _select(prop: dict[str, Any] | None) -> str:
    return str(((prop or {}).get("select") or {}).get("name") or "").strip()


def _url(prop: dict[str, Any] | None) -> str:
    return str((prop or {}).get("url") or "").strip()


def _number(prop: dict[str, Any] | None) -> float | int | None:
    return (prop or {}).get("number")


def _date_start(prop: dict[str, Any] | None) -> str:
    return str(((prop or {}).get("date") or {}).get("start") or "").strip()


def candidate_from_page_payload(pipeline, payload: dict[str, Any]) -> dict[str, Any]:
    props = (payload or {}).get("properties") or {}
    name = _rich_text(props.get("記事名"))
    source_url = _url(props.get("元情報URL"))
    primary_url = _url(props.get("一次情報URL"))
    source = _select(props.get("情報源"))
    content_status = _select(props.get("コンテンツ状態"))
    article_status = _select(props.get("記事状態"))

    mismatches = []
    if str((payload or {}).get("id") or "").replace("-", "") != TARGET_PAGE_ID.replace("-", ""):
        mismatches.append("page_id")
    if name != TARGET_NAME:
        mismatches.append("title")
    if source_url != TARGET_URL:
        mismatches.append("source_url")
    if primary_url and primary_url != TARGET_URL:
        mismatches.append("primary_url")
    if source != TARGET_SOURCE:
        mismatches.append("source")
    if content_status != str(pipeline.CONTENT_STATUS_QUALITY_FAILED):
        mismatches.append("content_status")
    if article_status == str(getattr(pipeline, "ARTICLE_STATUS_READY", "Ready")):
        mismatches.append("already_ready")
    if mismatches:
        raise RuntimeError(
            "Run343c exact Notion target contract changed; refusing provider call/mutation: "
            + ",".join(mismatches)
        )

    screening_score = _number(props.get("選別スコア"))
    if screening_score is None:
        screening_score = _number(props.get("判断スコア"))
    screening_reason = _rich_text(props.get("選別理由")) or _rich_text(props.get("スコア内訳"))
    description = _rich_text(props.get("元情報要約"))
    engagement = _number(props.get("注目度"))
    published_at = _date_start(props.get("公開日"))

    repo = {
        "nameWithOwner": TARGET_NAME,
        "name": TARGET_NAME,
        "url": TARGET_URL,
        "source": TARGET_SOURCE,
        "description": description,
        "engagement": engagement or 0,
        "publishedAt": published_at,
        "published_at": published_at,
    }
    return {
        "repo": repo,
        "notion_page_id": TARGET_PAGE_ID,
        "screening_score": screening_score,
        "screening_reason": screening_reason,
        "source_url": TARGET_URL,
        "revalidation_article_status": article_status,
        "revalidation_content_status": content_status,
    }


def read_exact_target(pipeline) -> dict[str, Any]:
    try:
        response = pipeline.requests.get(
            f"https://api.notion.com/v1/pages/{TARGET_PAGE_ID}",
            headers=pipeline._notion_headers(),
            timeout=10,
        )
    except Exception as exc:
        raise RuntimeError(f"Run343c exact Notion page read failed: {exc}") from exc
    if int(getattr(response, "status_code", 0) or 0) != 200:
        raise RuntimeError(
            f"Run343c exact Notion page read failed HTTP {getattr(response, 'status_code', 0)}"
        )
    return candidate_from_page_payload(pipeline, response.json() or {})


def run_targeted_recovery(pipeline) -> dict[str, Any]:
    budget = article_revalidation._cap_validation_budget(pipeline)
    pipeline.logger.warning(
        "[RUN343C TARGETED RECOVERY] page=%s exact=%s url=%s request_budget=%s persist=true",
        TARGET_PAGE_ID, TARGET_NAME, TARGET_URL, budget,
    )
    item = read_exact_target(pipeline)
    repo = item["repo"]
    pipeline.logger.info(
        "[RUN343C TARGET VERIFIED] page=%s status=%s/%s score=%s source=%s",
        TARGET_PAGE_ID,
        item.get("revalidation_article_status"),
        item.get("revalidation_content_status"),
        item.get("screening_score"),
        repo.get("source"),
    )
    is_safe, license_status = pipeline.legal_safety_gate(repo)
    if not is_safe:
        raise RuntimeError(f"Run343c legal safety gate rejected target: {license_status}")

    generated = pipeline.generate_intelligence_report(
        repo,
        notion_page_id=TARGET_PAGE_ID,
        screening_score=item.get("screening_score"),
        screening_reason=item.get("screening_reason", ""),
        candidate_rank=1,
        candidate_origin="new",
        attribution_context=item,
        persist_results=True,
    )
    if not generated:
        raise RuntimeError("Run343c target did not produce an accepted current-policy manuscript")
    manuscript, status = generated if isinstance(generated, tuple) else (generated, "accepted")
    if status != "accepted":
        raise RuntimeError(f"Run343c target remained non-Ready: status={status}")
    pipeline.logger.info(
        "[RUN343C TARGETED RECOVERY READY] %s chars=%s page=%s",
        TARGET_NAME, len(manuscript or ""), TARGET_PAGE_ID,
    )
    return {"accepted": 1, "page_id": TARGET_PAGE_ID, "name": TARGET_NAME, "url": TARGET_URL}


def main() -> None:
    article_revalidation.run_article_revalidation = run_targeted_recovery
    os.environ["AIIF_ONE_SHOT_MODE"] = "article_validation"
    import production_pipeline
    production_pipeline.main()


if __name__ == "__main__":
    main()
