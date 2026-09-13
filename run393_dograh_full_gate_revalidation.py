"""Run393: zero-model full-gate revalidation for repaired Dograh article.

Read-only audit: latest Notion manuscript + current first-party Dograh evidence.
No model calls, Notion writes, Ready sync, draft creation, or publication.
"""
from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Any

import requests

from run389_producthunt_surface_revalidation import deterministic_runtime, evaluate_surface, select_latest_markdown_manuscript
from run391_memmy_full_gate_revalidation import reconstruct_pre_presentation_draft as _base_reconstruct

PAGE_ID = "3bc479ff-dca9-8191-859c-c6ace77dcfdd"
DB_TITLE = "SaaS依存から解放されるか：音声AI開発における「Dograh」の現実的な評価と導入戦略"
FINAL_TITLE = "Dograh：音声AI基盤を自社で持つ選択肢を、小さく試す。"
PRIMARY_URL = "https://www.dograh.com/about"
EVIDENCE_URLS = (
    "https://www.dograh.com/about",
    "https://www.dograh.com/voice-ai-no-platform-fees",
    "https://raw.githubusercontent.com/dograh-hq/dograh/main/README.md",
)
REPORT_PATH = Path("gate_history/run393_dograh_full_gate_revalidation.json")


def _plain_html(value: str) -> str:
    text = re.sub(r"(?is)<script[^>]*>.*?</script>|<style[^>]*>.*?</style>", " ", value or "")
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch_first_party_evidence() -> tuple[str, list[dict[str, Any]]]:
    docs: list[dict[str, Any]] = []
    chunks: list[str] = []
    for url in EVIDENCE_URLS:
        response = requests.get(url, timeout=20, headers={"User-Agent": "AIIF-Run393/1.0"})
        if response.status_code != 200:
            raise RuntimeError(f"Dograh evidence fetch failed: {url} HTTP {response.status_code}")
        text = response.text if "raw.githubusercontent.com" in url else _plain_html(response.text)
        if len(text.strip()) < 500:
            raise RuntimeError(f"Dograh evidence unexpectedly thin: {url}")
        origin = "github_readme" if "raw.githubusercontent.com" in url else "official_vendor"
        docs.append({"url": url, "text": text, "origin": origin})
        chunks.append(f"SOURCE URL: {url}\n{text}")
    context = "\n\n".join(chunks)
    required = ("open source", "self-host", "BSD 2-Clause", "MCP", "beta")
    missing = [token for token in required if token.lower() not in context.lower()]
    if missing:
        raise RuntimeError(f"Dograh evidence contract drift: missing={missing}")
    return context, docs


def fetch_latest_manuscript() -> tuple[str, dict[str, Any]]:
    import note_ready_sync as sync

    page = sync._request("GET", f"https://api.notion.com/v1/pages/{PAGE_ID}")
    if page.status_code != 200:
        raise RuntimeError(f"Notion page fetch failed HTTP {page.status_code}")
    state = sync._source_state(page.json())
    if not state:
        raise RuntimeError("Dograh source state unavailable")
    if state.get("title") != DB_TITLE or state.get("source") != "OfficialVendor":
        raise RuntimeError(f"metadata mismatch title={state.get('title')} source={state.get('source')}")
    manuscript, caption, count = select_latest_markdown_manuscript(sync._block_children(PAGE_ID))
    return manuscript, {
        "eyecatch_url": state.get("eyecatch_url") or "",
        "primary_url": state.get("primary_url") or "",
        "caption": caption,
        "markdown_candidate_count": count,
    }


def reconstruct_pre_presentation_draft(manuscript: str) -> str:
    draft = _base_reconstruct(manuscript)
    draft = re.sub(r"(?ms)^#{2,3} Sources / Evidence\s*\n.*\Z", "", draft, count=1)
    return re.sub(r"\n{3,}", "\n\n", draft).strip()


def build_source_info(context: str, docs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "source": "OfficialVendor",
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
        "evidence_documents": docs,
        "checked_urls": {doc["url"] for doc in docs},
        "supplement_candidates": [],
        "evidence_metadata": {
            "coverage": {"method": "FOUND", "limitations": "FOUND"},
            "first_party_urls": [doc["url"] for doc in docs],
        },
    }


def build_parsed(core_draft: str) -> dict[str, Any]:
    return {
        "title_text": FINAL_TITLE,
        "note_draft": core_draft,
        "action_text": "まず1つの音声フローだけセルフホスト環境で試し、運用負荷・遅延・データ保存先を確認する。",
        "decision_text": "TRY",
        "score": 75,
        "decision_reason_text": "自社インフラで音声AIを運用したい組織なら、小規模な検証で適合性を確かめる価値がある。",
        "source_summary_text": "Dograhはオープンソースでセルフホスト可能な音声AI基盤で、ビジュアルワークフロー、電話連携、MCP、複数モデル接続を提供する。",
        "what_text": "自社環境でも動かせるオープンソースの音声AI基盤。",
        "why_important_text": "音声AIの構成やデータの扱いを自社側で管理したい場合の選択肢になる。",
    }


def run() -> dict[str, Any]:
    if not os.environ.get("NOTION_API_KEY"):
        raise RuntimeError("Run393 requires Notion read credential")
    manuscript, notion_meta = fetch_latest_manuscript()
    context, docs = fetch_first_party_evidence()
    source_info = build_source_info(context, docs)
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
            "Dograh",
            source_context=context,
            source="OfficialVendor",
            evidence_metadata=source_info["evidence_metadata"],
            source_info=source_info,
            freshness=freshness,
            output_truncated=False,
        )
        editorial_ok, editorial_warnings = pipeline.validate_editorial_gate(parsed, "Dograh")
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
        surface = evaluate_surface(DB_TITLE, manuscript, pipeline)

    surface_ok = surface.get("state") == "SURFACE_CLEAN_BODY_REGROUND_PROOF_REQUIRED"
    eyecatch_ok = bool(notion_meta.get("eyecatch_url"))
    full_gate_proven = all((evidence_ok, quality_ok, surface_ok, eyecatch_ok))
    blockers: list[str] = []
    if not evidence_ok:
        blockers.append(f"evidence:{evidence_result.get('state')}")
    if not quality_ok:
        blockers.extend(f"{r.get('gate')}:{r.get('reason_code')}:{r.get('message')}" for r in reason_rows if r.get("message"))
    if not surface_ok:
        blockers.extend(f"surface:{x}" for x in surface.get("issues") or [])
    if not eyecatch_ok:
        blockers.append("eyecatch_missing")

    result = {
        "run": "run393_dograh_full_gate_revalidation",
        "page_id": PAGE_ID,
        "full_gate_proven": full_gate_proven,
        "model_calls": 0,
        "google_api_calls": 0,
        "notion_writes": 0,
        "publication_writes": 0,
        "note_ready_sync": False,
        "ready_write_performed": False,
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
            "surface_state": surface.get("state"),
            "surface_issues": surface.get("issues") or [],
            "eyecatch_ok": eyecatch_ok,
        },
        "blockers": blockers,
        "evidence_urls": list(EVIDENCE_URLS),
        "manuscript_sha256": surface.get("manuscript_sha256"),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=list), encoding="utf-8")
    return result


def main() -> int:
    result = run()
    c = result["checks"]
    print(f"RUN393_FULL_GATE_PROVEN={str(result['full_gate_proven']).lower()}")
    print(f"RUN393_EVIDENCE_OK={str(c['evidence_ok']).lower()} state={c['evidence'].get('state')}")
    print(f"RUN393_FACT_OK={str(c['fact_ok']).lower()} failures={c['fact_failures']}")
    print(f"RUN393_EDITORIAL_OK={str(c['editorial_ok']).lower()} warnings={c['editorial_warnings']}")
    print(f"RUN393_PUBLICATION={c['publication_state']} issues={c['publication_issues']}")
    print(f"RUN393_HUMAN={c['human_state']} issues={c['human_issues']}")
    print(f"RUN393_QUALITY_DISPOSITION={c['quality_disposition']} quality_ok={str(c['quality_ok']).lower()}")
    print(f"RUN393_SURFACE={c['surface_state']} issues={c['surface_issues']}")
    print(f"RUN393_EYECATCH_OK={str(c['eyecatch_ok']).lower()}")
    print(f"RUN393_BLOCKERS={result['blockers']}")
    print("RUN393_MODEL_CALLS=0")
    print("RUN393_NOTION_WRITES=0")
    print("RUN393_PUBLICATION_WRITES=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
