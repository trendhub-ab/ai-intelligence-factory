"""Pure-baseline P5 Writer provider through the existing guarded Gemini budget.

Only for article_revalidation+v3_p5+original, never Production "new".
No AIIF Editor Persona or forced generation config is sent. The caller still
retains canonical first-pass management data and every downstream publication
gate; it does not authorize new note/Notion writes.
"""
from __future__ import annotations

import os
from typing import Any

from .v3_p5_call_contract import pure_p5_writer_config
from .v3_p5_rate_contract import P5_MODELS, ordered_p5_pool

ALLOWED_NONPREVIEW_MODELS = frozenset(P5_MODELS)


class P5PureProviderError(RuntimeError):
    """Refuse baseline-imitation calls outside documented isolated proof."""


def call_p5_pure_writer(
    p: Any,
    prompt: str,
    repo: dict,
    source_info: dict,
    *,
    request_kind: str = "deep_dive",
    request_context: str = "",
    request_origin: str = "new",
) -> tuple[Any, dict]:
    """Generate unmodified authorial P5 with Production *budget*, not persona.

    Reuse pipeline._call_model_pool so pacing, per-request accounting, model
    health, 503 fallback and run-level quotas remain unchanged. Filter pool
    BEFORE any provider requests; Preview/Lite and unknown models are excluded.
    This is not a byte-for-byte reproduction of the old SDK transport
    (old Phase0 used models.generate_content; Production uses chats).
    """
    boundary = str(
        getattr(p, "AIIF_P5_WRITER_BOUNDARY", None)
        or os.getenv("AIIF_P5_WRITER_BOUNDARY", "managed")
    )
    config = pure_p5_writer_config(
        {}, editorial_style=str(getattr(p, "AIIF_EDITORIAL_STYLE", "classic")),
        writer_boundary=boundary,
        request_origin=request_origin,
        request_kind=request_kind,
        nonpersisting_new_validation=(
            getattr(p, "_P5_NONPERSISTING_VALIDATION_ACTIVE", False) is True
        ),
    )
    if config != {}:
        raise P5PureProviderError("Pure baseline config must be empty")
    result = source_info.get("evidence_result") or {}
    if not (source_info.get("evidence_sufficient") is True
            or result.get("state") == "SUFFICIENT"):
        raise P5PureProviderError("Unverified source-native evidence")
    native = str(
        source_info.get("verification_context")
        or source_info.get("context") or ""
    )
    if len(native.strip()) < 80 or not str(
        source_info.get("primary_url") or repo.get("url") or ""
    ).startswith(("https://", "http://")):
        raise P5PureProviderError("Insufficient verified text or primary URL")
    if not all(token in prompt for token in (
        "1. Writer Reaction", "2. Editorial Discovery",
        "3. Cognitive Shift", "4. Persona Article Generation",
        "5. Fact-Safe Review",
    )):
        raise P5PureProviderError("Pure provider only accepts the canonical five-stage P5 prompt")
    guarded_pool = ordered_p5_pool(getattr(p, "DEEP_DIVE_MODEL_POOL", ()))
    if not guarded_pool:
        raise P5PureProviderError("No allowlisted 3.8/3.6 nonpreview Writer model")
    pool = getattr(p, "_call_model_pool", None)
    if not callable(pool):
        raise P5PureProviderError("Missing canonical budgeted Gemini model pool")
    response, model = pool(
        prompt, config, "deep_dive", 0, guarded_pool,
        deep_dive=True, request_context=request_context,
        request_origin=request_origin,
    )
    if model not in ALLOWED_NONPREVIEW_MODELS:
        raise P5PureProviderError("Unexpected model returned by budgeted pool")
    p.SELECTED_DEEP_DIVE_MODEL = model
    usage = getattr(p, "_extract_usage_metadata", None)
    if callable(usage):
        usage(response)
    metadata = getattr(p, "extract_grounding_metadata", None)
    if not callable(metadata):
        raise P5PureProviderError("Missing canonical grounding metadata parser")
    grounded = metadata(
        response, str(source_info.get("primary_url") or repo.get("url") or ""),
        True, False, False,
    )
    if grounded.get("grounding_status") == getattr(p, "GROUNDING_FAILED", "Failed"):
        raise P5PureProviderError("Source-native grounding not accepted")
    return response, grounded
