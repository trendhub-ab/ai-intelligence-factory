#!/usr/bin/env python3
"""Run365: byte-preserving rebase for the seven Run362-v2-proven stale Ready rows.

Run364 exposed one false positive in the original Run362 audit: a Ready caption whose policy
fingerprint existed on main but whose caption manuscript SHA did not match the persisted body.
Run365 therefore freezes only the seven rows that satisfy BOTH historical policy provenance
and exact body-hash validity.

Dry-run performs no writes. Apply requires an exact confirmation token, re-reads every page,
verifies metadata/eyecatch/history/body again, refuses partial batches, appends the exact
existing body under the current Ready caption, and verifies byte-identical readback.
No model/provider/Google API calls and no public note release are performed here.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import note_ready_sync as sync
import publication_contract as contract
import run362_ready_provenance_audit as provenance
import run364_historical_ready_rebase as base

APPLY_CONFIRMATION = "REBASE_RUN362_VALID_7"
REPORT_PATH = Path("gate_history/run365_historical_ready_rebase_report.json")
EXPECTED_ALLOWLIST_FINGERPRINT = "9812ce1e7d9a2da5a0ff48fb165cd027e27eda7dfe6769fe3fe8a9a9e95e9eab"

ALLOWLIST: dict[str, dict[str, str]] = {
    "3d5479ff-dca9-816a-a8da-c107d8f191b2": {
        "title": "AIに本番データベースの鍵をそのまま渡していませんか？",
        "source": "HackerNews",
        "primary_url": "https://www.tigerdata.com/blog/ai-agent-production-database-access",
        "manuscript_sha256": "82b6662d3ece726583a364802b7810e3ca0532859885fe96c32f5bd93c7be26d",
        "historical_policy_sha256": "651c5582aeb85628e14dd9c718d71a822bd92935d42db8a3987b682d6c322a21",
        "historical_commit": "6393b39ab86c3a142b491c481b91f642b2686999",
    },
    "3d2479ff-dca9-8195-bdf6-c54fe11e4a7a": {
        "title": "このAIは、なぜローン審査を落としたのか？」相関頼みのXAIを打ち破る「因果的説明」の新アプローチ。",
        "source": "ArXiv",
        "primary_url": "https://arxiv.org/abs/2609.04177v1",
        "manuscript_sha256": "4bd71b518c10d1b593b8f40b01f61cd1b51d246cdeddab0764e8490239327fe7",
        "historical_policy_sha256": "256df34a09b2a93e05c3b42032cad4445d3528469fb761aaf7cbf97ce581518a",
        "historical_commit": "94c85e20780a81ff8a069f6f2ca7f4800547c43a",
    },
    "3d2479ff-dca9-8145-aa8f-fe490a435be5": {
        "title": "次の単語を予測しているだけ」はもう古い？LLMの真価を見誤るメンタルモデルの罠。",
        "source": "HackerNews",
        "primary_url": "https://gmcgoldr.github.io/2026/09/04/llm-next-token-predictors.html",
        "manuscript_sha256": "17b9caa989d5a7765ad05498c2c91dd9c5dbd780116658da18f12ce29f18ac5d",
        "historical_policy_sha256": "abd19d7070eeafead97a1785dcebed99969e0fff4351a48f258eafb93aa82700",
        "historical_commit": "576c6f9b818101f524a237547401cbfe69b70989",
    },
    "3d1479ff-dca9-81cd-a9de-cdfe4c882cc9": {
        "title": "NVIDIA Blackwellの「FP4」はなぜ勝手に速くならないのか？FlashAttention-4が明かした現実と打開策。",
        "source": "ArXiv",
        "primary_url": "https://arxiv.org/abs/2609.04105v1",
        "manuscript_sha256": "8d61c063a1f911171916990e4f895615ebac05907dc62a41632e591ddf6aba7e",
        "historical_policy_sha256": "c837169941711b9f64c4095103f0ea57d18569026fbcc9dad7e86dae7d4fde5c",
        "historical_commit": "5bd30011e61d0f37c033557e68991cc6cb91f47b",
    },
    "3d0479ff-dca9-811a-ad6f-c525655c21ff": {
        "title": "Polars 2.0が目指す「静かな進化」は、なぜデータ開発の現場に大きな影響を与えるのか。",
        "source": "HackerNews",
        "primary_url": "https://pola.rs/posts/announcing-polars-2/",
        "manuscript_sha256": "05112cb4fb4dcceffff4a8cf971a02e1432130aee84dafa59673454ffb7ef722",
        "historical_policy_sha256": "9841aa3c535a449fca7ad96847e6bd95d944bab860227c2c66547fc07ac22623",
        "historical_commit": "aa0ca8f1de3b47e625917b48f75f22db9c43e838",
    },
    "3cc479ff-dca9-816b-b8e1-dbc5ce7b66f7": {
        "title": "AIでAIを採点する「LLMジャッジ」の落とし穴。統計手法が「存在しないバイアス」を作り出す仕組み。",
        "source": "ArXiv",
        "primary_url": "https://arxiv.org/abs/2608.27309v1",
        "manuscript_sha256": "60576c1b0b64ef7e0f7e03c2cf848b59fc7952067f332e51be74cf5a65acf934",
        "historical_policy_sha256": "abd19d7070eeafead97a1785dcebed99969e0fff4351a48f258eafb93aa82700",
        "historical_commit": "576c6f9b818101f524a237547401cbfe69b70989",
    },
    "3bd479ff-dca9-817f-926a-eaffbb779c4b": {
        "title": "Netflixが推薦の舞台裏をLLMネイティブへ舵を切った理由。",
        "source": "HackerNews",
        "primary_url": "https://netflixtechblog.com/genrec-towards-llm-native-recommendation-at-netflix-f20be6f643e3?gi=2e4aa81eb621",
        "manuscript_sha256": "8ffdf4ff26a7ccf80fc542f86f566bfc9291a33eef81932c03c79d8f2382ea4b",
        "historical_policy_sha256": "4e3f48cf4d9680a57efe99b0aa510a923e5a9585fac16058f0f9ab8098b27e80",
        "historical_commit": "880520487cb6c74619fb60faf695efac0759ca65",
    },
}

EXCLUDED_FALSE_POSITIVE = {
    "page_id": "3cf479ff-dca9-81c7-b087-f6ab02d10a85",
    "reason": "Run362-v1 matched policy history but body_sha_valid=false",
    "caption_manuscript_sha256": "a088b7141ee244fc5e819cdef84c0c30e6c4918a0f821cfd35b9237f0d5b71ce",
    "actual_body_sha256": "e4c77958659cbeceda4c0a6d994d48f903ff1662c19292b79b43e5f5719e56de",
}


def _allowlist_fingerprint() -> str:
    payload = json.dumps(ALLOWLIST, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _verify_allowlist_history() -> None:
    if len(ALLOWLIST) != 7:
        raise RuntimeError(f"Run365 allowlist must contain exactly 7 rows, got {len(ALLOWLIST)}")
    if _allowlist_fingerprint() != EXPECTED_ALLOWLIST_FINGERPRINT:
        raise RuntimeError("Run365 frozen allowlist fingerprint drift")
    if EXCLUDED_FALSE_POSITIVE["page_id"] in ALLOWLIST:
        raise RuntimeError("Run365 false-positive page re-entered allowlist")
    for page_id, expected in ALLOWLIST.items():
        commit = expected["historical_commit"]
        if subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"]).returncode != 0:
            raise RuntimeError(f"historical commit is not on current HEAD ancestry: {page_id} {commit}")
        actual_policy = provenance._policy_sha_at(commit)
        if actual_policy != expected["historical_policy_sha256"]:
            raise RuntimeError(
                f"historical policy proof drift for {page_id}: expected={expected['historical_policy_sha256']} actual={actual_policy}"
            )


def _write_report(result: dict[str, Any]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


def run(mode: str = "dry_run", confirmation: str = "") -> dict[str, Any]:
    mode = str(mode or "dry_run").strip().lower()
    if mode not in {"dry_run", "apply"}:
        raise ValueError("mode must be dry_run or apply")
    if mode == "apply" and confirmation != APPLY_CONFIRMATION:
        raise ValueError(f"apply requires confirmation={APPLY_CONFIRMATION}")
    if not sync.NOTION_API_KEY:
        raise ValueError("NOTION_API_KEY is required")

    _verify_allowlist_history()
    rows: list[dict[str, Any]] = []
    eligible: list[tuple[str, str, base.Decision]] = []
    current_count = 0

    for page_id, expected in ALLOWLIST.items():
        page = sync._request("GET", f"https://api.notion.com/v1/pages/{page_id}")
        if page.status_code != 200:
            rows.append({"page_id": page_id, "status": "blocked", "reason": f"page_read_http_{page.status_code}"})
            continue
        state = sync._source_state(page.json())
        if not state:
            rows.append({"page_id": page_id, "status": "blocked", "reason": "unsupported_or_incomplete_source"})
            continue
        pinned = {
            "title": state.get("title") or "",
            "source": state.get("source") or "",
            "primary_url": state.get("primary_url") or "",
        }
        mismatch = [k for k, v in pinned.items() if v != expected[k]]
        if mismatch:
            rows.append({"page_id": page_id, **pinned, "status": "blocked", "reason": "metadata_mismatch:" + ",".join(mismatch)})
            continue
        if not state.get("eyecatch_url"):
            rows.append({"page_id": page_id, **pinned, "status": "blocked", "reason": "missing_eyecatch"})
            continue

        decision = base.classify_page(sync._block_children(page_id), expected)
        rows.append({
            "page_id": page_id,
            **pinned,
            **{k: v for k, v in asdict(decision).items() if k != "body"},
        })
        if decision.status == "eligible":
            eligible.append((page_id, expected["title"], decision))
        elif decision.status == "current":
            current_count += 1

    blocked = [r for r in rows if r["status"] == "blocked"]
    if blocked:
        eligible = []

    # Run365 is intentionally all-or-nothing for the seven frozen rows. Already-current rows
    # are allowed for idempotent re-runs; every other row must be eligible.
    if not blocked and len(eligible) + current_count != 7:
        raise RuntimeError(
            f"Run365 batch cardinality mismatch: eligible={len(eligible)} current={current_count}"
        )

    applied = 0
    if mode == "apply" and not blocked:
        for page_id, title, decision in eligible:
            before = decision.body
            block = base._current_code_block(before)
            if sync._code_body(block) != before:
                raise RuntimeError(f"Run365 local byte round-trip failed for {title}")
            response = sync._request(
                "PATCH", f"https://api.notion.com/v1/blocks/{page_id}/children", json={"children": [block]}
            )
            if response.status_code != 200:
                raise RuntimeError(
                    f"Run365 Notion append failed for {title}: HTTP {response.status_code} {response.text[:300]}"
                )
            verified = sync._source_current_ready_manuscript(page_id)
            if verified != before:
                raise RuntimeError(f"Run365 post-write byte verification failed for {title}")
            applied += 1

    result = {
        "run": "run365_historical_ready_rebase",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "allowlist_size": len(ALLOWLIST),
        "allowlist_fingerprint": _allowlist_fingerprint(),
        "eligible": sum(1 for r in rows if r["status"] == "eligible"),
        "already_current": current_count,
        "blocked": len(blocked),
        "applied": applied,
        "body_bytes_modified": 0,
        "model_calls": 0,
        "google_api_calls": 0,
        "public_release": False,
        "batch_fail_closed": bool(blocked),
        "excluded_false_positive": EXCLUDED_FALSE_POSITIVE,
        "current_policy_sha256": contract.policy_sha256(),
        "rows": rows,
    }
    _write_report(result)
    return result


def main() -> int:
    result = run(
        mode=os.environ.get("AIIF_RUN365_MODE", "dry_run"),
        confirmation=os.environ.get("AIIF_RUN365_CONFIRM", ""),
    )
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
