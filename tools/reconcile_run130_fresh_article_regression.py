#!/usr/bin/env python3
"""Surgically reconcile Run130 Fresh Article Regression onto the latest main-derived branch.

The patch is fail-closed and touches only regression-test plumbing:
- two REGEN_TEST environment controls,
- deterministic fresh-candidate selection,
- fixed/fresh selector routing,
- the manual regression workflow UI/env.

It does not change production acquisition, screening, Deep Dive, quality gates,
Notion persistence, publication, or Gemini call sites.
"""
from pathlib import Path


PIPELINE = Path("pipeline.py")
WORKFLOW = Path(".github/workflows/regression-test.yml")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one anchor, found {count}")
    return text.replace(old, new, 1)


def patch_pipeline(text: str) -> str:
    if "def get_fresh_regen_test_items(" in text:
        print("Run130 Fresh Article Regression already present in pipeline.py")
        return text

    env_anchor = '''REGEN_TEST_SOURCE = os.environ.get("REGEN_TEST_SOURCE", "").strip()
REGEN_TEST_OUTPUT_DIR = os.environ.get("REGEN_TEST_OUTPUT_DIR", "regen_test_outputs")

# Deep Dive一次情報補強。'''
    env_replacement = '''REGEN_TEST_SOURCE = os.environ.get("REGEN_TEST_SOURCE", "").strip()
REGEN_TEST_OUTPUT_DIR = os.environ.get("REGEN_TEST_OUTPUT_DIR", "regen_test_outputs")
# Run130: choose historical fixed/A-B articles or newly collected candidates.
# Fresh selection itself is deterministic and adds zero Gemini Screening calls.
REGEN_TEST_ARTICLE_SET = os.environ.get("REGEN_TEST_ARTICLE_SET", "fixed").strip().lower()
REGEN_FRESH_FETCH_PER_SOURCE = int(os.environ.get("REGEN_FRESH_FETCH_PER_SOURCE", "12"))

# Deep Dive一次情報補強。'''
    text = replace_once(text, env_anchor, env_replacement, "Run130 env controls")

    function_anchor = '''def save_regen_test_manuscript(repo: dict, manuscript: str, quality_status: str = "accepted",
                                 quality_failures: list[str] | None = None) -> str:
'''
    fresh_functions = '''def _fresh_regen_candidate_score(repo: dict) -> tuple[float, int, str]:
    """0-API ranking used only to choose fresh regression candidates."""
    publishability = publication_probability_score({"repo": repo})
    engagement = int(repo.get("stargazerCount") or 0)
    published = str(repo.get("publishedAt") or "")
    return (float(publishability), engagement, published)


def get_fresh_regen_test_items(limit: int = 3, source_filter: str = "") -> list[dict] | None:
    """Collect new regression candidates with zero Gemini Screening calls and zero product writes.

    The selector reuses normal source-native fetchers, Production Legal Safety,
    Notion URL READ-ONLY dedupe, and deterministic metadata ranking. A dedupe-read
    failure is fail-closed. Selection is never persisted as a Production Decision Score.
    """
    fetch_limit = min(max(REGEN_FRESH_FETCH_PER_SOURCE, max(limit, 1)), 50)
    source_groups = {
        "GitHub": fetch_github_trending(fetch_limit),
        "HackerNews": fetch_hackernews_top(fetch_limit),
        "ArXiv": fetch_arxiv_ai_ml(fetch_limit),
        "ProductHunt": fetch_producthunt_trending(fetch_limit),
    }
    if source_filter:
        source_groups = {source_filter: source_groups.get(source_filter, [])}

    existing_urls = get_existing_repo_urls()
    if existing_urls is None:
        logger.error("[REGEN FRESH] Notion重複チェックに失敗したためFail-Closed停止")
        return None

    eligible_by_source: dict[str, list[dict]] = {}
    seen_identity_urls: set[str] = set()
    seen_fallback_keys: set[str] = set()
    for source, repos in source_groups.items():
        bucket: list[dict] = []
        for repo in repos:
            is_safe, license_status = legal_safety_gate(repo)
            if not is_safe:
                logger.info("[REGEN FRESH SKIP: LICENSE] %s -> %s", repo.get("nameWithOwner"), license_status)
                continue
            identity_urls = candidate_identity_urls(repo)
            title_key = _normalize_title_for_match(repo.get("nameWithOwner", ""))
            fallback_key = f"{repo.get('source', source)}:{title_key}"
            if (
                (identity_urls & existing_urls)
                or (identity_urls & seen_identity_urls)
                or (not identity_urls and fallback_key in seen_fallback_keys)
            ):
                logger.info("[REGEN FRESH SKIP: KNOWN] %s", repo.get("nameWithOwner"))
                continue
            seen_identity_urls.update(identity_urls)
            if not identity_urls:
                seen_fallback_keys.add(fallback_key)
            bucket.append(repo)
        bucket.sort(key=_fresh_regen_candidate_score, reverse=True)
        eligible_by_source[source] = bucket

    selected: list[dict] = []
    source_order = ["GitHub", "HackerNews", "ArXiv", "ProductHunt"]
    active_order = [source for source in source_order if source in eligible_by_source]
    for source in active_order:
        if len(selected) >= limit:
            break
        if eligible_by_source.get(source):
            selected.append(eligible_by_source[source].pop(0))

    if len(selected) < limit:
        remaining = [repo for source in active_order for repo in eligible_by_source.get(source, [])]
        remaining.sort(key=_fresh_regen_candidate_score, reverse=True)
        selected.extend(remaining[: max(0, limit - len(selected))])

    items: list[dict] = []
    for repo in selected[:limit]:
        metadata_score = publication_probability_score({"repo": repo})
        items.append({
            "notion_page_id": None,
            "screening_score": max(NOTION_SAVE_THRESHOLD_SCORE, int(metadata_score)),
            "screening_reason": "Fresh regression: 0-API source-native metadata selection; not a production Decision Score",
            "repo": repo,
        })
    logger.info(
        "[REGEN FRESH] collected=%s selected=%s sources=%s GeminiScreeningCalls=0 writes=0",
        sum(len(v) for v in source_groups.values()),
        len(items),
        ",".join(str(x["repo"].get("source") or "Unknown") for x in items),
    )
    return items


''' + function_anchor
    text = replace_once(text, function_anchor, fresh_functions, "Run130 fresh selector functions")

    runner_anchor = '''    items = get_regen_test_items(REGEN_TEST_LIMIT, REGEN_TEST_SOURCE)
    if items is None:
        logger.error("[REGEN TEST ABORTED] 既存記事の読み出しに失敗しました。")
'''
    runner_replacement = '''    if REGEN_TEST_ARTICLE_SET not in {"fixed", "fresh"}:
        raise ValueError("REGEN_TEST_ARTICLE_SET must be fixed or fresh")
    if REGEN_TEST_ARTICLE_SET == "fresh":
        logger.warning(" REGEN ARTICLE SET: FRESH（新規候補・0-API選定）")
        items = get_fresh_regen_test_items(REGEN_TEST_LIMIT, REGEN_TEST_SOURCE)
    else:
        logger.warning(" REGEN ARTICLE SET: FIXED（既存Deep Dive A/B比較）")
        items = get_regen_test_items(REGEN_TEST_LIMIT, REGEN_TEST_SOURCE)
    if items is None:
        logger.error("[REGEN TEST ABORTED] 回帰テスト候補の読み出し/収集に失敗しました。")
'''
    text = replace_once(text, runner_anchor, runner_replacement, "Run130 runner routing")
    return text


def patch_workflow(text: str) -> str:
    if "article_set:" not in text:
        trigger_anchor = '''on:
  workflow_dispatch:

concurrency:
'''
        trigger_replacement = '''on:
  workflow_dispatch:
    inputs:
      article_set:
        description: 'Article set: fixed = existing A/B set, fresh = newly collected candidates'
        required: true
        default: 'fixed'
        type: choice
        options:
          - fixed
          - fresh

concurrency:
'''
        text = replace_once(text, trigger_anchor, trigger_replacement, "Run130 workflow input")

    env_anchor = '''          REGEN_TEST_MODE: "true"
          TZ: 'Asia/Tokyo'
'''
    env_replacement = '''          REGEN_TEST_MODE: "true"
          REGEN_TEST_ARTICLE_SET: ${{ inputs.article_set }}
          REGEN_TEST_LIMIT: "3"
          REGEN_FRESH_FETCH_PER_SOURCE: "12"
          TZ: 'Asia/Tokyo'
'''
    if "REGEN_TEST_ARTICLE_SET:" not in text:
        text = replace_once(text, env_anchor, env_replacement, "Run130 workflow env")

    ph_anchor = '''          NOTION_API_VERSION: "2026-03-11"
          GEMINI_SCREENING_MODEL_CANDIDATES:'''
    ph_replacement = '''          NOTION_API_VERSION: "2026-03-11"
          PRODUCTHUNT_DEVELOPER_TOKEN: ${{ secrets.PRODUCTHUNT_DEVELOPER_TOKEN }}
          GEMINI_SCREENING_MODEL_CANDIDATES:'''
    if "PRODUCTHUNT_DEVELOPER_TOKEN:" not in text:
        text = replace_once(text, ph_anchor, ph_replacement, "Run130 Product Hunt regression secret")
    return text


def main() -> None:
    pipeline_text = patch_pipeline(PIPELINE.read_text(encoding="utf-8"))
    workflow_text = patch_workflow(WORKFLOW.read_text(encoding="utf-8"))
    PIPELINE.write_text(pipeline_text, encoding="utf-8")
    WORKFLOW.write_text(workflow_text, encoding="utf-8")
    print("Run130 Fresh Article Regression reconciled successfully")


if __name__ == "__main__":
    main()
