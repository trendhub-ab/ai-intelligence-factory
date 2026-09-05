import argparse
import ast
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--write", action="store_true")
args = parser.parse_args()
path = Path("pipeline.py")
source = path.read_text()

if all(marker in source for marker in (
    "from notion_payloads import (",
    "from source_document_parsing import (",
    "from deferred_queue_policy import (",
)):
    ast.parse(source)
    print(f"Run242 migration already applied: {len(source.splitlines())} lines")
    raise SystemExit(0)

if len(source.splitlines()) != 11497:
    raise RuntimeError(f"Run242 expected 11497-line Run241 preimage, got {len(source.splitlines())}")
for marker in (
    "def build_notion_properties(",
    "class _ReadableHTMLTextParser(HTMLParser):",
    "def _build_evidence_metadata(",
    "def _deferred_serializable(",
    "def enqueue_deferred_candidates(",
):
    if marker not in source:
        raise RuntimeError(f"Run242 preimage marker missing: {marker}")

tree = ast.parse(source)
lines = source.splitlines(keepends=True)
nodes = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}

replacements: dict[str, str] = {
    "safe_chunk_text": '''def safe_chunk_text(text: str, limit: int = NOTION_BLOCK_LIMIT) -> list[str]:\n    return _safe_chunk_text_impl(text, limit)\n''',
    "_notion_date_property": "_notion_date_property = _notion_date_property_impl\n",
    "build_notion_properties": '''def build_notion_properties(repo_name, repo_url, score, score_breakdown_text, what_text,\n                             why_important_text, why_not_important_text, action_text,\n                             spdx_id, paradigm_shift_text="",\n                             alternative_comparison_text="", migration_cost_text="",\n                             source: str = "GitHub", engagement: int = 0, title_text: str = "",\n                             eyecatch_url: str = "", published_at: str | None = None,\n                             analyzed_at: str | None = None, report_meta: dict | None = None,\n                             screening_score: int | None = None, screening_reason: str = "") -> dict:\n    return _build_notion_properties_impl(\n        repo_name, repo_url, score, score_breakdown_text, what_text, why_important_text, why_not_important_text,\n        action_text, spdx_id, paradigm_shift_text, alternative_comparison_text, migration_cost_text, source,\n        engagement, title_text, eyecatch_url, published_at, analyzed_at, report_meta, screening_score,\n        screening_reason, config=globals(),\n    )\n''',
    "build_notion_manuscript_children": '''def build_notion_manuscript_children(clean_manuscript: str, caption: str = MANUSCRIPT_CAPTION_READY) -> list:\n    return _build_notion_manuscript_children_impl(\n        clean_manuscript, caption, chunker=lambda text: safe_chunk_text(text),\n    )\n''',
    "build_notion_payload": '''def build_notion_payload(repo_name, repo_url, score, score_breakdown_text, what_text,\n                          why_important_text, why_not_important_text, action_text,\n                          spdx_id, clean_manuscript, paradigm_shift_text="",\n                          alternative_comparison_text="", migration_cost_text="",\n                          source: str = "GitHub", engagement: int = 0, title_text: str = "",\n                          eyecatch_url: str = "", published_at: str | None = None,\n                          analyzed_at: str | None = None, report_meta: dict | None = None,\n                          screening_score: int | None = None, screening_reason: str = "") -> dict:\n    return _build_notion_payload_impl(\n        repo_name, repo_url, score, score_breakdown_text, what_text, why_important_text, why_not_important_text,\n        action_text, spdx_id, clean_manuscript, paradigm_shift_text, alternative_comparison_text, migration_cost_text,\n        source, engagement, title_text, eyecatch_url, published_at, analyzed_at, report_meta, screening_score,\n        screening_reason, parent=_notion_parent(), build_properties=build_notion_properties,\n        build_children=build_notion_manuscript_children,\n    )\n''',
    "build_metadata_notion_properties": '''def build_metadata_notion_properties(repo_name, repo_url, score, reason,\n                                      source: str = "GitHub", engagement: int = 0,\n                                      published_at: str | None = None,\n                                      analyzed_at: str | None = None,\n                                      source_summary: str = "",\n                                      spdx_id: str = "") -> dict:\n    return _build_metadata_notion_properties_impl(\n        repo_name, repo_url, score, reason, source, engagement, published_at, analyzed_at, source_summary, spdx_id,\n        config=globals(),\n    )\n''',
    "_github_repo_name_from_url": "_github_repo_name_from_url = _github_repo_name_from_url_impl\n",
    "_github_repo_identity": '''def _github_repo_identity(repo: dict) -> str:\n    return _github_repo_identity_impl(repo, repo_name_from_url=_github_repo_name_from_url)\n''',
    "_is_github_global_navigation_url": "_is_github_global_navigation_url = _is_github_global_navigation_url_impl\n",
    "_extract_markdown_evidence_links": '''def _extract_markdown_evidence_links(text: str) -> list[tuple[str, str]]:\n    return _extract_markdown_evidence_links_impl(text, is_global_navigation_url=_is_github_global_navigation_url)\n''',
    "_effective_evidence_source": '''def _effective_evidence_source(repo: dict) -> str:\n    return _effective_evidence_source_impl(\n        repo, repo_name_from_url=_github_repo_name_from_url, extract_arxiv_id=_extract_arxiv_id,\n    )\n''',
    "_is_redundant_arxiv_doi": "_is_redundant_arxiv_doi = _is_redundant_arxiv_doi_impl\n",
    "_ReadableHTMLTextParser": "_ReadableHTMLTextParser = _ReadableHTMLTextParserImpl\n",
    "_is_low_value_arxiv_url": "_is_low_value_arxiv_url = _is_low_value_arxiv_url_impl\n",
    "_ResearchLinkParser": "_ResearchLinkParser = _ResearchLinkParserImpl\n",
    "_compress_evidence": '''def _compress_evidence(text: str) -> str:\n    return _compress_evidence_impl(text, truncate_source_context=_truncate_source_context)\n''',
    "_build_evidence_metadata": "_build_evidence_metadata = _build_evidence_metadata_impl\n",
    "_deferred_ttl_days": '''def _deferred_ttl_days(shelf_life: str) -> int:\n    return _deferred_ttl_days_impl(\n        shelf_life, flash_ttl_days=DEFERRED_FLASH_TTL_DAYS, trend_ttl_days=DEFERRED_TREND_TTL_DAYS,\n        evergreen_ttl_days=DEFERRED_EVERGREEN_TTL_DAYS,\n    )\n''',
    "_deferred_key": '''def _deferred_key(candidate: dict) -> str:\n    return _deferred_key_impl(\n        candidate, candidate_identity_urls=candidate_identity_urls, normalize_title_for_match=_normalize_title_for_match,\n    )\n''',
    "_deferred_serializable": '''def _deferred_serializable(candidate: dict) -> dict:\n    return _deferred_serializable_impl(candidate, ttl_days=_deferred_ttl_days, key_for_candidate=_deferred_key)\n''',
    "load_deferred_deep_dive_queue": '''def load_deferred_deep_dive_queue() -> list[dict]:\n    payload = None\n    if EYECATCH_GITHUB_REPO and GH_PAT:\n        dest_path = f"{DEFERRED_DEEP_DIVE_GITHUB_DIR}/deferred_queue.json"\n        api_url = f"https://api.github.com/repos/{EYECATCH_GITHUB_REPO}/contents/{dest_path}"\n        try:\n            res = requests.get(api_url, headers={"Authorization": f"Bearer {GH_PAT}", "Accept": "application/vnd.github+json"}, params={"ref": EYECATCH_GITHUB_BRANCH}, timeout=15)\n            if res.status_code == 200:\n                raw = base64.b64decode(res.json().get("content", "")).decode("utf-8")\n                payload = json.loads(raw)\n            elif res.status_code not in {404}:\n                logger.warning("[DEFERRED LOAD] GitHub HTTP %s", res.status_code)\n        except Exception as exc:\n            logger.warning("[DEFERRED LOAD] GitHub fallback to local: %s", exc)\n    if payload is None:\n        try:\n            with open(DEFERRED_DEEP_DIVE_STATE_PATH, "r", encoding="utf-8") as handle:\n                payload = json.load(handle)\n        except FileNotFoundError:\n            payload = {"version": 1, "items": []}\n        except Exception as exc:\n            logger.warning("[DEFERRED LOAD] local state corrupt; fail-closed empty queue: %s", exc)\n            payload = {"version": 1, "items": []}\n    return _valid_deferred_items_impl(payload, max_queue=DEFERRED_DEEP_DIVE_MAX_QUEUE)\n''',
    "save_deferred_deep_dive_queue": '''def save_deferred_deep_dive_queue(items: list[dict]) -> bool:\n    payload = _build_deferred_payload_impl(items, max_queue=DEFERRED_DEEP_DIVE_MAX_QUEUE)\n    try:\n        directory = os.path.dirname(DEFERRED_DEEP_DIVE_STATE_PATH)\n        if directory: os.makedirs(directory, exist_ok=True)\n        with open(DEFERRED_DEEP_DIVE_STATE_PATH, "w", encoding="utf-8") as handle:\n            json.dump(payload, handle, ensure_ascii=False, indent=2)\n    except Exception as exc:\n        logger.error("[DEFERRED SAVE] local write failed: %s", exc)\n        return False\n    if not (EYECATCH_GITHUB_REPO and GH_PAT):\n        return not os.environ.get("GITHUB_ACTIONS")\n    dest_path = f"{DEFERRED_DEEP_DIVE_GITHUB_DIR}/deferred_queue.json"\n    api_url = f"https://api.github.com/repos/{EYECATCH_GITHUB_REPO}/contents/{dest_path}"\n    headers = {"Authorization": f"Bearer {GH_PAT}", "Accept": "application/vnd.github+json"}\n    try:\n        current = requests.get(api_url, headers=headers, params={"ref": EYECATCH_GITHUB_BRANCH}, timeout=15)\n        body = base64.b64encode(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii")\n        put = {"message": "chore: update deferred deep dive queue", "content": body, "branch": EYECATCH_GITHUB_BRANCH}\n        if current.status_code == 200: put["sha"] = current.json().get("sha")\n        res = requests.put(api_url, headers=headers, json=put, timeout=30)\n        if res.status_code not in {200, 201}:\n            logger.error("[DEFERRED SAVE] GitHub HTTP %s %s", res.status_code, res.text[:300]); return False\n        return True\n    except Exception as exc:\n        logger.error("[DEFERRED SAVE] GitHub exception: %s", exc); return False\n''',
    "enqueue_deferred_candidates": '''def enqueue_deferred_candidates(candidates: list[dict]) -> int:\n    if not candidates: return 0\n    new_rows, final, evicted, ranked = _merge_rank_deferred_candidates_impl(\n        load_deferred_deep_dive_queue(), candidates, serialize_candidate=_deferred_serializable,\n        max_queue=DEFERRED_DEEP_DIVE_MAX_QUEUE,\n    )\n    if save_deferred_deep_dive_queue(final):\n        if evicted:\n            _fallback_deferred_rows_to_notion(evicted, "Deferred queue capacity overflow")\n        logger.info("[DEFERRED SAVED] queued=%s total=%s evicted_to_pending=%s", len(new_rows), len(final), len(evicted)); return len(new_rows)\n    _fallback_deferred_rows_to_notion(ranked, "Deferred queue persistence failed")\n    return 0\n''',
    "pop_deferred_candidates": '''def pop_deferred_candidates(limit: int) -> tuple[list[dict], list[dict]]:\n    return _pop_deferred_candidates_impl(load_deferred_deep_dive_queue(), limit)\n''',
}

spans = []
for name, replacement in replacements.items():
    node = nodes.get(name)
    if node is None:
        raise RuntimeError(f"Run242 target missing: {name}")
    spans.append((node.lineno - 1, node.end_lineno, replacement + "\n", name))
spans.sort()
for left, right in zip(spans, spans[1:]):
    if left[1] > right[0]:
        raise RuntimeError(f"Run242 overlapping targets: {left[3]} / {right[3]}")
for start, end, replacement, _name in reversed(spans):
    lines[start:end] = [replacement]
source = "".join(lines)

import_block = '''\nfrom notion_payloads import (\n    safe_chunk_text as _safe_chunk_text_impl, notion_date_property as _notion_date_property_impl,\n    build_notion_properties as _build_notion_properties_impl, build_notion_manuscript_children as _build_notion_manuscript_children_impl,\n    build_notion_payload as _build_notion_payload_impl, build_metadata_notion_properties as _build_metadata_notion_properties_impl,\n)\nfrom source_document_parsing import (\n    github_repo_name_from_url as _github_repo_name_from_url_impl, github_repo_identity as _github_repo_identity_impl,\n    is_github_global_navigation_url as _is_github_global_navigation_url_impl, extract_markdown_evidence_links as _extract_markdown_evidence_links_impl,\n    effective_evidence_source as _effective_evidence_source_impl, is_redundant_arxiv_doi as _is_redundant_arxiv_doi_impl,\n    ReadableHTMLTextParser as _ReadableHTMLTextParserImpl, is_low_value_arxiv_url as _is_low_value_arxiv_url_impl,\n    ResearchLinkParser as _ResearchLinkParserImpl, compress_evidence as _compress_evidence_impl,\n    build_evidence_metadata as _build_evidence_metadata_impl,\n)\nfrom deferred_queue_policy import (\n    deferred_ttl_days as _deferred_ttl_days_impl, deferred_key as _deferred_key_impl,\n    deferred_serializable as _deferred_serializable_impl, valid_deferred_items as _valid_deferred_items_impl,\n    build_deferred_payload as _build_deferred_payload_impl, merge_rank_deferred_candidates as _merge_rank_deferred_candidates_impl,\n    pop_deferred_candidates as _pop_deferred_candidates_impl,\n)\n'''
anchor = "\n# ==========================================\n# ログ設定\n# ==========================================\n"
if source.count(anchor) != 1:
    raise RuntimeError(f"Run242 import anchor count={source.count(anchor)}")
source = source.replace(anchor, import_block + anchor, 1)
ast.parse(source)

print(f"Run242 migration preview: 11497 -> {len(source.splitlines())} lines")
if args.write:
    path.write_text(source)
    print("Run242 migration write: PASS")
else:
    print("Run242 migration dry-run: PASS")
