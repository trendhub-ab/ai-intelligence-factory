"""Bounded, read-only validation of the repaired P13 inventory on GitHub-hosted runner.

Use the exact pinned Next implementation and original credential. Observe only
fixed phase names, HTTP status codes and actual request counts, including
429 retries performed by the pinned client. No diagnostic-level retry or writes.
"""
from __future__ import annotations

import json
import os
import re
import time
from urllib.error import HTTPError
from unittest.mock import patch

MAX_REQUESTS = 6000
MAX_SECONDS = 1800
SAFE_P13_CODES = frozenset({
    "P13_NOTION_ID_INVALID", "P13_REQUEST_NOT_READ_ONLY_ALLOWLISTED",
    "P13_NOTION_NON_200", "P13_NOTION_RESPONSE_TOO_LARGE", "P13_NOTION_READ_FAILED",
    "P13_NOTION_RESPONSE_INVALID", "P13_NOTION_READ_TOKEN_UNAVAILABLE",
    "P13_UNREGISTERED_DATA_SOURCE", "P13_DATA_SOURCE_ID_MISMATCH",
    "P13_DATA_SOURCE_SCHEMA_MISSING", "P13_PAGINATION_RESPONSE_INVALID",
    "P13_RESULT_ROW_INVALID", "P13_DUPLICATE_RESULT_ID", "P13_PAGINATION_SAFETY_LIMIT",
    "P13_FINAL_CURSOR_UNEXPECTED", "P13_NEXT_CURSOR_MISSING", "P13_CURSOR_REPEATED",
    "P13_PAGE_COUNT_EXCEEDED", "P13_ROW_PARENT_SOURCE_MISMATCH",
    "P13_SCHEMA_CONTRACT_MISMATCH", "P13_MALFORMED_CODE_BLOCK",
    "P13_DUPLICATE_LINEAGE_IN_PAGE", "P13_BAD_LINEAGE_JSON",
    "P13_LINEAGE_CONTRACT_MISMATCH", "P13_DUPLICATE_NEXT_IDENTITY",
    "P13_QUEUE_SYNC_ID_INVALID", "P13_QUEUE_SYNC_ID_DUPLICATE",
    "P13_RATE_LIMIT_EXHAUSTED", "P13_RATE_LIMIT_WAIT_EXCEEDS_BUDGET",
    "P13_RATE_LIMIT_RETRY_AFTER_INVALID",
})


class BudgetStop(Exception):
    pass


def probe(module, token, *, clock=time.monotonic, max_requests=MAX_REQUESTS,
          max_seconds=MAX_SECONDS, progress=None):
    start = clock()
    receipt = {"status": "READ_ONLY_PROBE_STOPPED", "phase": "initial",
               "requests": 0, "rate_limit_responses": 0, "http_status": None, "reason": "UNKNOWN",
               "notion_writes": 0, "note_writes": 0, "model_calls": 0,
               "vm_started": False, "full_inventory_verified": False}
    original_builder = module.build_opener

    def observed_builder(*args, **kwargs):
        opener = original_builder(*args, **kwargs)

        class Observer:
            def open(self, *a, **kw):
                if receipt["requests"] >= max_requests or clock() - start >= max_seconds:
                    receipt["reason"] = "PROBE_BUDGET_REACHED"
                    raise BudgetStop()
                receipt["requests"] += 1
                receipt["http_status"] = None
                if progress is not None and receipt["requests"] % 250 == 0:
                    progress({"status": "READ_ONLY_SCAN_PROGRESS",
                              "requests": receipt["requests"],
                              "rate_limit_responses": receipt["rate_limit_responses"],
                              "phase": receipt["phase"]})
                try:
                    response = opener.open(*a, **kw)
                except HTTPError as exc:
                    receipt["http_status"] = exc.code if type(exc.code) is int else None
                    if exc.code == 429:
                        receipt["rate_limit_responses"] += 1
                    raise
                receipt["http_status"] = response.status
                return response

        return Observer()

    def transport(method, path, payload, key):
        receipt["phase"] = (
            "root_blocks" if path.startswith("/v1/blocks/") else
            "data_source_rows" if method == "POST" else "schema"
        )
        return module._http_readonly(method, path, payload, key)

    try:
        with patch.object(module, "build_opener", observed_builder):
            result = module.NotionReadOnlyClient(token, transport=transport).read_inventory()
        receipt.update(status="READ_ONLY_INVENTORY_COMPLETE", reason="NONE",
                       full_inventory_verified=True,
                       content_count=len(result.content_pages), queue_count=len(result.queue_rows),
                       lineage_count=len(result.lineage_documents))
    except Exception as exc:
        if receipt["reason"] != "PROBE_BUDGET_REACHED":
            reason = str(exc)
            receipt["reason"] = reason if reason in SAFE_P13_CODES else "UNCLASSIFIED"
        # Never print traceback, exception text, page IDs, request URL or body.
    return receipt


def main():
    from aiif_next import p13_notion_public_api_readonly as p13
    result = probe(p13, os.environ.get("NOTION_API_KEY", ""),
                   progress=lambda item: print(json.dumps(item, sort_keys=True), flush=True))
    print(json.dumps(result, sort_keys=True))
    # Completed diagnostic, not a successful inventory or create authority.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
