"""Independent semantic judge for Technology comment Shadow comparison.

The judge receives only evidence plus anonymous Copy A/B. It never receives provider names,
Notion credentials, or write authority. It is advisory and can only veto/confirm a Shadow
comparison; automatic promotion remains impossible.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

import pipeline
import gemini_provider_resilience

from technology_comment_shadow import SHADOW_FIELDS


ALLOWED_MODELS = {"gemini-3.7-flash", "gemini-3.8-flash"}
AXES = ("specificity", "decision_usefulness", "evidence_alignment", "naturalness", "concision")


def _strip_json_fence(text: str) -> str:
    value = str(text or "").strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", value, re.S | re.I)
    return match.group(1).strip() if match else value


def _validate_scores(value: object) -> dict[str, int]:
    if not isinstance(value, dict) or set(value) != set(AXES):
        raise RuntimeError("semantic_judge_score_shape_invalid")
    result: dict[str, int] = {}
    for key in AXES:
        score = value[key]
        if type(score) is not int or not 0 <= score <= 100:
            raise RuntimeError("semantic_judge_score_range_invalid")
        result[key] = score
    return result


def _validate_judgment(raw: str) -> dict:
    try:
        data = json.loads(_strip_json_fence(raw))
    except Exception:
        raise RuntimeError("semantic_judge_json_invalid") from None
    required = {"unsupported_claims_A", "unsupported_claims_B", "scores_A", "scores_B", "winner", "reason"}
    if not isinstance(data, dict) or set(data) != required:
        raise RuntimeError("semantic_judge_shape_invalid")
    for key in ("unsupported_claims_A", "unsupported_claims_B"):
        rows = data[key]
        if not isinstance(rows, list) or any(not isinstance(row, str) or not row.strip() for row in rows):
            raise RuntimeError("semantic_judge_unsupported_claims_invalid")
        if len(rows) > 8:
            raise RuntimeError("semantic_judge_too_many_claims")
    data["scores_A"] = _validate_scores(data["scores_A"])
    data["scores_B"] = _validate_scores(data["scores_B"])
    if data["winner"] not in {"A", "B", "TIE"}:
        raise RuntimeError("semantic_judge_winner_invalid")
    if not isinstance(data["reason"], str) or not data["reason"].strip() or len(data["reason"]) > 500:
        raise RuntimeError("semantic_judge_reason_invalid")
    return data


def run(fixture_path: str, groq_report_path: str, output_path: str) -> dict:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    groq_report = json.loads(Path(groq_report_path).read_text(encoding="utf-8"))
    if fixture.get("source") != "synthetic_public_validation":
        raise RuntimeError("semantic_judge_public_synthetic_fixture_required")
    if groq_report.get("persist_allowed") is not False or groq_report.get("business_writes") != 0:
        raise RuntimeError("semantic_judge_requires_zero_write_shadow")

    baseline = fixture["baseline"]
    challenger = groq_report["challenger"]
    if set(baseline) != set(SHADOW_FIELDS) or set(challenger) != set(SHADOW_FIELDS):
        raise RuntimeError("semantic_judge_copy_shape_invalid")

    # Deterministic blind ordering prevents provider identity and fixed A/B position from
    # influencing the judge. The mapping is recovered only after the model returns.
    swap = int(hashlib.sha256(str(fixture["candidate_id"]).encode("utf-8")).hexdigest()[-1], 16) % 2 == 1
    copy_a, copy_b = (challenger, baseline) if swap else (baseline, challenger)
    challenger_label = "A" if swap else "B"
    baseline_label = "B" if swap else "A"

    prompt = f"""You are an independent quality and factual-boundary auditor for a Japanese paid intelligence database.
Provider identities are intentionally hidden. Judge Copy A and Copy B only from the evidence and text.

EVIDENCE is the sole factual surface. A statement is unsupported if it introduces a capability, failure mode,
usage condition, performance dimension, cost effect, production property, duration, causal claim, or certainty
that is not stated or directly entailed by EVIDENCE. Decision language may be cautious, but it must not create facts.

Score both copies 0-100 on exactly five axes:
- specificity: concrete and tied to the actual evidence rather than generic wording
- decision_usefulness: helps a reader decide where to use, avoid, test, or defer
- evidence_alignment: no unsupported factual expansion and preserves uncertainty/scope
- naturalness: concise natural Japanese suitable for a professional paid database
- concision: dense 1-2 sentence product copy without padding

Important rules:
- Do not reward extra detail when the extra detail is unsupported.
- Treat ties as TIE; do not force a winner.
- List each materially unsupported claim as a short string. Use [] when none.
- Ignore provider/model identity; none is supplied.
- Return one JSON object only with exactly these keys:
  unsupported_claims_A, unsupported_claims_B, scores_A, scores_B, winner, reason
- scores_A and scores_B must each contain exactly: {', '.join(AXES)} with integer 0-100 values.
- winner must be A, B, or TIE.
- reason must be <=500 characters.

EVIDENCE:
{json.dumps(fixture['evidence'], ensure_ascii=False)}

COPY A:
{json.dumps(copy_a, ensure_ascii=False)}

COPY B:
{json.dumps(copy_b, ensure_ascii=False)}
"""

    model = os.environ.get("AIIF_GEMINI_SHADOW_JUDGE_MODEL", "gemini-3.8-flash").strip()
    if model not in ALLOWED_MODELS:
        raise RuntimeError("semantic_judge_model_not_allowed")
    if not str(getattr(pipeline, "GEMINI_API_KEY", "") or "").strip():
        raise RuntimeError("GEMINI_API_KEY is required")

    gemini_provider_resilience.install(pipeline)
    if getattr(pipeline, "GEMINI_RETRY_OWNER", None) != "factory" or getattr(pipeline, "GEMINI_SDK_RETRY_ATTEMPTS", None) != 1:
        raise RuntimeError("semantic_judge_retry_contract_not_active")

    chat = pipeline.client.chats.create(
        model=model,
        config={"max_output_tokens": 1800, "temperature": 0, "response_mime_type": "application/json"},
    )
    response = chat.send_message(prompt)
    if response is None:
        raise RuntimeError("semantic_judge_no_response")
    judgment = _validate_judgment(str(getattr(response, "text", "") or ""))

    challenger_scores = judgment[f"scores_{challenger_label}"]
    baseline_scores = judgment[f"scores_{baseline_label}"]
    challenger_unsupported = judgment[f"unsupported_claims_{challenger_label}"]
    baseline_unsupported = judgment[f"unsupported_claims_{baseline_label}"]
    semantic_winner = (
        "challenger" if judgment["winner"] == challenger_label
        else "baseline" if judgment["winner"] == baseline_label
        else "tie"
    )
    challenger_total = sum(challenger_scores.values()) / len(AXES)
    baseline_total = sum(baseline_scores.values()) / len(AXES)
    semantic_gate = (
        not challenger_unsupported
        and semantic_winner == "challenger"
        and challenger_total >= baseline_total + 5
        and all(challenger_scores[key] >= baseline_scores[key] for key in AXES)
        and sum(challenger_scores[key] > baseline_scores[key] for key in AXES) >= 3
    )
    deterministic_gate = bool(groq_report.get("comparison", {}).get("deterministic_gate_passed"))
    combined_promotion_candidate = deterministic_gate and semantic_gate

    report = {
        "mode": "technology_comment_shadow_semantic_judge",
        "candidate_id": fixture["candidate_id"],
        "judge_provider": "gemini",
        "judge_model": model,
        "challenger_label": challenger_label,
        "baseline_label": baseline_label,
        "challenger_unsupported_claims": challenger_unsupported,
        "baseline_unsupported_claims": baseline_unsupported,
        "challenger_scores": challenger_scores,
        "baseline_scores": baseline_scores,
        "semantic_winner": semantic_winner,
        "semantic_reason": judgment["reason"],
        "semantic_gate_passed": semantic_gate,
        "deterministic_gate_passed": deterministic_gate,
        "combined_promotion_candidate": combined_promotion_candidate,
        "automatic_promotion_allowed": False,
        "persist_allowed": False,
        "business_writes": 0,
    }
    Path(output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    report = run(
        os.environ.get("AIIF_TECH_COMMENT_SHADOW_FIXTURE", "tests/fixtures/technology_comment_shadow_live.json"),
        os.environ.get("AIIF_TECH_COMMENT_SHADOW_REPORT", "technology-comment-shadow-live.json"),
        os.environ.get("AIIF_TECH_COMMENT_SEMANTIC_REPORT", "technology-comment-shadow-semantic.json"),
    )
    # No prose is printed: only aggregate verdicts/counts.
    print(json.dumps({
        "mode": report["mode"],
        "judge_model": report["judge_model"],
        "challenger_unsupported_claim_count": len(report["challenger_unsupported_claims"]),
        "baseline_unsupported_claim_count": len(report["baseline_unsupported_claims"]),
        "semantic_winner": report["semantic_winner"],
        "semantic_gate_passed": report["semantic_gate_passed"],
        "deterministic_gate_passed": report["deterministic_gate_passed"],
        "combined_promotion_candidate": report["combined_promotion_candidate"],
        "automatic_promotion_allowed": False,
        "business_writes": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
