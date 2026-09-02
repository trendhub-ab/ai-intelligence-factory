"""Run194: version persisted Ready manuscripts with the current production contract.

Why this exists:
- historical Content Intelligence pages can remain `記事状態=Ready` after the quality stack
  changes;
- the pre-Run194 idempotency guard treated any old/unversioned Ready manuscript as sufficient
  and therefore could prevent a newly generated current manuscript from being appended;
- downstream note automation then had no reliable way to distinguish old Ready inventory from
  content produced by the current article-quality and eyecatch stack.

This layer is zero-provider-call.  It does not alter article text, scores, gates, Gemini budget,
or public-release behavior.  It only changes the Ready manuscript persistence contract:
current production Ready manuscripts receive an exact versioned caption, and an old Ready block
no longer blocks appending a current-version Ready block.  Old blocks are deliberately retained
for audit/rollback; downstream publication paths select only the current stamp.
"""
from __future__ import annotations

from typing import Any

import publication_contract as contract

_INSTALLED_ATTR = "_run194_publication_contract_installed"


def install(pipeline_module: Any) -> Any:
    if getattr(pipeline_module, _INSTALLED_ATTR, False):
        return pipeline_module

    original_build_children = pipeline_module.build_notion_manuscript_children
    legacy_ready_caption = str(getattr(pipeline_module, "MANUSCRIPT_CAPTION_READY", "AIIF_MANUSCRIPT:READY"))

    def build_current_manuscript_children(clean_manuscript: str, caption: str | None = None) -> list:
        effective = caption
        if effective is None or str(effective).strip() == legacy_ready_caption:
            effective = contract.CURRENT_READY_CAPTION
        return original_build_children(clean_manuscript, effective)

    def has_current_ready_manuscript(page_id: str, headers: dict) -> bool:
        # Historical/unversioned Ready blocks are not deleted, but they are no longer allowed
        # to satisfy the idempotency guard for a current production save.
        for block in pipeline_module._notion_page_manuscript_blocks(page_id, headers):
            caption = pipeline_module._notion_code_caption(block)
            if contract.is_current_ready_caption(caption):
                return True
        return False

    pipeline_module.build_notion_manuscript_children = build_current_manuscript_children
    pipeline_module._notion_page_has_manuscript_child = has_current_ready_manuscript
    pipeline_module.MANUSCRIPT_CAPTION_CURRENT_READY = contract.CURRENT_READY_CAPTION
    pipeline_module.CURRENT_PUBLICATION_CONTRACT = contract.CONTRACT_ID
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
