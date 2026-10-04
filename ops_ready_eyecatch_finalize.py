#!/usr/bin/env python3
"""Bounded ops-only eyecatch finalizer for the P0-B live-proof candidate.

This wrapper changes only the provider fallback sequence and model-compatible
thinking configuration used by the existing semantic eyecatch layout layer.
All publication, canonical-body, title, asset, Notion, note-mutation, and
public-release guards remain owned by the existing production implementation.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

import ready_eyecatch_finalize as ready_finalize
import run180_eyecatch_semantic_layout as semantic_layout

BOUNDED_LAYOUT_MODELS = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
)


def _bounded_request_layout_plan(
    pipeline_module: Any, source_title: str, subheadline: str
) -> dict[str, Any] | None:
    if bool(getattr(pipeline_module, "SYNTHETIC_REGRESSION_MODE", False)):
        return None

    prompt = semantic_layout._layout_prompt(source_title, subheadline)
    logger = getattr(pipeline_module, "logger", None)
    timeout_guard = getattr(pipeline_module, "_gemini_call_timeout", None)
    if not callable(timeout_guard):
        if logger is not None:
            logger.warning(
                "[P0B OPS EYECATCH FAIL-CLOSED] timeout watchdog unavailable; "
                "skip provider layout"
            )
        return None

    for model_name in BOUNDED_LAYOUT_MODELS:
        try:
            config: dict[str, Any] = {
                "response_mime_type": "application/json",
                "response_json_schema": semantic_layout._LAYOUT_RESPONSE_SCHEMA,
                "max_output_tokens": semantic_layout.EYECATCH_LAYOUT_MAX_OUTPUT_TOKENS,
            }
            # 3.6/3.5 accept MINIMAL. 3.7/3.8 explicitly reject MINIMAL,
            # so leave their thinking level unspecified and let the provider use
            # its supported default. No quality/evidence/layout guard is relaxed.
            if model_name in {"gemini-3.6-flash", "gemini-3.5-flash"}:
                config["thinking_config"] = {"thinking_level": "minimal"}

            with timeout_guard(semantic_layout.EYECATCH_LAYOUT_CALL_TIMEOUT_SECONDS):
                response = pipeline_module._generate_via_chat(
                    model_name,
                    prompt,
                    config=config,
                    request_kind="eyecatch_layout",
                    reserve=0,
                    request_context="p0b_ops_public_eyecatch_semantic_title_layout",
                    count_as_deep_dive=False,
                    request_origin="new",
                )
            plan = semantic_layout._parse_plan_response(response)
            if semantic_layout._validate_layout_plan(source_title, subheadline, plan) is not None:
                return plan
            if logger is not None:
                logger.warning(
                    "[P0B OPS EYECATCH LAYOUT RETRY] model=%s invalid headline or geometry",
                    model_name,
                )
        except Exception as exc:
            if logger is not None:
                logger.warning(
                    "[P0B OPS EYECATCH PROVIDER FALLBACK] model=%s error=%s",
                    model_name,
                    exc,
                )
    return None


def finalize(sync_id: str) -> dict:
    # Keep the production renderer and all existing validators intact. Only the
    # bounded provider request function is replaced for this isolated ops branch.
    semantic_layout.EYECATCH_LAYOUT_MODELS = BOUNDED_LAYOUT_MODELS
    semantic_layout.EYECATCH_LAYOUT_MODEL = BOUNDED_LAYOUT_MODELS[0]
    semantic_layout._request_layout_plan = _bounded_request_layout_plan
    result = ready_finalize.finalize_ready_eyecatch(sync_id)
    result["ops_provider_route"] = list(BOUNDED_LAYOUT_MODELS)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.sync_id), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
