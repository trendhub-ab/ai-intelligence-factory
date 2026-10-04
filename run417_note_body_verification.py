"""Run417: install the P0-A canonical note body persistence contract.

The former distributed-anchor verifier could accept semantic corruption when a changed
value fell outside its sampled windows.  Run417 now delegates the effective draft path
to the deterministic canonical renderer + DOM readback guard.  This remains model-free
and contains no publication action.
"""
from __future__ import annotations

from typing import Any

import note_canonical_persistence_guard as canonical
import note_draft_automation as base


verify_body_content = canonical.verify_body_content
markdown_to_safe_html = canonical.markdown_to_safe_html


def install(note_module: Any = base) -> Any:
    canonical.install(note_module)
    note_module._run417_body_verification_installed = True
    return note_module
