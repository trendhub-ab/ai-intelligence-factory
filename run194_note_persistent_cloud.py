#!/usr/bin/env python3
"""Run194 cloud entrypoint: persistent Chrome plus current publication-contract guard.

This keeps Run190's browser/session lifecycle and Run193's official note header-image UI, but
installs the Run194 current-manuscript guard before any source article can reach the browser.
There are no Gemini/model calls and no public-release action in this entrypoint.
"""
from __future__ import annotations

import note_draft_automation as base
import run190_note_persistent_cloud as cloud
import run194_note_current_contract as current_contract


def main() -> None:
    cloud.install()
    current_contract.install()
    base.main()


if __name__ == "__main__":
    main()
