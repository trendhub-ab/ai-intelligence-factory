#!/usr/bin/env python3
"""Hosted note draft entrypoint with current-publication and durable-delivery guards.

Production execution is intentionally ephemeral: GitHub-hosted Chromium is created from
NOTE_STORAGE_STATE_B64 for each run and closed at the end. No persistent browser profile,
self-hosted runner, VM-local state, OS account, or public-release action is required.
"""
from __future__ import annotations

import note_draft_automation as base
import note_delivery_runtime as delivery_runtime
import note_eyecatch_persistence as eyecatch_persistence
import note_publication_reconcile as note_lifecycle
import run193_note_official_header_upload as run193
import run194_note_current_contract as current_contract
import run222_note_presentation_integrity as run222
import run417_note_body_verification as run417


def main() -> None:
    # Keep the proven visible-UI header/crop/editor guards while retaining base's
    # ephemeral storage-state browser lifecycle.
    run193.install()
    run417.install(base)
    current_contract.install()
    run222.install_note(base)
    eyecatch_persistence.install_creation_persistence_guard(base)
    note_lifecycle.install_draft_identity(base)
    # Durable delivery owns base.run and must be installed last before execution.
    delivery_runtime.install(base)
    current_contract.run_base_main_with_safe_noop()


if __name__ == "__main__":
    main()
