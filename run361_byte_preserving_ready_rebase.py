#!/usr/bin/env python3
"""Run361: byte-preserving recovery for the Ready inventory invalidated by PR #295.

This is deliberately not a general stale-manuscript migration. It can re-sign only a
manuscript that was current under the exact main commit immediately before PR #295 and whose
persisted manuscript SHA still matches its body bytes.

Why this narrow migration is safe:
- PR #295 changed paid-product/Notion comment ownership and the publication fingerprint, not
  the accepted article body bytes.
- Run360 changes Writer/retry orchestration only; it does not lower Fact, Evidence,
  Publication, Editorial, Human Appeal, or Reader acceptance thresholds.
- a repository-diff guard refuses execution if any publication-policy file outside the
  reviewed allowlist changed since the safe base ref;
- the manuscript body is appended byte-for-byte unchanged under the current caption;
- unsupported/legacy captions, body-SHA mismatches, missing eyecatches, inactive sources,
  multiple/conflicting candidates, or a newer Ready-family block are skipped fail-closed.

ZERO model/provider calls. No article regeneration. No public note publication.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import note_ready_sync as sync
import publication_contract as contract

SAFE_BASE_REF = "3f235ba38519a5bb4c3500e6184a2493e2b88cce"
APPLY_CONFIRMATION = "REBASE_IDENTICAL_BODY"
RICH_TEXT_LIMIT = 1900
DEFAULT_MAX_PAGES = 40
REPORT_PATH = Path("gate_history/run361_stale_ready_rebase_report.json")

# Every publication-material difference from SAFE_BASE_REF to this migration was reviewed.
# decision_intelligence/comment_write_contract are paid-product comment preservation only;
# publication_contract only adds that dependency to the fingerprint; run208/run284 are
# generation/retry orchestration and do not weaken an acceptance gate.
SAFE_CHANGED_POLICY_FILES = frozenset({
    "decision_intelligence.py",
    "comment_write_contract.py",
    "publication_contract.py",
    "run208_reader_value_repair.py",
    "run284_reader_recovery_precision.py",
})
EXPECTED_MANIFEST_ADDITIONS = frozenset({"comment_write_contract.py"})


@dataclass(frozen=True)
class CandidateDecision:
    status: str
    reason: str
    body: str = ""
    old_policy_sha256: str = ""
    manuscript_sha256: str = ""


def _git(*args: str) -> bytes:
    proc = subprocess.run(
        ["git", *args], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed: {proc.stderr.decode('utf-8', errors='replace')[:500]}"
        )
    return proc.stdout


def _manifest_from_source(source: str) -> tuple[str, ...]:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(t, ast.Name) and t.id == "PUBLICATION_POLICY_FILES" for t in node.targets):
                value = ast.literal_eval(node.value)
                if not isinstance(value, tuple) or not all(isinstance(x, str) for x in value):
                    raise RuntimeError("PUBLICATION_POLICY_FILES is not a literal tuple of strings")
                return tuple(value)
    raise RuntimeError("PUBLICATION_POLICY_FILES not found")


def historical_manifest(ref: str = SAFE_BASE_REF) -> tuple[str, ...]:
    source = _git("show", f"{ref}:publication_contract.py").decode("utf-8")
    return _manifest_from_source(source)


def historical_policy_sha256(ref: str = SAFE_BASE_REF) -> str:
    import hashlib

    digest = hashlib.sha256()
    for relative in historical_manifest(ref):
        body = _git("show", f"{ref}:{relative}")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(body)
        digest.update(b"\0")
    return digest.hexdigest()


def changed_publication_policy_files(ref: str = SAFE_BASE_REF) -> set[str]:
    old = set(historical_manifest(ref))
    current = set(contract.PUBLICATION_POLICY_FILES)
    union = sorted(old | current)
    if not union:
        return set()
    changed = _git("diff", "--name-only", ref, "HEAD", "--", *union).decode("utf-8")
    return {line.strip() for line in changed.splitlines() if line.strip()}


def verify_repository_compatibility(ref: str = SAFE_BASE_REF) -> dict[str, Any]:
    old_manifest = set(historical_manifest(ref))
    current_manifest = set(contract.PUBLICATION_POLICY_FILES)
    added = current_manifest - old_manifest
    removed = old_manifest - current_manifest
    changed = changed_publication_policy_files(ref)
    unexpected_changed = changed - SAFE_CHANGED_POLICY_FILES
    unexpected_added = added - EXPECTED_MANIFEST_ADDITIONS
    if removed or unexpected_changed or unexpected_added:
        raise RuntimeError(
            "Run361 publication-policy diff is no longer proven compatible: "
            f"removed={sorted(removed)} unexpected_changed={sorted(unexpected_changed)} "
            f"unexpected_added={sorted(unexpected_added)}"
        )
    return {
        "base_ref": ref,
        "changed_policy_files": sorted(changed),
        "manifest_added": sorted(added),
        "manifest_removed": sorted(removed),
    }


def _caption_fields(value: str) -> dict[str, str]:
    text = str(value or "").strip()
    if not text.startswith(contract.READY_CAPTION_PREFIX):
        return {}
    fields: dict[str, str] = {}
    for token in text[len(contract.READY_CAPTION_PREFIX):].split("|"):
        if "=" not in token:
            return {}
        key, val = token.split("=", 1)
        key, val = key.strip(), val.strip()
        if not key or key in fields:
            return {}
        fields[key] = val
    return fields


def classify_ready_blocks(blocks: list[dict], historical_policy_sha: str) -> CandidateDecision:
    ready_family: list[tuple[int, str, str, dict[str, str], bool]] = []
    for index, block in enumerate(blocks):
        caption = sync._code_caption(block)
        if not contract.is_ready_family_caption(caption):
            continue
        body = sync._code_body(block)
        fields = _caption_fields(caption)
        body_valid = bool(
            body
            and fields.get("contract") == contract.CONTRACT_ID
            and fields.get("manuscript_sha256") == contract.manuscript_sha256(body)
        )
        ready_family.append((index, body, caption, fields, body_valid))

    if not ready_family:
        return CandidateDecision("skip", "no_ready_family_block")

    current = [row for row in ready_family if row[4] and contract.is_current_ready_block(row[1], row[2])]
    if current:
        return CandidateDecision("current", "already_current")

    matches = [
        row for row in ready_family
        if row[4] and row[3].get("policy_sha256") == historical_policy_sha
    ]
    if len(matches) != 1:
        return CandidateDecision("skip", f"safe_historical_match_count={len(matches)}")

    selected = matches[0]
    if selected[0] != ready_family[-1][0]:
        return CandidateDecision("skip", "safe_block_is_not_latest_ready_family")

    body = selected[1]
    return CandidateDecision(
        "eligible",
        "exact_pre_pr295_current_block_body_hash_valid",
        body=body,
        old_policy_sha256=historical_policy_sha,
        manuscript_sha256=contract.manuscript_sha256(body),
    )


def _current_code_block(body: str) -> dict[str, Any]:
    segments = [body[i:i + RICH_TEXT_LIMIT] for i in range(0, len(body), RICH_TEXT_LIMIT)]
    if not segments or "".join(segments) != body:
        raise RuntimeError("Run361 segmentation changed manuscript bytes")
    caption = contract.current_ready_caption(body)
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [
                {"type": "text", "text": {"content": segment}}
                for segment in segments
            ],
            "language": "markdown",
            "caption": [{"type": "text", "text": {"content": caption}}],
        },
    }


def _write_report(payload: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run(mode: str = "dry_run", confirmation: str = "", max_pages: int = DEFAULT_MAX_PAGES) -> dict[str, Any]:
    mode = str(mode or "dry_run").strip().lower()
    if mode not in {"dry_run", "apply"}:
        raise ValueError("mode must be dry_run or apply")
    if mode == "apply" and confirmation != APPLY_CONFIRMATION:
        raise ValueError(f"apply requires confirmation={APPLY_CONFIRMATION}")
    if max_pages < 1 or max_pages > DEFAULT_MAX_PAGES:
        raise ValueError(f"max_pages must be within 1..{DEFAULT_MAX_PAGES}")
    if not sync.NOTION_API_KEY:
        raise ValueError("NOTION_API_KEY is required")
    if not (sync.SOURCE_DATA_SOURCE_ID or sync.SOURCE_DATABASE_ID):
        raise ValueError("Content Intelligence source DB is not configured")

    compatibility = verify_repository_compatibility()
    old_policy = historical_policy_sha256()
    current_policy = contract.policy_sha256()
    if old_policy == current_policy:
        raise RuntimeError("Run361 expected a policy transition but historical/current SHA are equal")

    pages = sync._query_db(
        sync.SOURCE_DATA_SOURCE_ID,
        sync.SOURCE_DATABASE_ID,
        payload={
            "filter": {
                "property": sync.SOURCE_ARTICLE_STATUS,
                "select": {"equals": sync.SOURCE_READY},
            }
        },
    )

    rows: list[dict[str, Any]] = []
    eligible: list[tuple[str, str, CandidateDecision]] = []
    for page in pages:
        page_id = str(page.get("id") or "").strip()
        state = sync._source_state(page)
        if not state:
            rows.append({"page_id": page_id, "status": "skip", "reason": "unsupported_or_incomplete_ready_source"})
            continue
        if not state.get("eyecatch_url"):
            rows.append({"page_id": page_id, "title": state.get("title"), "status": "skip", "reason": "missing_eyecatch"})
            continue
        decision = classify_ready_blocks(sync._block_children(page_id), old_policy)
        row = {
            "page_id": page_id,
            "title": state.get("title") or "",
            "source": state.get("source") or "",
            "primary_url": state.get("primary_url") or "",
            **{k: v for k, v in asdict(decision).items() if k != "body"},
        }
        rows.append(row)
        if decision.status == "eligible":
            eligible.append((page_id, state.get("title") or "", decision))

    if len(eligible) > max_pages:
        raise RuntimeError(
            f"Run361 eligible count {len(eligible)} exceeds max_pages={max_pages}; refusing partial arbitrary migration"
        )

    applied = 0
    if mode == "apply":
        for page_id, title, decision in eligible:
            before_body = decision.body
            block = _current_code_block(before_body)
            # Local round-trip proof before touching Notion.
            if sync._code_body(block) != before_body:
                raise RuntimeError(f"Run361 local byte round-trip failed for {title}")
            if not contract.is_current_ready_block(before_body, sync._code_caption(block)):
                raise RuntimeError(f"Run361 generated invalid current caption for {title}")

            response = sync._request(
                "PATCH",
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                json={"children": [block]},
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"Run361 Notion append failed for {title}: HTTP {response.status_code} {response.text[:300]}"
                )
            verified = sync._source_current_ready_manuscript(page_id)
            if verified != before_body:
                raise RuntimeError(f"Run361 post-write byte verification failed for {title}")
            applied += 1

    counts: dict[str, int] = {}
    for row in rows:
        key = f"{row.get('status')}:{row.get('reason')}"
        counts[key] = counts.get(key, 0) + 1

    result = {
        "run": "run361_byte_preserving_ready_rebase",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "safe_base_ref": SAFE_BASE_REF,
        "historical_policy_sha256": old_policy,
        "current_policy_sha256": current_policy,
        "repository_compatibility": compatibility,
        "ready_pages_seen": len(pages),
        "eligible": len(eligible),
        "applied": applied,
        "body_bytes_modified": 0,
        "gemini_calls": 0,
        "public_release": False,
        "counts": counts,
        "rows": rows,
    }
    _write_report(result)
    return result


def main() -> int:
    mode = os.environ.get("AIIF_READY_REBASE_MODE", "dry_run")
    confirmation = os.environ.get("AIIF_READY_REBASE_CONFIRM", "")
    max_pages = int(os.environ.get("AIIF_READY_REBASE_MAX", str(DEFAULT_MAX_PAGES)))
    result = run(mode=mode, confirmation=confirmation, max_pages=max_pages)
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
