"""Run172 production reliability guardrails.

This module fixes failure modes observed in Daily Run #106 without weakening any
Fact / Evidence / Publication gate and without adding Gemini request lanes.

The policy is deliberately installed as a small bridge layer so the production
pipeline can be rolled back independently from the accumulated core logic.
"""
from __future__ import annotations

import hashlib
import re
import time
import unicodedata
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse

_INSTALLED_ATTR = "_run172_production_reliability_installed"
_GITHUB_ISSUE_RE = re.compile(r"^/([^/]+)/([^/]+)/issues/(\d+)(?:/|$)", re.I)

# These are intentionally narrow.  A normal editorial number such as "3 ideas"
# must not become a hard evidence blocker.  Material quantities, money,
# multipliers and percentages are source-bound claims.
_MATERIAL_NUMBER_PATTERNS = (
    re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(?:x|×|倍)(?!\w)", re.I),
    re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*%(?!\w)"),
    re.compile(r"(?:[$¥￥€£]\s*\d+(?:[.,]\d+)*|\d+(?:[.,]\d+)*\s*(?:USD|JPY|EUR|GBP|ドル|円))", re.I),
)
_EVENT_ALIASES = {
    "bug": ("bug", "defect", "issue", "error", "不具合", "バグ"),
    "vulnerability": ("vulnerability", "cve-", "exploit", "security flaw", "脆弱性"),
    "exploit": ("exploit", "rce", "remote code execution", "攻撃", "悪用"),
    "charge": ("charge", "billing", "cost", "price", "課金", "請求"),
    "outage": ("outage", "downtime", "service disruption", "障害", "停止"),
    "leak": ("leak", "breach", "exposure", "漏えい", "流出"),
}
_ANCHOR_STOP = {
    "show", "hn", "the", "a", "an", "on", "in", "for", "from", "with", "and", "or",
    "bug", "issue", "error", "causing", "causes", "charge", "charges", "billing", "security",
}


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).lower().replace("×", "x")
    return re.sub(r"\s+", " ", value).strip()


def safe_notion_file_name(base: str, suffix: str = ".png", max_chars: int = 96) -> str:
    """Return a deterministic Notion file display name safely below its 100-char cap."""
    max_chars = min(100, max(24, int(max_chars)))
    clean = unicodedata.normalize("NFKC", str(base or "eyecatch")).replace("\r", " ").replace("\n", " ").strip()
    clean = re.sub(r"\s+", " ", clean) or "eyecatch"
    full = clean if clean.lower().endswith(suffix.lower()) else clean + suffix
    if len(full) <= max_chars:
        return full
    stem = full[:-len(suffix)] if suffix and full.lower().endswith(suffix.lower()) else full
    digest = hashlib.sha256(full.encode("utf-8")).hexdigest()[:10]
    trailer = f"__{digest}{suffix}"
    budget = max(1, max_chars - len(trailer))
    return stem[:budget].rstrip(" ._-/:：") + trailer


def _github_issue_identity(url: str) -> tuple[str, str, int] | None:
    try:
        parsed = urlparse(str(url or ""))
    except Exception:
        return None
    if parsed.hostname not in {"github.com", "www.github.com"}:
        return None
    match = _GITHUB_ISSUE_RE.match(parsed.path or "")
    if not match:
        return None
    return match.group(1), match.group(2), int(match.group(3))


def _fetch_github_issue_report(pipeline_module: Any, url: str) -> str:
    """Fetch the exact issue report used as discovery evidence, with no Gemini call."""
    identity = _github_issue_identity(url)
    if not identity:
        return ""
    owner, repo, number = identity
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = str(getattr(pipeline_module, "GH_PAT", "") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    try:
        response = pipeline_module.requests.get(api_url, headers=headers, timeout=20)
        if response.status_code != 200:
            pipeline_module.logger.warning("[GITHUB ISSUE EVIDENCE] fetch failed status=%s url=%s", response.status_code, url)
            return ""
        data = response.json() or {}
    except Exception as exc:
        pipeline_module.logger.warning("[GITHUB ISSUE EVIDENCE] fetch error url=%s error=%s", url, exc)
        return ""

    title = str(data.get("title") or "").strip()
    body = str(data.get("body") or "").strip()
    state = str(data.get("state") or "").strip()
    author = str((data.get("user") or {}).get("login") or "").strip()
    if not title and not body:
        return ""
    # Important authority boundary: an issue proves that a report exists.  It is
    # not by itself proof that the maintainer/vendor confirmed the diagnosis.
    return (
        "[GITHUB ISSUE REPORT — REPORT EVIDENCE, NOT MAINTAINER CONFIRMATION]\n"
        f"Repository: {owner}/{repo}\nIssue: #{number}\nState: {state}\nReporter: {author}\n"
        f"Title: {title}\nBody:\n{body[:30000]}"
    ).strip()


def _append_context(info: dict, key: str, addition: str, limit: int) -> None:
    old = str(info.get(key) or "").strip()
    addition = str(addition or "").strip()
    if not addition:
        return
    merged = (old + "\n\n" + addition).strip() if old else addition
    info[key] = merged[:max(1000, int(limit))]


def _material_claim_gaps(title: str, context: str) -> list[str]:
    """Find only high-confidence title claims that are absent from retrieved evidence."""
    title_n = _norm(title)
    context_n = _norm(context)
    if not title_n or not context_n:
        return []
    gaps: list[str] = []

    # Material numeric claims.  Exact material numbers must exist somewhere in
    # retrieved evidence before the model may build an article around them.
    for pattern in _MATERIAL_NUMBER_PATTERNS:
        for match in pattern.finditer(title_n):
            token = match.group(0).strip()
            number = match.group(1) if match.lastindex else re.sub(r"\D", "", token)
            if "x" in token or "倍" in token:
                candidates = (f"{number}x", f"{number} x", f"{number}倍")
                if not any(x in context_n for x in candidates):
                    gaps.append(f"material_numeric:{token}")
            elif "%" in token:
                if f"{number}%" not in context_n and f"{number} %" not in context_n:
                    gaps.append(f"material_numeric:{token}")
            else:
                compact = re.sub(r"\s+", "", token)
                if compact not in re.sub(r"\s+", "", context_n):
                    gaps.append(f"material_money:{token}")

    matched_event_groups: list[tuple[str, tuple[str, ...]]] = []
    for label, aliases in _EVENT_ALIASES.items():
        if any(alias in title_n for alias in aliases):
            matched_event_groups.append((label, aliases))
            if not any(alias in context_n for alias in aliases):
                gaps.append(f"event_claim:{label}")

    # Named-anchor coverage is required only for event/risk claims.  This avoids
    # turning normal editorial titles or research-paper capitalization into a
    # brittle token-matching gate.
    if matched_event_groups:
        raw_anchors = re.findall(r"\b(?:[A-Z]{2,}|[A-Z][A-Za-z0-9_.-]{2,})\b", str(title or ""))
        anchors = []
        for token in raw_anchors:
            norm = _norm(token)
            if norm in _ANCHOR_STOP or norm.isdigit() or norm in anchors:
                continue
            anchors.append(norm)
        if len(anchors) >= 2:
            present = [anchor for anchor in anchors if anchor in context_n]
            if len(present) < 2:
                missing = [anchor for anchor in anchors if anchor not in context_n][:3]
                gaps.append("named_anchor:" + ",".join(missing))

    return list(dict.fromkeys(gaps))


def _extract_management_lines(raw_text: str) -> dict[str, str]:
    """Recover exact management values when Gemini changes only bullet punctuation."""
    text = str(raw_text or "")
    marker = "=== ARTICLE ==="
    if marker in text:
        text = text.split(marker, 1)[0]
    labels = {
        "Source Summary": "source_summary_text",
        "What": "what_text",
        "Why Important": "why_important_text",
        "Decision": "decision_text",
        "Decision Reason": "decision_reason_text",
        "Action": "action_text",
        "Article Value": "article_value_text",
    }
    out: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*(?:[-*•・]\s*)?([^:：\n]{2,40})\s*[:：]\s*(.+?)\s*$", line)
        if not match:
            continue
        label = match.group(1).strip()
        value = match.group(2).strip()
        key = labels.get(label)
        if key and value:
            out[key] = value
    return out


def _article_similarity(before: dict, after: dict) -> float:
    a = re.sub(r"\s+", " ", str((before or {}).get("note_draft") or "")).strip()
    b = re.sub(r"\s+", " ", str((after or {}).get("note_draft") or "")).strip()
    if not a or not b:
        return 1.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def install(pipeline_module: Any) -> Any:
    """Install all Run172 reliability fixes idempotently."""
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_build_notion_properties = pipeline_module.build_notion_properties
    original_prepare_source_context = pipeline_module.prepare_source_context
    original_assess_evidence = pipeline_module.assess_evidence_sufficiency
    original_parse = pipeline_module._parse_gemini_response
    original_build_prompt = pipeline_module.build_decision_prompt
    original_build_retry = pipeline_module.build_dynamic_retry_instruction
    original_degraded = pipeline_module.human_appeal_materially_degraded
    original_publication_probability = pipeline_module.publication_probability_score

    def build_notion_properties_safe(*args, **kwargs):
        props = original_build_notion_properties(*args, **kwargs)
        key = getattr(pipeline_module, "PROP_EYECATCH", "アイキャッチ")
        block = (props or {}).get(key) or {}
        for item in block.get("files") or []:
            name = str(item.get("name") or "eyecatch.png")
            item["name"] = safe_notion_file_name(name[:-4] if name.lower().endswith(".png") else name)
        return props

    def prepare_source_context_exact_issue(repo: dict):
        info = original_prepare_source_context(repo)
        info["_run172_candidate_title"] = str(repo.get("nameWithOwner") or repo.get("title") or "")
        primary = str(repo.get("primaryUrl") or repo.get("url") or info.get("primary_url") or "")
        info["_run172_candidate_primary_url"] = primary
        report = _fetch_github_issue_report(pipeline_module, primary)
        if report:
            limit = int(getattr(pipeline_module, "VERIFICATION_CONTEXT_MAX_CHARS", 180000))
            _append_context(info, "context", report, limit)
            _append_context(info, "verification_context", report, limit)
            info["primary_url"] = primary
            info["primary_source_resolved"] = True
            info["primary_fetch_failed"] = False
            info["run172_issue_report_evidence"] = True
            checked = info.get("checked_urls")
            if isinstance(checked, set):
                checked.add(primary)
            deep_urls = info.setdefault("deep_source_urls", [])
            if isinstance(deep_urls, list) and primary not in deep_urls:
                deep_urls.append(primary)
            pipeline_module.logger.info("[GITHUB ISSUE EVIDENCE] exact report context resolved: %s", primary)
        return info

    def assess_evidence_with_core_claim(info: dict):
        result = dict(original_assess_evidence(info) or {})
        title = str(info.get("_run172_candidate_title") or "")
        context = "\n".join([
            str(info.get("verification_context") or ""),
            str(info.get("context") or ""),
        ])
        gaps = _material_claim_gaps(title, context)
        if not gaps:
            result["core_claim_gaps"] = []
            return result

        missing = list(result.get("blocking_missing") or [])
        if "core_claim_coverage" not in missing:
            missing.append("core_claim_coverage")
        result["blocking_missing"] = missing
        result["core_claim_gaps"] = gaps
        result["decision_scope_safe"] = False
        has_supplement = bool(info.get("supplement_candidates")) and not bool(info.get("evidence_supplement_attempted"))
        if has_supplement:
            result["state"] = getattr(pipeline_module, "EVIDENCE_SUPPLEMENT_REQUIRED", "SUPPLEMENT_REQUIRED")
        else:
            result["state"] = getattr(pipeline_module, "EVIDENCE_INSUFFICIENT", "INSUFFICIENT")
        pipeline_module.logger.warning("[CORE CLAIM EVIDENCE GAP] title=%s gaps=%s", title, gaps)
        return result

    def parse_with_bullet_recovery(full_text: str):
        parsed = original_parse(full_text)
        recovered = _extract_management_lines(full_text)
        for key, value in recovered.items():
            if not str(parsed.get(key) or "").strip():
                if key == "decision_text" and hasattr(pipeline_module, "_normalize_decision"):
                    value = pipeline_module._normalize_decision(value) or value
                parsed[key] = value
        return parsed

    def build_prompt_with_report_boundary(*args, **kwargs):
        prompt = original_build_prompt(*args, **kwargs)
        if "[GITHUB ISSUE REPORT — REPORT EVIDENCE, NOT MAINTAINER CONFIRMATION]" in prompt:
            prompt += (
                "\n\n【GitHub Issueの権威境界】\n"
                "Issue本文は『その報告が存在する』ことの一次資料です。maintainer/vendorが本文で明示的に確認していない限り、"
                "『バグが確認された』『原因が確定した』『必ず発生する』とは書かず、『Issueで報告された』『投稿者は〜と報告した』"
                "の強度に限定してください。数値・料金・影響範囲もIssue本文にある条件を落とさないでください。\n"
            )
        return prompt

    def build_retry_with_patch_contract(reason_rows: list[dict]):
        instruction, sections = original_build_retry(reason_rows)
        instruction = instruction.rstrip() + (
            "\n【Run172 Patch Retry Contract】\n"
            "・前回稿は全面再生成の素材ではなく正本です。指摘対象の文・管理項目だけを置換し、それ以外の段落・見出し・Evidence・"
            "固有名詞・数値・Decisionは可能な限り同じ文面で保持してください。\n"
            "・指摘にTitleが含まれない限りタイトルを変更しない。Decision/Score/Actionが指摘対象でない限り管理値を変更しない。\n"
            "・修正のために新しい数値・固有名詞・保証表現・外部知識を追加しない。削除で意味が壊れる場合だけ、同じEvidence範囲の"
            "弱い表現へ局所置換してください。\n"
        )
        return instruction, sections

    def degraded_with_broad_rewrite_guard(before: dict, after: dict) -> bool:
        if original_degraded(before, after):
            return True
        before_article = str((before or {}).get("note_draft") or "")
        after_article = str((after or {}).get("note_draft") or "")
        # A local repair should retain most of a substantial manuscript.  This is
        # a review guard, not an automatic hard fail; it prevents a silent broad
        # rewrite from being treated as a successful patch.
        if min(len(before_article), len(after_article)) >= 1200:
            similarity = _article_similarity(before, after)
            if similarity < 0.42:
                pipeline_module.logger.warning("[RETRY BROAD REWRITE GUARD] similarity=%.3f", similarity)
                return True
        return False

    def publication_probability_with_evidence_surface(item: dict) -> int:
        base = int(original_publication_probability(item))
        primary = str(item.get("primaryUrl") or item.get("url") or "")
        title = str(item.get("nameWithOwner") or item.get("title") or "")
        source = str(item.get("source") or "")
        issue = _github_issue_identity(primary)
        if issue:
            base += 12
        title_n = _norm(title)
        has_material = any(pattern.search(title_n) for pattern in _MATERIAL_NUMBER_PATTERNS)
        has_event = any(any(alias in title_n for alias in aliases) for aliases in _EVENT_ALIASES.values())
        if source == "HackerNews" and has_material and has_event and not issue:
            host = (urlparse(primary).hostname or "").lower()
            # Numeric incident claims need a claim-bearing surface. Generic docs
            # are less likely to support the title than an issue/report itself.
            if host and host not in {"github.com", "www.github.com", "arxiv.org", "www.arxiv.org"}:
                base -= 12
        return max(0, min(100, base))

    # Preserve the existing bounded model-pool behavior, but do not spend a
    # second request on the same model after HTTP 503. RPM/TPM still get one
    # same-model transport retry. The logical request kind is preserved so a
    # quality_retry is not mislabeled as deep_dive_retry.
    def call_model_pool_fail_fast_503(prompt: str, config: dict | None, kind: str, reserve: int,
                                      pool: list[str], deep_dive: bool = False, request_context: str = "",
                                      request_origin: str = "new"):
        last_error: Exception | None = None
        for model_name in pool:
            if model_name in pipeline_module.SESSION_EXHAUSTED_MODELS or model_name in pipeline_module.SESSION_UNAVAILABLE_MODELS:
                continue
            for attempt in range(2):
                try:
                    if deep_dive:
                        time.sleep(max(0, pipeline_module.GEMINI_DEEP_DIVE_CALL_PACING_SECONDS))
                        with pipeline_module._gemini_call_timeout(pipeline_module.GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS):
                            response = pipeline_module._generate_via_chat(
                                model_name, prompt, config=config, request_kind=kind, reserve=reserve,
                                request_context=request_context, count_as_deep_dive=True,
                                request_origin=request_origin,
                            )
                    else:
                        with pipeline_module._gemini_call_timeout(pipeline_module.GEMINI_SCREENING_CALL_TIMEOUT_SECONDS):
                            response = pipeline_module._generate_via_chat(
                                model_name, prompt, config=config, request_kind=kind, reserve=reserve,
                                request_context=request_context,
                            )
                    return response, model_name
                except pipeline_module.APIError as exc:
                    last_error = exc
                    code = getattr(exc, "code", None)
                    quota_type = pipeline_module.classify_gemini_quota_error(exc) if code == 429 else ""
                    if code == 429 and quota_type in {"RPD", "DAILY_TOKEN"}:
                        pipeline_module._mark_model_exhausted(model_name, quota_type)
                        break
                    if code == 503:
                        pipeline_module._mark_model_unavailable(model_name, "503")
                        break
                    if code == 404:
                        pipeline_module._mark_model_unavailable(model_name, "404")
                        break
                    if code == 429 and quota_type in {"RPM", "TPM"} and attempt == 0:
                        time.sleep(pipeline_module._extract_retry_delay(exc, 15))
                        continue
                    break
                except (pipeline_module.GeminiBudgetExceededError, pipeline_module.GeminiCallTimeoutError) as exc:
                    last_error = exc
                    if isinstance(exc, pipeline_module.GeminiCallTimeoutError):
                        pipeline_module.logger.warning(
                            "[GEMINI TRANSIENT TIMEOUT] model=%s kind=%s error=%s; falling back",
                            model_name, kind, exc,
                        )
                    break
                except Exception as exc:
                    if pipeline_module._is_gemini_transport_timeout(exc):
                        last_error = exc
                        pipeline_module.logger.warning(
                            "[GEMINI TRANSIENT TIMEOUT] model=%s kind=%s error=%s; falling back",
                            model_name, kind, exc,
                        )
                        break
                    raise
        raise pipeline_module.NoAvailableModelError("利用可能なGeminiモデルがありません") from last_error

    def call_product_review_pool_fail_fast_503(prompt: str, request_context: str, request_kind_base: str = "product_review"):
        last_error: Exception | None = None
        structured_repair = request_kind_base == "product_review_retry"
        thinking_level = "low" if structured_repair else "medium"
        max_output_tokens = 5000 if structured_repair else 8000
        for model_name in pipeline_module.DEEP_DIVE_MODEL_POOL:
            if model_name in pipeline_module.SESSION_EXHAUSTED_MODELS or model_name in pipeline_module.SESSION_UNAVAILABLE_MODELS:
                continue
            for attempt in range(2):
                if not pipeline_module.PRODUCT_REVIEW_REQUEST_BUDGET.can_request():
                    raise pipeline_module.ProductReviewBudgetExceededError(pipeline_module.PRODUCT_REVIEW_REQUEST_BUDGET.summary())
                try:
                    time.sleep(max(0, pipeline_module.GEMINI_DEEP_DIVE_CALL_PACING_SECONDS))
                    return pipeline_module._generate_via_chat(
                        model_name, prompt,
                        config={
                            "response_mime_type": "application/json",
                            "response_json_schema": pipeline_module._PRODUCT_REVIEW_RESPONSE_SCHEMA,
                            "thinking_config": {"thinking_level": thinking_level},
                            "max_output_tokens": max_output_tokens,
                        },
                        request_kind=request_kind_base,
                        request_context=request_context,
                        count_as_deep_dive=False,
                        request_origin="product_review",
                    ), model_name
                except pipeline_module.APIError as exc:
                    last_error = exc
                    code = getattr(exc, "code", None)
                    quota_type = pipeline_module.classify_gemini_quota_error(exc) if code == 429 else ""
                    if code == 429 and quota_type in {"RPD", "DAILY_TOKEN"}:
                        pipeline_module._mark_model_exhausted(model_name, quota_type)
                        break
                    if code == 503:
                        pipeline_module._mark_model_unavailable(model_name, "503")
                        break
                    if code == 404:
                        pipeline_module._mark_model_unavailable(model_name, "404")
                        break
                    if code == 429 and quota_type in {"RPM", "TPM"} and attempt == 0:
                        time.sleep(pipeline_module._extract_retry_delay(exc, 15))
                        continue
                    break
                except (pipeline_module.GeminiBudgetExceededError, pipeline_module.GeminiCallTimeoutError) as exc:
                    last_error = exc
                    break
        raise pipeline_module.NoAvailableModelError("Product Reviewに利用可能なGeminiモデルがありません") from last_error

    pipeline_module.build_notion_properties = build_notion_properties_safe
    pipeline_module.prepare_source_context = prepare_source_context_exact_issue
    pipeline_module.assess_evidence_sufficiency = assess_evidence_with_core_claim
    pipeline_module._parse_gemini_response = parse_with_bullet_recovery
    pipeline_module.build_decision_prompt = build_prompt_with_report_boundary
    pipeline_module.build_dynamic_retry_instruction = build_retry_with_patch_contract
    pipeline_module.human_appeal_materially_degraded = degraded_with_broad_rewrite_guard
    pipeline_module.publication_probability_score = publication_probability_with_evidence_surface
    pipeline_module._call_model_pool = call_model_pool_fail_fast_503
    pipeline_module._call_product_review_pool = call_product_review_pool_fail_fast_503
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
