"""Run391: zero-model full-gate revalidation for the repaired Memmy manuscript.

Reconstruct the production pre-presentation draft from the latest stored manuscript,
validate it against current first-party evidence, then separately validate the stored
final Reader/Surface presentation. No model, Notion write, Ready sync, or publication.
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any

import requests

from run389_producthunt_surface_revalidation import (
    TARGETS,
    deterministic_runtime,
    evaluate_surface,
    select_latest_markdown_manuscript,
)

PAGE_ID = "3bc479ff-dca9-8116-a7e1-d1d7e2274f7d"
TITLE = "AIエージェントの「記憶」を中央集権化せよ：Memmy Agentの実用的判断"
PRIMARY_URL = "https://github.com/MemTensor/memmy-agent"
README_URL = "https://raw.githubusercontent.com/MemTensor/memmy-agent/main/README.md"
DOCS_URL = "https://memmy.bot/docs/en/start/getting-started/"
REPORT_PATH = Path("gate_history/run391_memmy_full_gate_revalidation.json")


def _plain_html(value: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", value or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch_first_party_evidence() -> tuple[str, list[dict[str, Any]]]:
    documents: list[dict[str, Any]] = []
    chunks: list[str] = []
    for url, kind in ((README_URL, "github_readme"), (DOCS_URL, "official_docs")):
        response = requests.get(url, timeout=20, headers={"User-Agent": "AIIF-Run391/1.0"})
        if response.status_code != 200:
            raise RuntimeError(f"first-party evidence fetch failed: {url} HTTP {response.status_code}")
        text = response.text if kind == "github_readme" else _plain_html(response.text)
        if len(text.strip()) < 500:
            raise RuntimeError(f"first-party evidence unexpectedly thin: {url}")
        chunks.append(f"SOURCE URL: {url}\n{text}")
        documents.append({"url": url, "text": text, "origin": kind})
    context = "\n\n".join(chunks)
    required = ("Claude Code", "Codex", "local", "trial", "API Key")
    missing = [token for token in required if token.lower() not in context.lower()]
    if missing:
        raise RuntimeError(f"first-party evidence contract drift: missing={missing}")
    return context, documents


def fetch_latest_manuscript() -> tuple[str, dict[str, Any]]:
    import note_ready_sync as sync

    page = sync._request("GET", f"https://api.notion.com/v1/pages/{PAGE_ID}")
    if page.status_code != 200:
        raise RuntimeError(f"Notion page fetch failed HTTP {page.status_code}")
    state = sync._source_state(page.json())
    if not state:
        raise RuntimeError("Notion source state unavailable")
    if state.get("title") != TITLE or state.get("source") != "GitHub":
        raise RuntimeError(f"metadata mismatch: title={state.get('title')} source={state.get('source')}")
    if str(state.get("primary_url") or "").rstrip("/") != PRIMARY_URL.rstrip("/"):
        raise RuntimeError(f"primary URL drift: {state.get('primary_url')}")
    manuscript, caption, count = select_latest_markdown_manuscript(sync._block_children(PAGE_ID))
    return manuscript, {
        "eyecatch_url": state.get("eyecatch_url") or "",
        "primary_url": state.get("primary_url") or "",
        "caption": caption,
        "markdown_candidate_count": count,
    }


def reconstruct_pre_presentation_draft(manuscript: str) -> str:
    """Undo only deterministic final-presentation layers added after Quality Gate.

    Production runs Fact/Editorial/Publication/Human gates before build_clean_note_manuscript
    adds the H1, Reader-first 30-second header and final Sources/Evidence presentation.
    The business article body is preserved verbatim.
    """
    text = str(manuscript or "").strip()
    text = re.sub(r"(?m)^# [^\n]+\n+", "", text, count=1)
    text = re.sub(
        r"(?ms)^## 30秒でわかるこの記事\s*\n.*?(?=^## (?!30秒でわかるこの記事)|\Z)",
        "",
        text,
        count=1,
    )
    text = re.sub(r"(?ms)^## Sources / Evidence\s*\n.*\Z", "", text, count=1)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def build_source_info(context: str, documents: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source": "GitHub",
        "primary_url": PRIMARY_URL,
        "primary_source_resolved": True,
        "verification_context": context,
        "context": context,
        "freshness_status_available": True,
        "requested_action_risk_tier": "LOW",
        "numeric_claims_required": False,
        "actor_attribution_required": False,
        "deep_source_required": False,
        "deep_source_scanned": True,
        "decision_scope_safe": True,
        "evidence_supplement_attempted": True,
        "evidence_documents": documents,
        "checked_urls": {doc["url"] for doc in documents},
        "supplement_candidates": [],
        "evidence_metadata": {
            "coverage": {"method": "FOUND", "limitations": "FOUND"},
            "first_party_urls": [doc["url"] for doc in documents],
        },
    }


def build_parsed(core_draft: str) -> dict[str, Any]:
    return {
        "title_text": TITLE + "。",
        "note_draft": core_draft,
        "action_text": "まず1案件だけで、別のAIに替えても過去の決定を正しく思い出せるか試す。",
        "decision_text": "TRY",
        "score": 65,
        "decision_reason_text": "複数のAIを使い、そのたびに背景説明をやり直しているなら限定的に試す価値がある。",
        "source_summary_text": "Memmy Agentは複数のAIが同じ記憶を参照するためのlocal-firstなメモリ基盤を提供する。",
        "what_text": "複数のAIに同じ記憶を使わせるためのオープンソースツール。",
        "why_important_text": "AIを替えるたびに背景を説明し直す負担を減らせる可能性がある。",
    }


def run() -> dict[str, Any]:
    if len([t for t in TARGETS if t.page_id == PAGE_ID]) != 1:
        raise RuntimeError("Run391 target inventory drift")
    if not os.environ.get("NOTION_API_KEY"):
        raise RuntimeError("Run391 requires Notion read credential")

    manuscript, notion_meta = fetch_latest_manuscript()
    context, documents = fetch_first_party_evidence()
    source_info = build_source_info(context, documents)
    core_draft = reconstruct_pre_presentation_draft(manuscript)
    parsed = build_parsed(core_draft)

    with deterministic_runtime() as pipeline:
        evidence_result = pipeline.assess_evidence_sufficiency(source_info)
        evidence_ok = str(evidence_result.get("state")) == str(getattr(pipeline, "EVIDENCE_SUFFICIENT", "SUFFICIENT"))
        source_info["sufficient"] = evidence_ok
        source_info["decision_scope_safe"] = bool(evidence_result.get("decision_scope_safe"))
        freshness = {"status": "CURRENT_FIRST_PARTY_RECHECKED", "current": True, "checked": True}

        fact_ok, fact_failures = pipeline.validate_fact_gate(
            parsed,
            "MemTensor/memmy-agent",
            source_context=context,
            source="GitHub",
            evidence_metadata=source_info["evidence_metadata"],
            source_info=source_info,
            freshness=freshness,
            output_truncated=False,
        )
        editorial_ok, editorial_warnings = pipeline.validate_editorial_gate(parsed, "MemTensor/memmy-agent")
        publication_state, publication_issues = pipeline.validate_publication_readiness_gate(parsed, context, source_info)
        human_state, human_issues = pipeline.validate_human_appeal_gate(parsed, [])
        reason_rows = (
            pipeline.map_gate_reasons("fact", fact_failures)
            + pipeline.map_gate_reasons("editorial", editorial_warnings)
            + pipeline.map_gate_reasons("publication", publication_issues)
            + pipeline.map_gate_reasons("human_appeal", human_issues)
        )
        disposition = pipeline.gate_reason_disposition(reason_rows)
        quality_ok = disposition in {pipeline.GATE_DISPOSITION_PASS, pipeline.GATE_DISPOSITION_PASS_WITH_WARNINGS}
        surface = evaluate_surface(TITLE, manuscript, pipeline)

    surface_ok = surface.get("state") == "SURFACE_CLEAN_BODY_REGROUND_PROOF_REQUIRED"
    eyecatch_ok = bool(notion_meta.get("eyecatch_url"))
    full_gate_proven = all((evidence_ok, quality_ok, surface_ok, eyecatch_ok))

    blockers: list[str] = []
    if not evidence_ok:
        blockers.append(f"evidence:{evidence_result.get('state')}")
    if not quality_ok:
        blockers.extend(
            f"{row.get('gate')}:{row.get('reason_code')}:{row.get('message')}"
            for row in reason_rows
            if row.get("message")
        )
    if not surface_ok:
        blockers.extend(f"surface:{x}" for x in surface.get("issues") or [])
    if not eyecatch_ok:
        blockers.append("eyecatch_missing")

    result = {
        "run": "run391_memmy_full_gate_revalidation",
        "title": TITLE,
        "page_id": PAGE_ID,
        "full_gate_proven": full_gate_proven,
        "ready_write_performed": False,
        "model_calls": 0,
        "google_api_calls": 0,
        "notion_writes": 0,
        "publication_writes": 0,
        "note_ready_sync": False,
        "checks": {
            "evidence_ok": evidence_ok,
            "evidence": evidence_result,
            "fact_ok": fact_ok,
            "fact_failures": fact_failures,
            "editorial_ok": editorial_ok,
            "editorial_warnings": editorial_warnings,
            "publication_state": publication_state,
            "publication_issues": publication_issues,
            "human_state": human_state,
            "human_issues": human_issues,
            "quality_disposition": disposition,
            "quality_ok": quality_ok,
            "reason_rows": reason_rows,
            "surface_state": surface.get("state"),
            "surface_issues": surface.get("issues") or [],
            "eyecatch_ok": eyecatch_ok,
        },
        "blockers": blockers,
        "evidence_urls": [README_URL, DOCS_URL],
        "manuscript_sha256": surface.get("manuscript_sha256"),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=list), encoding="utf-8")
    return result


def main() -> int:
    result = run()
    checks = result["checks"]
    print(f"RUN391_FULL_GATE_PROVEN={str(result['full_gate_proven']).lower()}")
    print(f"RUN391_EVIDENCE_OK={str(checks['evidence_ok']).lower()} state={checks['evidence'].get('state')}")
    print(f"RUN391_FACT_OK={str(checks['fact_ok']).lower()} failures={checks['fact_failures']}")
    print(f"RUN391_EDITORIAL_OK={str(checks['editorial_ok']).lower()} warnings={checks['editorial_warnings']}")
    print(f"RUN391_PUBLICATION={checks['publication_state']} issues={checks['publication_issues']}")
    print(f"RUN391_HUMAN={checks['human_state']} issues={checks['human_issues']}")
    print(f"RUN391_QUALITY_DISPOSITION={checks['quality_disposition']} quality_ok={str(checks['quality_ok']).lower()}")
    print(f"RUN391_SURFACE={checks['surface_state']} issues={checks['surface_issues']}")
    print(f"RUN391_EYECATCH_OK={str(checks['eyecatch_ok']).lower()}")
    print(f"RUN391_BLOCKERS={result['blockers']}")
    print("RUN391_MODEL_CALLS=0")
    print("RUN391_NOTION_WRITES=0")
    print("RUN391_PUBLICATION_WRITES=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
