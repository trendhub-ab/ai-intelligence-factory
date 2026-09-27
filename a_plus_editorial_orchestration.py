"""A+ runtime orchestration: Local Skills skeleton, Gemini prose, provider-free retry fallback.

This layer is deliberately external to pipeline.py so the production core remains small.
It changes no Gate thresholds, adds no mandatory provider call, and never creates a
Decision when the initial Deep Dive failed before structured management data existed.
"""
from __future__ import annotations

from functools import wraps
from types import SimpleNamespace
from typing import Any

from local_skills.a_plus import (
    build_prewrite_contract,
    can_use_local_fallback,
    render_provider_compatible_fallback,
)


_MARKER = "_a_plus_editorial_orchestration_installed"
_OUTPUT_MARKER = "
【Output Contract｜完成稿のみ】"


def _provider_unavailable(exc: Exception) -> bool:
    name = exc.__class__.__name__
    if name in {
        "GeminiCallTimeoutError",
        "NoAvailableModelError",
        "GeminiBudgetExceededError",
        "DeepDiveRunBudgetExceededError",
        "PendingRetryBudgetExceededError",
    }:
        return True
    return getattr(exc, "code", None) in {429, 503}


def _fallback_grounding(source_info: dict) -> dict[str, Any]:
    primary = str(source_info.get("primary_url") or "").strip()
    urls: list[str] = []
    for value in list(source_info.get("evidence_urls") or []):
        url = str(value or "").strip()
        if url and url not in urls:
            urls.append(url)
    if primary and primary not in urls:
        urls.append(primary)
    return {
        "grounding_status": str(source_info.get("method") or "Source Native"),
        "evidence_urls": urls,
        "a_plus_local_fallback": True,
    }


def install(pipeline_module):
    p = pipeline_module
    if bool(getattr(p, _MARKER, False)):
        return p

    original_prompt = p.build_decision_prompt
    original_parse = p._parse_gemini_response
    original_retry = p.should_attempt_dynamic_retry
    original_call = p.call_gemini_grounded_deep_dive
    original_generate = p.generate_intelligence_report

    state: dict[str, Any] = {
        "last_parsed": None,
        "last_retry_rows": [],
        "last_evidence_result": {},
        "force_local_fallback": False,
    }

    @wraps(original_generate)
    def generate_intelligence_report_a_plus(*args, **kwargs):
        state["last_parsed"] = None
        state["last_retry_rows"] = []
        state["last_evidence_result"] = {}
        state["force_local_fallback"] = False
        return original_generate(*args, **kwargs)

    @wraps(original_prompt)
    def build_decision_prompt_a_plus(*args, **kwargs):
        prompt = str(original_prompt(*args, **kwargs) or "")
        evidence_result = kwargs.get("evidence_result") or {}
        evidence_metadata = kwargs.get("evidence_metadata") or {}
        contract = build_prewrite_contract(evidence_result, evidence_metadata)
        block = "
【A+ Local Skills Pre-Write Contract】
" + contract + "
"
        if _OUTPUT_MARKER in prompt:
            return prompt.replace(_OUTPUT_MARKER, block + _OUTPUT_MARKER, 1)
        return prompt.rstrip() + "
" + block

    @wraps(original_parse)
    def parse_gemini_response_a_plus(*args, **kwargs):
        parsed = original_parse(*args, **kwargs)
        if isinstance(parsed, dict):
            state["last_parsed"] = dict(parsed)
        return parsed

    @wraps(original_retry)
    def should_attempt_dynamic_retry_a_plus(reason_rows, evidence_result, *args, **kwargs):
        rows = list(reason_rows or [])
        evidence = dict(evidence_result or {})
        state["last_retry_rows"] = rows
        state["last_evidence_result"] = evidence
        state["force_local_fallback"] = False

        allowed, reason = original_retry(reason_rows, evidence_result, *args, **kwargs)
        if allowed:
            return allowed, reason

        seed = state.get("last_parsed")
        if can_use_local_fallback(seed, rows, evidence):
            state["force_local_fallback"] = True
            return True, "a_plus_local_fallback"
        return allowed, reason

    @wraps(original_call)
    def call_gemini_grounded_deep_dive_a_plus(
        prompt: str,
        repo: dict,
        source_info: dict,
        request_kind: str = "deep_dive",
        request_context: str = "",
        request_origin: str = "new",
    ):
        def local_result(cause: str):
            seed = state.get("last_parsed")
            rows = list(state.get("last_retry_rows") or [])
            evidence = dict(state.get("last_evidence_result") or source_info.get("evidence_result") or {})
            if request_kind != "quality_retry" or not can_use_local_fallback(seed, rows, evidence):
                return None
            response_text, meta = render_provider_compatible_fallback(
                p,
                repo,
                seed,
                source_info=source_info,
            )
            logger = getattr(p, "logger", None)
            if logger:
                logger.warning(
                    "[A+ LOCAL FALLBACK] %s cause=%s writer=%s provider_article_reused=%s",
                    request_context,
                    cause,
                    meta.get("writer_blob_sha"),
                    meta.get("provider_article_surface_reused"),
                )
            return SimpleNamespace(text=response_text, candidates=[]), _fallback_grounding(source_info)

        if request_kind == "quality_retry" and bool(state.get("force_local_fallback")):
            result = local_result("retry_policy_unavailable")
            if result is not None:
                state["force_local_fallback"] = False
                return result

        try:
            return original_call(
                prompt,
                repo,
                source_info,
                request_kind=request_kind,
                request_context=request_context,
                request_origin=request_origin,
            )
        except Exception as exc:
            if request_kind == "quality_retry" and _provider_unavailable(exc):
                result = local_result(f"provider_unavailable:{exc.__class__.__name__}")
                if result is not None:
                    state["force_local_fallback"] = False
                    return result
            raise

    p.generate_intelligence_report = generate_intelligence_report_a_plus
    p.build_decision_prompt = build_decision_prompt_a_plus
    p._parse_gemini_response = parse_gemini_response_a_plus
    p.should_attempt_dynamic_retry = should_attempt_dynamic_retry_a_plus
    p.call_gemini_grounded_deep_dive = call_gemini_grounded_deep_dive_a_plus
    setattr(p, _MARKER, True)
    setattr(p, "A_PLUS_EDITORIAL_ORCHESTRATION", True)
    return p
