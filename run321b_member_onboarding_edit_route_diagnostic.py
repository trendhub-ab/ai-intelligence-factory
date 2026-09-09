#!/usr/bin/env python3
"""Compatibility runner for the Run322 no-mutation publish-settings probe.

Run321b established the exact intermediate dialog. The existing hard-bound workflow still invokes
this filename, so it now delegates to Run322, which selects `最新の下書き`, clicks the observed
`編集する` confirmation, re-verifies the exact revision, enters publish settings, and stops before
any final save/update/publish control.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import note_draft_automation as base
import run321_member_onboarding_official_edit_route_probe as run321
import run322_member_onboarding_version_confirm_publish_probe as run322

CONFIRM_TOKEN = run321.CONFIRM_TOKEN
RESULT_ENV = "NOTE_MEMBER_ONBOARDING_EDIT_ROUTE_DIAGNOSTIC_RESULT_FILE"


def diagnose() -> dict:
    supplied = os.environ.get("NOTE_MEMBER_ONBOARDING_EDIT_ROUTE_DIAGNOSTIC_CONFIRM", "").strip()
    if supplied != CONFIRM_TOKEN:
        raise base.NoteDraftError("Run321b/322 exact edit-route confirmation is missing or invalid")

    prior = os.environ.get("NOTE_MEMBER_ONBOARDING_VERSION_CONFIRM_PUBLISH_PROBE_CONFIRM")
    os.environ["NOTE_MEMBER_ONBOARDING_VERSION_CONFIRM_PUBLISH_PROBE_CONFIRM"] = supplied
    try:
        result = run322.probe()
    finally:
        if prior is None:
            os.environ.pop("NOTE_MEMBER_ONBOARDING_VERSION_CONFIRM_PUBLISH_PROBE_CONFIRM", None)
        else:
            os.environ["NOTE_MEMBER_ONBOARDING_VERSION_CONFIRM_PUBLISH_PROBE_CONFIRM"] = prior

    # Preserve the existing workflow's result contract while exposing all Run322 evidence.
    result = dict(result)
    result["status"] = "diagnostic_complete_no_mutation"
    result["run322_probe_completed"] = True
    return result


def main() -> None:
    result = diagnose()
    output = os.environ.get(RESULT_ENV, "").strip()
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("RUN321B_MEMBER_ONBOARDING_EDIT_ROUTE_DIAGNOSTIC=" + json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
