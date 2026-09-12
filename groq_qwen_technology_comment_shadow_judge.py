"""Qwen cross-model semantic judge for Technology comment Shadow replay.

Generator and judge use different model families: GPT-OSS 120B generated the frozen
synthetic challenger; Qwen 3.6 27B judges anonymous A/B copies. This script has no
Notion credentials, no mutation code, and no promotion authority.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

from technology_comment_shadow import SHADOW_FIELDS


API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "qwen/qwen3.6-27b"
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


def _post(prompt: str) -> tuple[dict, dict]:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required")
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 1400,
        "reasoning_effort": "none",
        "reasoning_format": "hidden",
        "temperature": 0.2,
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ai-intelligence-factory-shadow-qwen-judge/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.loads(response.read().decode("utf-8")), {k.lower(): v for k, v in response.headers.items()}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"Qwen judge HTTP {exc.code}: {detail}") from None


def run(fixture_path: str, challenger_report_path: str, output_path: str) -> dict:
    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    challenger_report = json.loads(Path(challenger_report_path).read_text(encoding="utf-8"))
    if fixture.get("source") != "synthetic_public_validation":
        raise RuntimeError("semantic_judge_public_synthetic_fixture_required")
    if challenger_report.get("persist_allowed") is not False or challenger_report.get("business_writes") != 0:
        raise RuntimeError("semantic_judge_requires_zero_write_shadow")

    baseline = fixture["baseline"]
    challenger = challenger_report["challenger"]
    if set(baseline) != set(SHADOW_FIELDS) or set(challenger) != set(SHADOW_FIELDS):
        raise RuntimeError("semantic_judge_copy_shape_invalid")

    swap = int(hashlib.sha256(str(fixture["candidate_id"]).encode("utf-8")).hexdigest()[-1], 16) % 2 == 1
    copy_a, copy_b = (challenger, baseline) if swap else (baseline, challenger)
    challenger_label = "A" if swap else "B"
    baseline_label = "B" if swap else "A"

    prompt = f"""You are an independent factual-boundary and paid-product quality auditor.
The two Japanese copies are anonymous. Judge only from EVIDENCE and the texts. Do not infer provider identity.

EVIDENCE is the sole factual surface. A claim is unsupported if it adds a capability, failure mode, usage
condition, performance dimension, cost effect, production property, duration, causal claim, or certainty not
stated or directly entailed by EVIDENCE. Decision language may be cautious but must not create facts.

Score both copies 0-100 on exactly five axes:
- specificity: concrete and tied to actual evidence rather than generic wording
- decision_usefulness: helps decide where to use, avoid, test, or defer
- evidence_alignment: no unsupported factual expansion and preserves scope/uncertainty
- naturalness: concise natural Japanese suitable for a professional paid database
- concision: dense 1-2 sentence product copy without padding

Rules:
- Do not reward unsupported extra detail.
- Use TIE when materially tied.
- List every materially unsupported claim as a short string; [] when none.
- Return one JSON object only with exactly:
  unsupported_claims_A, unsupported_claims_B, scores_A, scores_B, winner, reason
- scores_A and scores_B contain exactly {', '.join(AXES)} with integer 0-100 values.
- winner is A, B, or TIE. reason <=500 characters.

EVIDENCE:
{json.dumps(fixture['evidence'], ensure_ascii=False)}

COPY A:
{json.dumps(copy_a, ensure_ascii=False)}

COPY B:
{json.dumps(copy_b, ensure_ascii=False)}
"""

    body, headers = _post(prompt)
    try:
        choice = body["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise RuntimeError(f"Qwen judge incomplete output: {choice.get('finish_reason')}")
        judgment = _validate_judgment(choice["message"]["content"])
        usage = body.get("usage") or {}
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Qwen judge malformed response") from None

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
    deterministic_gate = bool(challenger_report.get("comparison", {}).get("deterministic_gate_passed"))

    report = {
        "mode": "technology_comment_shadow_cross_model_judge",
        "candidate_id": fixture["candidate_id"],
        "generator_model": challenger_report.get("model"),
        "judge_provider": "groq",
        "judge_model": MODEL,
        "cross_model_family": True,
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
        "combined_promotion_candidate": deterministic_gate and semantic_gate,
        "automatic_promotion_allowed": False,
        "persist_allowed": False,
        "business_writes": 0,
        "usage": {
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        },
        "rate_headers": {
            k: v for k, v in headers.items()
            if k.startswith("x-ratelimit-") or k == "retry-after"
        },
    }
    Path(output_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    report = run(
        os.environ.get("AIIF_TECH_COMMENT_SHADOW_FIXTURE", "tests/fixtures/technology_comment_shadow_live.json"),
        os.environ.get("AIIF_TECH_COMMENT_SHADOW_REPORT", "tests/fixtures/technology_comment_shadow_groq_rerun.json"),
        os.environ.get("AIIF_TECH_COMMENT_QWEN_JUDGE_REPORT", "technology-comment-shadow-qwen-judge.json"),
    )
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
        "usage": report["usage"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
