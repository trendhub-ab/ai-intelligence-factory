"""Isolated, fixed-evidence Ready eligibility experiment.

No production stores, note endpoints, or user-facing publication are touched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

# GitHub Actions executes this file by path from experiments/, whereas production
# modules live at repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


EVIDENCE_URL = "https://github.com/astral-sh/uv/blob/dd965a276182e2d46d80439feecd03216cc6643a/README.md"
EVIDENCE = """Primary source: astral-sh/uv README at dd965a276182e2d46d80439feecd03216cc6643a.
uv is a Python package and project manager written in Rust. The README describes a universal
lockfile, Python version installation and management, dependency and environment management,
script execution with inline dependency metadata, a pip-compatible interface, Cargo-style
workspaces, and a global cache. It supports macOS, Linux and Windows. The README advertises
10–100x faster performance than pip and points to BENCHMARKS.md; this is the author's claim
and is not an independently confirmed general speed guarantee. The README describes dual
Apache-2.0 and MIT licenses. The cited README gives no independently verified benchmark for
the reader's workload and no assurance of migration compatibility for a particular project.
Any recommended action must be a limited comparison or test, not an immediate full migration.
"""
REPO = {
    "nameWithOwner": "astral-sh/uv", "url": "https://github.com/astral-sh/uv",
    "primaryUrl": EVIDENCE_URL, "source": "GitHub", "stargazerCount": 0,
    "licenseInfo": {"spdxId": "MIT"},
    "description": "Python package and project manager written in Rust.",
}
MODELS = ("gemini-3.6-flash", "gemini-3.5-flash")
STYLES = ("classic", "human_narrative", "duo_narrative", "minimal")


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def install_production_gates():
    import pipeline as p
    import production_pipeline

    # The same installer order as the production entrypoint, while bypassing its
    # operational main, runtime-state writes, and all production persistence.
    original = p.main
    p.main = lambda: None
    try:
        production_pipeline.main()
    finally:
        p.main = original
    return p


def source_info(p):
    metadata = p._build_evidence_metadata(EVIDENCE, False)
    return {
        "primary_source_resolved": True, "primary_url": EVIDENCE_URL,
        "context": EVIDENCE, "verification_context": EVIDENCE,
        "method": p.GROUNDING_SOURCE_NATIVE, "source": "GitHub",
        "source_details": {}, "supplement_candidates": [],
        "evidence_documents": [{"url": EVIDENCE_URL, "retrieved": True}],
        "evidence_urls": [EVIDENCE_URL], "deep_source_scanned": False,
        "evidence_metadata": metadata,
        "requested_action_risk_tier": "LOW",
    }


def gate_result(p, parsed, info, *, truncated=False):
    fact, fact_reasons = p.validate_fact_gate(
        parsed, REPO["nameWithOwner"], source_context=EVIDENCE,
        source="GitHub", evidence_metadata=info["evidence_metadata"],
        source_info=info, freshness={}, output_truncated=truncated,
    )
    editorial, editorial_reasons = p.validate_editorial_gate(parsed, REPO["nameWithOwner"])
    publication, publication_reasons = p.validate_publication_readiness_gate(parsed, EVIDENCE, info)
    reader, reader_reasons = p.validate_human_appeal_gate(parsed, [])
    rows = sum((p.map_gate_reasons(k, v) for k, v in (
        ("fact", fact_reasons), ("editorial", editorial_reasons),
        ("publication", publication_reasons), ("human_appeal", reader_reasons))), [])
    disposition = p.gate_reason_disposition(rows)
    ready_eligible = disposition in {p.GATE_DISPOSITION_PASS, p.GATE_DISPOSITION_PASS_WITH_WARNINGS}
    return {
        "evidence": info["evidence_result"]["state"],
        "fact": {"pass": fact, "reasons": fact_reasons},
        "editorial": {"pass": editorial, "reasons": editorial_reasons},
        "publication": {"state": publication, "reasons": publication_reasons},
        "reader_value": {"state": reader, "reasons": reader_reasons},
        "reason_rows": rows, "disposition": disposition,
        "ready_eligible_before_persistence": ready_eligible,
    }


def prompt_for(p, style: str, feedback: str = "", previous: str = "") -> str:
    p.AIIF_EDITORIAL_STYLE = "classic" if style == "minimal" else style
    prompt = p.build_decision_prompt(
        REPO["nameWithOwner"], EVIDENCE_URL, 0, REPO["description"],
        quality_feedback=feedback, source="GitHub", source_context=EVIDENCE,
        evidence_metadata=p._build_evidence_metadata(EVIDENCE, False),
        freshness={}, previous_article=previous,
        evidence_result=p.assess_evidence_sufficiency(source_info(p)),
    )
    if style == "minimal":
        # Keep the production output schema and evidence boundaries, but replace
        # narrative style requests with one explicit concise editorial condition.
        prompt += "\n【実験条件: Evidence中心】事実の出典と未検証条件を明確にし、脚色せず、指定の出力形式を守る。"
    return prompt


def evaluate(p, raw: str, info):
    parsed = p._parse_gemini_response(raw)
    parsed_before_polish = parsed.get("note_draft", "")
    parsed, jp_changes = p._apply_final_japanese_polish(parsed)
    parsed, structure_changes = p._apply_deterministic_structure_polish(parsed)
    parsed["grounding_status"] = p.GROUNDING_SOURCE_NATIVE
    parsed["evidence_urls_text"] = EVIDENCE_URL
    action = p.classify_action_risk_tier(parsed.get("action_text", ""))
    current_info = dict(info)
    current_info["requested_action_risk_tier"] = action
    current_info["evidence_result"] = p.assess_evidence_sufficiency(current_info)
    result = gate_result(p, parsed, current_info)
    rescue = None
    if not result["ready_eligible_before_persistence"]:
        hard = p._reason_rows_by_severity(result["reason_rows"], p.GATE_SEVERITY_HARD)
        if hard:
            rescued, changes = p._apply_deterministic_publication_rescue(parsed, hard)
            if changes:
                ok, diag = p._publication_rescue_can_be_ready(
                    rescued, EVIDENCE, "GitHub", current_info["evidence_metadata"],
                    current_info, {}, peer_articles=[],
                )
                rescue = {
                    "changes": changes, "body": rescued.get("note_draft", ""),
                    "body_sha256": sha(rescued.get("note_draft", "")),
                    "ready_eligible": bool(ok and not rescued.get("_rescue_loss", {}).get("loss_exceeded")),
                    "diagnostics": diag,
                    "new_reason_codes": sorted(set(r.get("reason_code") for r in diag["reason_rows"])
                                               - set(r.get("reason_code") for r in result["reason_rows"])),
                }
    return {
        "raw_response": raw, "raw_sha256": sha(raw),
        "body_before_polish": parsed_before_polish,
        "body_after_polish": parsed.get("note_draft", ""),
        "polish_changes": jp_changes, "structure_changes": structure_changes,
        "gate": result, "rescue": rescue,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("preflight", "initial", "feedback"), required=True)
    parser.add_argument("--model", choices=MODELS)
    parser.add_argument("--in-dir", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.phase != "preflight" and not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY missing: zero provider sends")
    p = install_production_gates()
    info = source_info(p)
    evidence = p.assess_evidence_sufficiency(info)
    info["evidence_result"] = evidence
    info["sufficient"] = evidence["state"] == p.EVIDENCE_SUFFICIENT
    info["decision_scope_safe"] = evidence.get("decision_scope_safe", False)
    if not info["sufficient"]:
        raise RuntimeError(f"Frozen Evidence insufficient: {evidence}; zero provider sends")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.phase == "preflight":
        (args.out_dir / "preflight.json").write_text(json.dumps({
            "evidence_state": evidence["state"], "evidence_sha256": sha(EVIDENCE),
            "evidence_url": EVIDENCE_URL, "provider_sends": 0,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    rows = []
    if args.phase == "initial":
        if not args.model:
            parser.error("--model required for initial phase")
        conditions = [(style, repeat, args.model, "", "") for style in STYLES for repeat in (1, 2)]
    else:
        if not args.in_dir:
            parser.error("--in-dir required for feedback phase")
        records = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(args.in_dir.rglob("*.json"))]
        failures = [r for r in records if r.get("phase") == "initial" and not r.get("error")
                    and not r["initial"]["gate"]["ready_eligible_before_persistence"]]
        conditions = []
        for row in failures[:8]:
            reasons = [r["message"] for r in row["initial"]["gate"]["reason_rows"]
                       if r.get("severity") in {p.GATE_SEVERITY_HARD, p.GATE_SEVERITY_REVIEW}]
            if reasons:
                conditions.append((row["style"], row["repeat"], row["model"], " / ".join(reasons), row["initial"]["body_after_polish"]))
    for style, repeat, model, feedback, previous in conditions:
        ident = f"{model}_{style}_{repeat}"
        row = {"id": ident, "model": model, "style": style, "repeat": repeat,
               "phase": args.phase, "evidence_url": EVIDENCE_URL, "evidence_sha256": sha(EVIDENCE)}
        try:
            prompt = prompt_for(p, style, feedback, previous)
            from canonical_article_contract import aiif_editor_persona
            config = {"max_output_tokens": p.GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS,
                      "system_instruction": aiif_editor_persona()}
            response = p._generate_via_chat(model, prompt, config=config,
                         request_kind="deep_dive" if args.phase == "initial" else "quality_retry",
                         request_context="experiment:ready-yield-fixed-evidence",
                         count_as_deep_dive=True)
            row["prompt_sha256"] = sha(prompt)
            row["feedback"] = feedback
            row[args.phase] = evaluate(p, response.text or "", info)
        except Exception as exc:
            row["error"] = {"type": type(exc).__name__, "message": str(exc)[:1000]}
        (args.out_dir / f"{ident}.json").write_text(json.dumps(row, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        rows.append(row)
    (args.out_dir / "summary.json").write_text(json.dumps({
        "phase": args.phase, "count": len(rows), "provider_errors": sum("error" in r for r in rows),
        "ready_eligible": sum(r.get(args.phase, {}).get("gate", {}).get("ready_eligible_before_persistence", False) for r in rows),
        "evidence_sha256": sha(EVIDENCE), "note_writes": 0, "notion_writes": 0,
        "actual_ready_persisted": 0,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if not rows and args.phase != "feedback":
        raise RuntimeError("No eligible cases; zero provider sends")


if __name__ == "__main__":
    main()
