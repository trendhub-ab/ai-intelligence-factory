"""Publication-integrity overlay for persisted Ready manuscripts.

Run194 introduced fail-closed Ready provenance.  Run195 hardens that contract against two
cross-version failure modes found by repository-wide falsification:
1) manual version strings can be forgotten when article/eyecatch code changes;
2) within one policy version, a regenerated manuscript can differ while an older Ready block
   causes the upgrade idempotency check to skip the new body.

The contract is now content-addressed: the caption contains an automatic SHA-256 of the actual
publication-policy files and SHA-256 of the manuscript body.  Upgrade idempotency skips append
only when the *latest valid current-policy Ready block* is byte-equivalent to the manuscript
being saved.  Older blocks remain for audit but can never satisfy a newer/different save.

Notion rich_text segmentation is transport-only and must never change manuscript bytes.  The
legacy paragraph-aware chunker can drop a newline when a chunk boundary is crossed, while Notion
may merge rich_text segments again on readback.  This overlay therefore rewrites code-block
rich_text with lossless fixed-size slices before persistence and verifies the in-memory roundtrip.
"""
from __future__ import annotations

import inspect
from typing import Any

import publication_contract as contract

_INSTALLED_ATTR = "_run194_publication_contract_installed"
_DEFAULT_NOTION_RICH_TEXT_LIMIT = 1900


def _block_body(block: dict) -> str:
    code = (block or {}).get("code") or {}
    return "".join(
        str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
        for item in (code.get("rich_text") or [])
    )


def _lossless_text_segments(text: str, limit: int) -> list[str]:
    """Split only for Notion transport; joining the segments must reproduce text exactly."""
    if limit <= 0:
        raise ValueError("Notion rich_text limit must be positive")
    value = str(text or "")
    return [value[i:i + limit] for i in range(0, len(value), limit)]


def _rewrite_code_rich_text_losslessly(children: list, manuscript: str, limit: int) -> list:
    """Replace a real Notion code-block payload's rich_text without changing stub/test shapes."""
    if not children or not isinstance(children[0], dict):
        return children
    code = children[0].get("code")
    if not isinstance(code, dict) or "rich_text" not in code:
        return children

    segments = _lossless_text_segments(manuscript, limit)
    code["rich_text"] = [
        {"type": "text", "text": {"content": segment}}
        for segment in segments
    ]
    roundtrip = "".join(
        str(((item.get("text") or {}).get("content")) or "")
        for item in code["rich_text"]
    )
    if roundtrip != str(manuscript or ""):
        raise RuntimeError("Notion manuscript segmentation changed persisted bytes")
    return children


def _latest_current_block(pipeline_module: Any, page_id: str, headers: dict) -> tuple[str, str] | None:
    latest: tuple[str, str] | None = None
    for block in pipeline_module._notion_page_manuscript_blocks(page_id, headers):
        caption = pipeline_module._notion_code_caption(block)
        body = _block_body(block)
        if contract.is_current_ready_block(body, caption):
            latest = (body, caption)
    return latest


def install(pipeline_module: Any) -> Any:
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_build_children = pipeline_module.build_notion_manuscript_children
    original_upgrade = pipeline_module.upgrade_notion_page_with_report
    upgrade_signature = inspect.signature(original_upgrade)
    legacy_ready_caption = str(
        getattr(pipeline_module, "MANUSCRIPT_CAPTION_READY", "AIIF_MANUSCRIPT:READY")
    )

    def build_current_manuscript_children(clean_manuscript: str, caption: str | None = None) -> list:
        effective = caption
        if effective is None or str(effective).strip() == legacy_ready_caption:
            effective = contract.current_ready_caption(clean_manuscript)
        children = original_build_children(clean_manuscript, effective)
        limit = int(
            getattr(pipeline_module, "NOTION_BLOCK_LIMIT", _DEFAULT_NOTION_RICH_TEXT_LIMIT)
            or _DEFAULT_NOTION_RICH_TEXT_LIMIT
        )
        return _rewrite_code_rich_text_losslessly(children, clean_manuscript, limit)

    def has_current_ready_manuscript(page_id: str, headers: dict) -> bool:
        return _latest_current_block(pipeline_module, page_id, headers) is not None

    def upgrade_with_exact_body_idempotency(*args, **kwargs):
        bound = upgrade_signature.bind_partial(*args, **kwargs)
        clean_manuscript = str(bound.arguments.get("clean_manuscript") or "")
        if not clean_manuscript:
            return original_upgrade(*args, **kwargs)

        previous_has = pipeline_module._notion_page_has_manuscript_child

        def latest_matches_expected(page_id: str, headers: dict) -> bool:
            latest = _latest_current_block(pipeline_module, page_id, headers)
            if latest is None:
                return False
            body, caption = latest
            return contract.is_exact_current_ready_block(body, caption, clean_manuscript)

        # The original two-phase transaction remains authoritative.  We change only its
        # idempotency answer for this call, then restore the default predicate even on failure.
        pipeline_module._notion_page_has_manuscript_child = latest_matches_expected
        try:
            return original_upgrade(*args, **kwargs)
        finally:
            pipeline_module._notion_page_has_manuscript_child = previous_has

    pipeline_module.build_notion_manuscript_children = build_current_manuscript_children
    pipeline_module._notion_page_has_manuscript_child = has_current_ready_manuscript
    pipeline_module.upgrade_notion_page_with_report = upgrade_with_exact_body_idempotency
    pipeline_module.CURRENT_PUBLICATION_CONTRACT = contract.CONTRACT_ID
    pipeline_module.CURRENT_PUBLICATION_POLICY_SHA256 = contract.policy_sha256()
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
