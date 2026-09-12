#!/usr/bin/env python3
"""Run362: read-only provenance audit for stale Ready manuscripts.

Maps persisted Ready-family policy fingerprints to fingerprints that actually existed on
main's first-parent history. A historical Ready match is valid only when the caption policy
fingerprint existed on main AND the caption manuscript SHA matches the persisted body bytes.
For pages without valid Ready-family captions it inventories only metadata/hashes of
manuscript-like code blocks. It never writes Notion and never calls a model.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import note_ready_sync as sync
import publication_contract as contract

REPORT_PATH = Path("gate_history/run362_ready_provenance_audit.json")
MAX_HISTORY = 900


def _git(*args: str, allow_fail: bool = False) -> bytes:
    p = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode and not allow_fail:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.decode(errors='replace')[:400]}")
    return p.stdout if p.returncode == 0 else b""


def _manifest_at(commit: str) -> tuple[str, ...]:
    raw = _git("show", f"{commit}:publication_contract.py", allow_fail=True)
    if not raw:
        return ()
    try:
        tree = ast.parse(raw.decode("utf-8"))
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "PUBLICATION_POLICY_FILES" for t in node.targets):
                value = ast.literal_eval(node.value)
                if isinstance(value, tuple) and all(isinstance(x, str) for x in value):
                    return tuple(value)
    except Exception:
        return ()
    return ()


def _policy_sha_at(commit: str) -> str:
    manifest = _manifest_at(commit)
    if not manifest:
        return ""
    d = hashlib.sha256()
    for rel in manifest:
        body = _git("show", f"{commit}:{rel}", allow_fail=True)
        if not body:
            return ""
        d.update(rel.encode()); d.update(b"\0"); d.update(body); d.update(b"\0")
    return d.hexdigest()


def historical_policy_index() -> dict[str, dict[str, str]]:
    commits = _git("rev-list", "--first-parent", f"--max-count={MAX_HISTORY}", "HEAD").decode().splitlines()
    out: dict[str, dict[str, str]] = {}
    last = None
    for commit in commits:
        sha = _policy_sha_at(commit)
        if not sha or sha == last:
            continue
        last = sha
        ts = _git("show", "-s", "--format=%cI", commit).decode().strip()
        subject = _git("show", "-s", "--format=%s", commit).decode().strip()
        out.setdefault(sha, {"commit": commit, "committed_at": ts, "subject": subject})
    return out


def _caption_fields(caption: str) -> dict[str, str]:
    text = str(caption or "").strip()
    if text == contract.LEGACY_READY_CAPTION:
        return {"legacy": "true"}
    if not text.startswith(contract.READY_CAPTION_PREFIX):
        return {}
    fields: dict[str, str] = {}
    for token in text[len(contract.READY_CAPTION_PREFIX):].split("|"):
        if "=" in token:
            k, v = token.split("=", 1)
            fields[k.strip()] = v.strip()
    return fields


def _block_meta(block: dict, index: int) -> dict[str, Any]:
    body = sync._code_body(block)
    caption = sync._code_caption(block)
    fields = _caption_fields(caption)
    return {
        "index": index,
        "type": block.get("type"),
        "caption": caption[:280],
        "ready_family": contract.is_ready_family_caption(caption),
        "body_len": len(body),
        "body_sha256": contract.manuscript_sha256(body) if body else "",
        "caption_policy_sha256": fields.get("policy_sha256", ""),
        "caption_manuscript_sha256": fields.get("manuscript_sha256", ""),
        "body_sha_valid": bool(body and fields.get("manuscript_sha256") == contract.manuscript_sha256(body)),
        "legacy_ready_caption": fields.get("legacy") == "true",
    }


def main() -> int:
    if not sync.NOTION_API_KEY:
        raise ValueError("NOTION_API_KEY is required")
    history = historical_policy_index()
    pages = sync._query_db(
        sync.SOURCE_DATA_SOURCE_ID, sync.SOURCE_DATABASE_ID,
        payload={"filter": {"property": sync.SOURCE_ARTICLE_STATUS, "select": {"equals": sync.SOURCE_READY}}},
    )
    rows = []
    summary: dict[str, int] = {}
    for page in pages:
        page_id = str(page.get("id") or "")
        state = sync._source_state(page)
        blocks = sync._block_children(page_id)
        metas = [_block_meta(b, i) for i, b in enumerate(blocks) if b.get("type") == "code"]
        ready = [m for m in metas if m["ready_family"]]
        matched = []
        for m in ready:
            psha = m["caption_policy_sha256"]
            if psha and psha in history and m["body_sha_valid"]:
                matched.append({**m, "historical_main": history[psha]})
        legacy_candidates = [
            m for m in metas
            if (not m["ready_family"]) and m["body_len"] >= 500
        ]
        if not state:
            cls = "unsupported_or_incomplete"
        elif not state.get("eyecatch_url"):
            cls = "missing_eyecatch"
        elif matched:
            cls = "historical_main_ready_family"
        elif ready:
            cls = "unmapped_ready_family"
        elif legacy_candidates:
            cls = "legacy_manuscript_like_code"
        else:
            cls = "no_manuscript_provenance"
        summary[cls] = summary.get(cls, 0) + 1
        rows.append({
            "page_id": page_id,
            "title": (state or {}).get("title", ""),
            "source": (state or {}).get("source", ""),
            "primary_url": (state or {}).get("primary_url", ""),
            "eyecatch_present": bool((state or {}).get("eyecatch_url")),
            "classification": cls,
            "ready_family_blocks": ready,
            "historical_main_matches": matched,
            "legacy_manuscript_like_code": legacy_candidates,
            "code_block_count": len(metas),
        })
    result = {
        "run": "run362_ready_provenance_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "write_operations": 0,
        "model_calls": 0,
        "pages_seen": len(pages),
        "historical_policy_fingerprints": len(history),
        "summary": summary,
        "rows": rows,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
