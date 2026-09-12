"""Bounded, zero-write Groq raw-Screening shadow against production Run46 history.

This is deliberately a falsification harness, not a migration switch.
The Run46 observed history does not preserve candidate descriptions, so this runner
selects threshold-near production records, sends the SAME reduced metadata twice to
Groq, and measures decision stability against the historical raw-screening boundary.
Because input fidelity is incomplete, automatic/provider promotion is always forbidden.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.request

from screening_protocol import batch_screening_prompt, parse_batch_screening_response

API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = os.environ.get("AIIF_GROQ_SCREENING_MODEL", "openai/gpt-oss-120b").strip()
TRACKING_THRESHOLD = 55
PORTFOLIO_TOPICS = {"MODEL", "AGENT", "DEVTOOLS", "INFRA", "DATA", "SECURITY", "MULTIMODAL", "PRODUCT", "OTHER"}


def _post(prompt: str) -> tuple[str, dict]:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required")
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_completion_tokens": 3000,
        "reasoning_effort": "low",
        "reasoning_format": "hidden",
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ai-intelligence-factory-screening-shadow/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:1600]
        raise RuntimeError(f"Groq HTTP {exc.code}: {detail}") from None
    try:
        choice = body["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise RuntimeError(f"Groq incomplete output: {choice.get('finish_reason')}")
        return choice["message"]["content"], body.get("usage") or {}
    except (KeyError, IndexError, TypeError):
        raise RuntimeError("Groq malformed response") from None


def _select_threshold_near(items: list[dict], limit: int = 10) -> list[dict]:
    eligible = [row for row in items if isinstance(row.get("raw_screening_score"), int)]
    return sorted(
        eligible,
        key=lambda row: (abs(int(row["raw_screening_score"]) - TRACKING_THRESHOLD), str(row.get("id", ""))),
    )[:limit]


def _to_prompt_items(rows: list[dict]) -> list[dict]:
    result = []
    for row in rows:
        result.append({
            "screening_id": str(row["id"]),
            "repo": {
                "source": row.get("source", ""),
                "nameWithOwner": row.get("name", ""),
                # Run46 observed history does not preserve the original description.
                # Keep it explicitly empty; do not invent/reconstruct prose.
                "description": "",
                "stargazerCount": row.get("engagement", 0),
                "publishedAt": row.get("published_at"),
                "url": row.get("url", ""),
            },
        })
    return result


def _parse(text: str, ids: set[str]) -> tuple[dict[str, dict], list[str], str]:
    # Groq json_object mode can wrap the requested array in a single object. Fail closed
    # unless we can unwrap one unambiguous list value.
    try:
        root = json.loads(text)
        if isinstance(root, dict):
            lists = [value for value in root.values() if isinstance(value, list)]
            if len(lists) == 1:
                text = json.dumps(lists[0], ensure_ascii=False)
    except json.JSONDecodeError:
        pass
    return parse_batch_screening_response(
        text,
        ids,
        include_diagnostic=True,
        tracking_eligibility_min_score=TRACKING_THRESHOLD,
        portfolio_topics=PORTFOLIO_TOPICS,
    )


def _decision_map(parsed: dict[str, dict]) -> dict[str, bool]:
    return {candidate_id: int(row["score"]) >= TRACKING_THRESHOLD for candidate_id, row in parsed.items()}


def run(baseline_path: str, report_path: str, repeats: int = 2) -> dict:
    baseline = json.loads(Path(baseline_path).read_text(encoding="utf-8"))
    if baseline.get("run_id") != "20260912T020237Z" or baseline.get("total_screened") != 24:
        raise RuntimeError("unexpected_run46_baseline")
    rows = _select_threshold_near(baseline.get("items") or [], 10)
    if len(rows) != 10:
        raise RuntimeError("insufficient_threshold_near_records")

    prompt_items = _to_prompt_items(rows)
    ids = {item["screening_id"] for item in prompt_items}
    prompt = batch_screening_prompt(prompt_items)
    runs = []
    for index in range(repeats):
        raw, usage = _post(prompt)
        parsed, missing, diagnostic = _parse(raw, ids)
        runs.append({
            "index": index + 1,
            "scores": {candidate_id: row["score"] for candidate_id, row in parsed.items()},
            "tracking_eligible": {candidate_id: row["tracking_eligible"] for candidate_id, row in parsed.items()},
            "commercial_scores": {candidate_id: row["commercial_score"] for candidate_id, row in parsed.items()},
            "shelf_life_scores": {candidate_id: row["shelf_life_score"] for candidate_id, row in parsed.items()},
            "topics": {candidate_id: row["portfolio_topic"] for candidate_id, row in parsed.items()},
            "missing": missing,
            "diagnostic": diagnostic,
            "usage": {
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        })

    historical = {str(row["id"]): int(row["raw_screening_score"]) for row in rows}
    historical_decisions = {candidate_id: score >= TRACKING_THRESHOLD for candidate_id, score in historical.items()}
    parsed_decisions = [_decision_map({cid: {"score": score} for cid, score in run_row["scores"].items()}) for run_row in runs]

    flips = []
    false_promotions = []
    false_demotions = []
    for candidate_id in sorted(ids):
        values = [decision.get(candidate_id) for decision in parsed_decisions]
        if len(set(values)) > 1:
            flips.append(candidate_id)
        for run_index, decision in enumerate(values, start=1):
            if decision is None:
                continue
            if decision and not historical_decisions[candidate_id]:
                false_promotions.append({"id": candidate_id, "run": run_index})
            if (not decision) and historical_decisions[candidate_id]:
                false_demotions.append({"id": candidate_id, "run": run_index})

    schema_complete = all(not row["missing"] and not row["diagnostic"] for row in runs)
    report = {
        "mode": "groq_raw_screening_shadow_run46",
        "provider": "groq",
        "model": MODEL,
        "historical_reference": {
            "run_id": baseline["run_id"],
            "stage": "raw_screening",
            "threshold": TRACKING_THRESHOLD,
            "scores_are_human_ground_truth": False,
        },
        "input_fidelity": {
            "production_records": True,
            "description_preserved": False,
            "production_equivalent": False,
            "reason": "Run46 observed history does not preserve original candidate description",
        },
        "selected": [{
            "id": str(row["id"]),
            "source": row.get("source"),
            "historical_raw_score": int(row["raw_screening_score"]),
            "historical_raw_pass": int(row["raw_screening_score"]) >= TRACKING_THRESHOLD,
        } for row in rows],
        "runs": runs,
        "stability": {
            "decision_flips": flips,
            "decision_flip_count": len(flips),
            "false_promotions_vs_historical": false_promotions,
            "false_demotions_vs_historical": false_demotions,
            "schema_complete": schema_complete,
        },
        "persist_allowed": False,
        "business_writes": 0,
        "automatic_promotion_allowed": False,
        "promotion_candidate": False,
        "promotion_blockers": [
            "incomplete_input_fidelity:missing_description",
            *(["decision_instability"] if flips else []),
            *(["false_promotion_observed"] if false_promotions else []),
            *(["schema_incomplete"] if not schema_complete else []),
        ],
    }
    Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    baseline_path = os.environ.get("AIIF_SCREENING_RUN46_BASELINE", "/tmp/screening_run46.json")
    report_path = os.environ.get("AIIF_GROQ_SCREENING_SHADOW_REPORT", "groq-screening-shadow-run46.json")
    report = run(baseline_path, report_path, repeats=2)
    print(json.dumps({
        "mode": report["mode"],
        "provider": report["provider"],
        "model": report["model"],
        "selected_count": len(report["selected"]),
        "decision_flip_count": report["stability"]["decision_flip_count"],
        "false_promotion_count": len(report["stability"]["false_promotions_vs_historical"]),
        "false_demotion_count": len(report["stability"]["false_demotions_vs_historical"]),
        "schema_complete": report["stability"]["schema_complete"],
        "production_equivalent": report["input_fidelity"]["production_equivalent"],
        "automatic_promotion_allowed": False,
        "business_writes": 0,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
