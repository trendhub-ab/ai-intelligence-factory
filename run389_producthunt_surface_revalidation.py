"""Run389: read-only deterministic surface revalidation for five migrated ProductHunt rows.

This lane intentionally proves only current Reader/Surface status of the latest stored
manuscript. A surface-clean result never proves Fact/Evidence, body re-grounding,
eyecatch quality, Publication Contract, or Ready eligibility.

Network scope is limited to Notion Public API GETs. No Gemini/provider calls, Notion
writes, Note Ready sync, draft creation, or publication actions are present.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from unittest.mock import patch


@dataclass(frozen=True)
class Target:
    page_id: str
    title: str
    source: str


TARGETS = (
    Target("3bc479ff-dca9-8116-a7e1-d1d7e2274f7d", "AIエージェントの「記憶」を中央集権化せよ：Memmy Agentの実用的判断", "GitHub"),
    Target("3bc479ff-dca9-815a-a6d3-d08da120a7bb", "Wispr Flow Notetaker：会議後の「コピペ作業」を根絶するMCP時代の議事録最適化戦略", "OfficialVendor"),
    Target("3bc479ff-dca9-8191-859c-c6ace77dcfdd", "SaaS依存から解放されるか：音声AI開発における「Dograh」の現実的な評価と導入戦略", "OfficialVendor"),
    Target("3bc479ff-dca9-81cb-905d-f6f5452c66e5", "AI検索で自社が「無視」されていないかを確認する技術：AI Search Consoleの導入判断", "OfficialVendor"),
    Target("3c4479ff-dca9-81b6-813b-cd544200f14a", "仕様書とコードの乖離をどう防ぐか。ビジネスロジック統合エンジン「GoRules」の登場から考える。", "OfficialVendor"),
)

REPORT_PATH = Path("gate_history/run389_producthunt_surface_revalidation.json")


def select_latest_markdown_manuscript(blocks: list[dict[str, Any]]) -> tuple[str, str, int]:
    """Return the latest substantial markdown code body; fail closed if none exists."""
    candidates: list[tuple[str, str]] = []
    for block in blocks:
        if block.get("type") != "code":
            continue
        code = block.get("code") or {}
        language = str(code.get("language") or "").lower()
        if language not in {"markdown", "md"}:
            continue
        body = "".join(
            str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
            for item in (code.get("rich_text") or [])
        )
        caption = "".join(
            str(item.get("plain_text") or ((item.get("text") or {}).get("content")) or "")
            for item in (code.get("caption") or [])
        )
        if len(body.strip()) < 500 or not re.search(r"(?m)^#{2,3}\s+", body):
            continue
        candidates.append((body, caption))
    if not candidates:
        raise RuntimeError("no substantial markdown manuscript block")
    body, caption = candidates[-1]
    return body, caption, len(candidates)


def partition_article_body(manuscript: str) -> str:
    """Match Run367's historical-manuscript partition without rewriting text."""
    body = str(manuscript or "")
    if "### 元情報\n" in body:
        _prefix, rest = body.split("### 元情報\n", 1)
        boundary = re.search(r"\n\n(?=[^-\n])", rest)
        if boundary:
            body = rest[boundary.end():]
    else:
        body = re.sub(r"^# [^\n]+\n+", "", body)
    body = re.split(r"\n(?:---\n+)?### Sources / Evidence\b", body, maxsplit=1)[0]
    return body.strip()


def current_presentation_contract_present(manuscript: str) -> bool:
    text = str(manuscript or "")
    return all(token in text for token in ("## 30秒でわかるこの記事", "**何が出た？**", "**なぜ重要？**", "**結論は？**"))


@contextmanager
def deterministic_runtime():
    """Install the current quality stack while forbidding provider/network use during gates."""
    with patch.dict(os.environ, {
        "SYNTHETIC_REGRESSION_MODE": "true",
        "GEMINI_API_KEY": "RUN389_DISABLED",
        "GH_PAT": "RUN389_DISABLED",
        "GEMINI_QUOTA_PROJECT_ID": "RUN389_DISABLED",
    }):
        import pipeline
        import production_pipeline
        production_pipeline.install_runtime_layers(pipeline)

        def blocked(*_args, **_kwargs):
            raise RuntimeError("Run389 deterministic gate phase forbids network/provider calls")

        with patch("requests.sessions.Session.request", blocked), \
             patch("socket.socket.connect", blocked), \
             patch("socket.create_connection", blocked):
            yield pipeline


def evaluate_surface(title: str, manuscript: str, pipeline) -> dict[str, Any]:
    """Apply current deterministic body Reader + Run248/249 high-confidence surface checks."""
    from reader_value_review_bridge import _material_reader_value_issues
    from run248_first_real_publish_quality_calibration import extra_reader_value_issues
    import run249_final_publication_surface_gate as surface

    body = partition_article_body(manuscript)
    signals = pipeline._reader_experience_signals(body)
    issues: list[str] = []
    issues += _material_reader_value_issues(pipeline, body)
    issues += extra_reader_value_issues(signals)
    title_issue = surface._unbalanced_japanese_quote_issue(title)
    if title_issue:
        issues.append(title_issue)
    issues += surface._extra_japanese_surface_failures(manuscript)

    presentation_current = current_presentation_contract_present(manuscript)
    if not presentation_current:
        issues.append("presentation_contract_missing:reader_first_30sec_header")

    issues = list(dict.fromkeys(issues))
    if issues:
        state = "SURFACE_REVIEW"
    else:
        state = "SURFACE_CLEAN_BODY_REGROUND_PROOF_REQUIRED"
    return {
        "state": state,
        "issues": issues,
        "reader_signals": signals,
        "presentation_contract_current": presentation_current,
        "manuscript_sha256": hashlib.sha256(manuscript.encode("utf-8")).hexdigest(),
        "manuscript_chars": len(manuscript),
        "body_chars": len(body),
        "full_fact_evidence_gate_proven": False,
        "ready_eligible": False,
    }


def _read_target(sync, target: Target) -> dict[str, Any]:
    page = sync._request("GET", f"https://api.notion.com/v1/pages/{target.page_id}")
    if page.status_code != 200:
        return {"page_id": target.page_id, "title": target.title, "state": "FETCH_BLOCKED", "reason": f"page_http_{page.status_code}"}
    state = sync._source_state(page.json())
    if not state:
        return {"page_id": target.page_id, "title": target.title, "state": "FETCH_BLOCKED", "reason": "source_state_not_ready_or_supported"}
    if state.get("title") != target.title or state.get("source") != target.source:
        return {
            "page_id": target.page_id, "title": target.title, "state": "FETCH_BLOCKED",
            "reason": "metadata_mismatch", "actual_title": state.get("title"), "actual_source": state.get("source"),
        }
    if not state.get("primary_url"):
        return {"page_id": target.page_id, "title": target.title, "state": "FETCH_BLOCKED", "reason": "primary_url_missing"}

    recovery_blockers: list[str] = []
    if not state.get("eyecatch_url"):
        recovery_blockers.append("eyecatch_missing")
    try:
        manuscript, caption, candidate_count = select_latest_markdown_manuscript(sync._block_children(target.page_id))
    except Exception as exc:
        return {"page_id": target.page_id, "title": target.title, "state": "FETCH_BLOCKED", "reason": str(exc)}
    return {
        "page_id": target.page_id,
        "title": target.title,
        "source": target.source,
        "primary_url": state.get("primary_url"),
        "eyecatch_url": state.get("eyecatch_url") or "",
        "recovery_blockers": recovery_blockers,
        "manuscript": manuscript,
        "caption": caption,
        "markdown_candidate_count": candidate_count,
    }


def run() -> dict[str, Any]:
    if len(TARGETS) != 5 or len({t.page_id for t in TARGETS}) != 5:
        raise RuntimeError("Run389 exact five-target inventory drift")
    import note_ready_sync as sync
    if not sync.NOTION_API_KEY:
        raise RuntimeError("Run389 requires Notion read credential")

    fetched = [_read_target(sync, target) for target in TARGETS]
    rows: list[dict[str, Any]] = []
    with deterministic_runtime() as pipeline:
        for item in fetched:
            if item.get("state") == "FETCH_BLOCKED":
                rows.append(item)
                continue
            verdict = evaluate_surface(item["title"], item["manuscript"], pipeline)
            row = {k: v for k, v in item.items() if k not in {"manuscript"}} | verdict
            if row.get("recovery_blockers"):
                row["ready_eligible"] = False
            rows.append(row)

    counts: dict[str, int] = {}
    blocker_counts: dict[str, int] = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
        for blocker in row.get("recovery_blockers") or []:
            blocker_counts[blocker] = blocker_counts.get(blocker, 0) + 1
    result = {
        "run": "run389_producthunt_surface_revalidation",
        "targets": 5,
        "counts": dict(sorted(counts.items())),
        "recovery_blockers": dict(sorted(blocker_counts.items())),
        "model_calls": 0,
        "google_api_calls": 0,
        "notion_writes": 0,
        "publication_writes": 0,
        "note_ready_sync": False,
        "full_gate_proven": False,
        "rows": rows,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    result = run()
    print(f"RUN389_COUNTS={result['counts']}")
    print(f"RUN389_BLOCKERS={result['recovery_blockers']}")
    for row in result["rows"]:
        detail = ";".join(row.get("issues") or []) or row.get("reason", "")
        blockers = ",".join(row.get("recovery_blockers") or [])
        print(f"RUN389_ROW\t{row['state']}\t{row['title']}\t{detail}\tblockers={blockers}")
    print("RUN389_MODEL_CALLS=0")
    print("RUN389_NOTION_WRITES=0")
    print("RUN389_PUBLICATION_WRITES=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
