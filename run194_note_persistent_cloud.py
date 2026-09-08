#!/usr/bin/env python3
"""Run194 cloud entrypoint: persistent Chrome plus current publication-contract guard.

This keeps Run190's browser/session lifecycle and Run193's official note header-image UI, but
installs the Run194 current-manuscript guard before any source article can reach the browser.
Run222 is installed only after that guard so note-editor presentation changes cannot weaken the
stored manuscript hash/policy validation. Run295 adds a shared fail-closed eyecatch persistence
proof after note UI selector drift was confirmed in production. There are no Gemini/model calls
and no public-release action in this entrypoint.
"""
from __future__ import annotations

import note_eyecatch_persistence as eyecatch_persistence
import run190_note_persistent_cloud as cloud
import run194_note_current_contract as current_contract
import run222_note_presentation_integrity as run222


def main() -> None:
    cloud.install()
    current_contract.install()
    # Validate the byte-exact stored manuscript first; only then strip the duplicated H1 and
    # correct the footer order for note's editor presentation.
    run222.install_note(cloud.base)
    # Run295 closes the old count()==0 escape hatch and accepts current note header-media
    # evidence when the obsolete visible "画像を変更" control is no longer present.
    eyecatch_persistence.install_creation_persistence_guard(cloud.base)
    current_contract.run_base_main_with_safe_noop()


if __name__ == "__main__":
    main()
