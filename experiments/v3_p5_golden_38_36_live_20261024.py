"""One-shot, nonpublishing golden P5 C-only live replay.

Exactly the selected #852 three frozen inputs and selected five-stage prompt.
One complete model arm: Gemini 3.8 Flash first, then 3.6 Flash ONLY if the
first model fails. Discard partial first-model batches; never compare mixed
models. Gemini 3.6 Flash: STRICT MAXIMUM THREE PROVIDER SENDS in this run,
spaced by at least 90 seconds; no SDK auto retries.

This is an editorial proof, not a full Production Fact/Publication Gate.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from google import genai

from experiments.v3_p5_baseline_repro import (
    BASELINE, BASELINE_HUMAN_SCORES, frozen_case_prompts,
)
from local_skills.v3_p5_one_shot import _extract_bundle

MODELS = ("gemini-3.8-flash", "gemini-3.6-flash")
MAX_SENDS_BY_MODEL = {"gemini-3.8-flash": 3, "gemini-3.6-flash": 3}
MAX_TOTAL_SENDS = 6
MIN_SEND_SPACING_SECONDS = 90.0
OUTPUT = Path("p5_golden_38_to_36_live_20261024")
CONFIRM = "P5_GOLDEN_38_TO_36_ONCE"
CASE_LABELS = ("FFT", "Elastic", "Claude")
ARTIFACT_FIELDS = ("Writer Reaction", "Editorial Discovery", "Cognitive Shift",
                   "Persona Article Generation", "Fact-Safe Review")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def plan() -> tuple[list[tuple[str, str]], dict]:
    prompts = frozen_case_prompts()
    if len(prompts) != 3 or len({n for n, _ in prompts}) != 3:
        raise RuntimeError("Original P5 golden fixture must contain exactly three cases")
    if len(MODELS) != 2 or MODELS != ("gemini-3.8-flash", "gemini-3.6-flash"):
        raise RuntimeError("Unexpected P5 nonpreview model routing")
    if MAX_SENDS_BY_MODEL["gemini-3.6-flash"] != 3 or MAX_TOTAL_SENDS != 6:
        raise RuntimeError("Gemini 3.6 Flash budget must stay at 3 sends")
    if MIN_SEND_SPACING_SECONDS < 90:
        raise RuntimeError("Rate-limit protection weakened")
    if any("preview" in model or "lite" in model for model in MODELS):
        raise RuntimeError("Preview/Lite forbidden")
    if any("1. Writer Reaction" not in prompt
           or "5. Fact-Safe Review" not in prompt for _, prompt in prompts):
        raise RuntimeError("Wrong P5 prompt")
    state = {
        "status": "PRECHECK_PASSED_NO_API",
        "source_baseline_commit": BASELINE,
        "source_baseline_human_scores": BASELINE_HUMAN_SCORES,
        "source_baseline_mean": 83,
        "model_priority": list(MODELS),
        "model_used": None,
        "call_count_total": 0,
        "call_count_by_model": dict.fromkeys(MODELS, 0),
        "max_by_model": MAX_SENDS_BY_MODEL,
        "minimum_call_spacing_seconds": MIN_SEND_SPACING_SECONDS,
        "source_prompt_sha256": {
            label: hashlib.sha256(prompt.encode("utf-8")).hexdigest()
            for label, (_, prompt) in zip(CASE_LABELS, prompts)
        },
        "attempts": [],
        "publication": False,
        "notion_write": False,
        "note_write": False,
        "full_production_fact_gate": False,
        "human_editorial_approval": False,
    }
    return prompts, state


def _status(exc: BaseException) -> int | None:
    for attr in ("code", "status_code"):
        value = getattr(exc, attr, None)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return None


def main() -> None:
    prompts, state = plan()
    _write_json(OUTPUT / "manifest.json", state)
    if os.getenv("P5_GOLDEN_LIVE_CONFIRM") != CONFIRM:
        print("P5_GOLDEN_38_36_PRECHECK_PASS provider_requests=0", flush=True)
        return
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is required for the one-shot proof")

    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options={"timeout": 120000, "retry_options": {"attempts": 1}},
    )
    last_terminal: float | None = None
    try:
        for model in MODELS:
            completed = []
            for idx, (case_id, prompt) in enumerate(prompts):
                if state["call_count_by_model"][model] >= MAX_SENDS_BY_MODEL[model]:
                    raise RuntimeError("per-model request ceiling")
                if state["call_count_total"] >= MAX_TOTAL_SENDS:
                    raise RuntimeError("global provider request ceiling")
                if last_terminal is not None:
                    waiting = max(0, MIN_SEND_SPACING_SECONDS - (time.monotonic() - last_terminal))
                    if waiting:
                        print(f"P5_RATE_PACING model={model} sleep_seconds={waiting:.1f}", flush=True)
                        time.sleep(waiting)
                state["call_count_by_model"][model] += 1
                state["call_count_total"] += 1
                number = state["call_count_total"]
                event = {
                    "attempt": number, "model": model, "golden_case": CASE_LABELS[idx],
                    "status": "SENT", "article_chars": 0,
                }
                state["attempts"].append(event)
                state["status"] = "GENERATING"
                _write_json(OUTPUT / "manifest.json", state)
                print(
                    f"P5_SEND number={number}/{MAX_TOTAL_SENDS} model={model} "
                    f"case={CASE_LABELS[idx]} model_calls={state['call_count_by_model'][model]}/3",
                    flush=True,
                )
                try:
                    # Replicate selected preintegration P5 call: contents alone.
                    # NO system persona, management instruction, forced config or
                    # temperature. Explicitly disabled automatic SDK retries.
                    response = client.models.generate_content(model=model, contents=prompt)
                    final, stages = _extract_bundle(str(getattr(response, "text", "") or ""))
                    if not final.strip().startswith("# "):
                        raise ValueError("P5 manuscript must start with Markdown H1")
                    if tuple(stages) != ARTIFACT_FIELDS:
                        raise ValueError("Unexpected editorial stage order")
                    event.update(status="FULL_5_STAGE_VALID", article_chars=len(final))
                    # Interim cases are retained ONLY as diagnostics if this
                    # model later fails; they cannot become a mixed-model set.
                    case_folder = OUTPUT / "by_model" / model
                    case_folder.mkdir(parents=True, exist_ok=True)
                    (case_folder / f"{CASE_LABELS[idx]}.md").write_text(
                        final + "\n", encoding="utf-8"
                    )
                    _write_json(case_folder / f"{CASE_LABELS[idx]}_stages.json", stages)
                    completed.append(final)
                    print(
                        f"P5_FIVE_STAGE_VALID model={model} case={CASE_LABELS[idx]} "
                        f"chars={len(final)}", flush=True
                    )
                except Exception as exc:
                    code = _status(exc)
                    event.update(status="FAILED", http_status=code, error_type=type(exc).__name__)
                    state["status"] = "MODEL_REJECTED_RESTART_TRIPLET"
                    _write_json(OUTPUT / "manifest.json", state)
                    print(
                        f"P5_MODEL_REJECTED model={model} case={CASE_LABELS[idx]} "
                        f"http={code} error_type={type(exc).__name__}", flush=True
                    )
                    last_terminal = time.monotonic()
                    break  # Only the next model may retry, from case 1.
                last_terminal = time.monotonic()

            if len(completed) == 3:
                state["model_used"] = model
                state["status"] = "THREE_CASES_VALID_NEEDS_HUMAN_EDITORIAL_AND_FACT_REVIEW"
                for label, final in zip(CASE_LABELS, completed):
                    (OUTPUT / f"golden_{label}.md").write_text(final + "\n", encoding="utf-8")
                _write_json(OUTPUT / "manifest.json", state)
                print(
                    f"P5_GOLDEN_TECHNICAL_SUCCESS model={model} cases=3 "
                    f"3.6_calls={state['call_count_by_model']['gemini-3.6-flash']} "
                    f"total_calls={state['call_count_total']}", flush=True
                )
                return
            if model != MODELS[-1]:
                print(
                    "P5_FALLBACK_RESTART_FFT_ELASTIC_CLAUDE model=gemini-3.6-flash",
                    flush=True,
                )

        state["status"] = "TECHNICAL_NO_GO_NOT_COMPARABLE"
        _write_json(OUTPUT / "manifest.json", state)
        print(
            f"P5_GOLDEN_NO_GO model_3_6_calls={state['call_count_by_model']['gemini-3.6-flash']}"
            f" total_calls={state['call_count_total']}", flush=True,
        )
        raise RuntimeError("No single non-preview model produced all three original P5 cases")
    finally:
        _write_json(OUTPUT / "manifest.json", state)
        client.close()


if __name__ == "__main__":
    main()
