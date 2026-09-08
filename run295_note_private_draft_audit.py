#!/usr/bin/env python3
"""Run295: use one shared eyecatch-persistence proof for note creation and audit.

Run294 proved the current GenRec private draft contains a 620x325 header image even
though note no longer exposes the legacy visible "画像を変更" control. Run295 turns
that diagnostic into the canonical fail-closed proof used by the read-only audit.
The creation path installs the same proof separately from run194_note_persistent_cloud.

This entrypoint is read-only. It emits only categorical/numeric eyecatch metrics and
the existing Run292 safe body diagnostics. No unpublished text, draft URL, image URL,
screenshot, model call, draft mutation, or public-release action is exposed.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable

import note_eyecatch_persistence as eyecatch
import run292_note_rendered_body_audit as base292

base = base292.base


class Run295EyecatchProofError(base.PrivateDraftAuditError):
    def __init__(self, code: str, metrics: dict[str, Any]) -> None:
        super().__init__(f"Run295 eyecatch proof failed safely: {code}")
        self.code = str(code)
        self.safe_metrics = dict(metrics)


def _audit_wrapper(original: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
    def wrapped(page: Any, title: str, manuscript: str) -> dict[str, Any]:
        try:
            title_locator = base.note_base._find_title(page)
        except Exception:
            title_locator = None
        metrics = eyecatch.collect_eyecatch_metrics(page, title_locator=title_locator)
        state = eyecatch.classify_eyecatch_persistence(metrics)
        if not eyecatch.eyecatch_persistence_confirmed(metrics):
            code = "eyecatch_missing_likely" if state == eyecatch.MISSING_LIKELY else "eyecatch_persistence_ambiguous"
            raise Run295EyecatchProofError(code, metrics)

        proxy = eyecatch.EyecatchProofPageProxy(page, base.note_base._find_title)
        result = original(proxy, title, manuscript)
        result["eyecatch_present"] = True
        result["eyecatch_proof_mode"] = state
        for key, value in metrics.items():
            result[key] = value
        return result

    return wrapped


def run(*, confirm: str, sync_id: str, prepare_only: bool = False) -> dict[str, Any]:
    original = base._audit_current_page
    base._audit_current_page = _audit_wrapper(original)
    try:
        return base292.run(confirm=confirm, sync_id=sync_id, prepare_only=prepare_only)
    finally:
        base._audit_current_page = original


def _safe_failure_result(sync_id: str, code: str, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    return base292._safe_failure_result(sync_id, code, metrics)


def _write_result(path_value: str, result: dict[str, Any]) -> None:
    if not path_value:
        return
    target = Path(path_value)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sync-id", default=os.environ.get("NOTE_TARGET_SYNC_ID", ""))
    parser.add_argument("--confirm", default=os.environ.get("NOTE_AUDIT_CONFIRM", ""))
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        default=os.environ.get("NOTE_AUDIT_PREPARE_ONLY", "false").lower() in {"1", "true", "yes", "on"},
    )
    parser.add_argument("--result-file", default=os.environ.get("NOTE_AUDIT_RESULT_FILE", ""))
    args = parser.parse_args()

    exit_code = 0
    try:
        result = run(confirm=args.confirm, sync_id=args.sync_id, prepare_only=args.prepare_only)
    except Run295EyecatchProofError as exc:
        result = _safe_failure_result(args.sync_id, exc.code, exc.safe_metrics)
        exit_code = 2
    except base292.Run292AuditDiagnosticError as exc:
        result = _safe_failure_result(args.sync_id, exc.code, exc.safe_metrics)
        exit_code = 2
    except base.PrivateDraftAuditError as exc:
        result = _safe_failure_result(args.sync_id, base292._safe_non_body_guard_code(exc))
        exit_code = 2

    _write_result(args.result_file, result)
    print(json.dumps(result, ensure_ascii=False))
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
