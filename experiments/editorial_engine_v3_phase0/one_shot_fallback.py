"""One-shot experimental P5 C-only fallback. Never import from Production.

This helper is ONLY present on a disposable non-merging workflow branch.
Model changes require a complete fresh 3-case C run with immutable A/B.
Fallback is permitted solely for 429/503 provider errors; never article failures.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo


CANDIDATE_MODELS = (
    "gemini-3-flash-preview",
    "gemini-3.6-flash",
    "gemini-3.8-flash",
)
BASELINE_RUN_ID = 39239644474
MAX_C_CASES = 3


def main() -> int:
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Missing GEMINI_API_KEY")
    assert len(CANDIDATE_MODELS) == len(set(CANDIDATE_MODELS)) == 3
    assert all("lite" not in name.lower() for name in CANDIDATE_MODELS)
    baseline = Path("phase0_baseline")
    attempt_root = Path("phase0_fallback_attempts")
    attempt_root.mkdir(exist_ok=True)
    summary: list[dict[str, object]] = []
    selected_model: str | None = None

    for index, model in enumerate(CANDIDATE_MODELS, 1):
        if datetime.now(ZoneInfo("Asia/Tokyo")).hour < 17:
            raise RuntimeError("Gemini prohibited before 17:00 JST")
        workspace = attempt_root / f"model_{index}"
        shutil.copytree(baseline, workspace)
        checkpoint_path = workspace / "checkpoint.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        assert checkpoint["selected_model"] == "gemini-3.8-flash"
        assert len(checkpoint["cases"]) == MAX_C_CASES
        assert all(
            case["outputs"].get("A_CURRENT_WRITER")
            and case["outputs"].get("B_PERSONA_ONLY")
            for case in checkpoint["cases"]
        )
        checkpoint["baseline_selected_model"] = "gemini-3.8-flash"
        checkpoint["comparison_model_exception"] = "ONE_OFF_MIXED_MODEL_C_FALLBACK"
        checkpoint["selected_model"] = model
        for key in (
            "c_refinement_fingerprint",
            "c_completed_case_ids",
            "c_refinement_provider_calls_total",
            "c_refinement_provider_attempts_total",
        ):
            checkpoint.pop(key, None)
        checkpoint_path.write_text(
            json.dumps(checkpoint, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        env = os.environ.copy()
        env["AIIF_PHASE0_MODELS"] = model
        env["AIIF_PHASE0_OUTPUT_DIR"] = str(workspace)
        env["AIIF_PHASE0_REGENERATE_C_ONLY"] = "true"
        print(f"C_ONLY_FALLBACK_TRIAL={index}/3 selected={model}", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "experiments.editorial_engine_v3_phase0.live"],
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=900,
            check=False,
        )
        outcome: dict[str, object] = {
            "model": model,
            "returncode": result.returncode,
        }
        if result.returncode == 0:
            proof = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "experiments.editorial_engine_v3_phase0.proof",
                    "verify",
                    "--output-dir",
                    str(workspace),
                ],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                check=False,
            )
            verdict_file = workspace / "proof_verdict.json"
            if proof.returncode != 0 or not verdict_file.exists():
                outcome["status"] = "structural_failure_stop"
                summary.append(outcome)
                print("C_ONLY_STRUCTURAL_FAILURE_NO_FALLBACK", flush=True)
                break
            verdict = json.loads(verdict_file.read_text(encoding="utf-8"))
            checks = verdict.get("checks", {})
            if (
                verdict.get("status") != "PASS"
                or len(verdict.get("completed_case_ids", ())) != MAX_C_CASES
                or len(checks) < 16
                or not all(checks.values())
            ):
                outcome["status"] = "structural_failure_stop"
                summary.append(outcome)
                print("C_ONLY_STRUCTURAL_FAILURE_NO_FALLBACK", flush=True)
                break
            outcome["status"] = "PASS"
            summary.append(outcome)
            selected_model = model
            output = Path("phase0_artifacts")
            if output.exists():
                shutil.rmtree(output)
            shutil.copytree(workspace, output)
            (output / "fallback_selection.json").write_text(
                json.dumps(
                    {
                        "selected_model": model,
                        "models_tried": summary,
                        "baseline_run_id": BASELINE_RUN_ID,
                        "fallback_policy": "whole_three_case_set; provider 429/503 only",
                        "max_candidates": len(CANDIDATE_MODELS),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(
                f"C_ONLY_FALLBACK_PASS model={model} completed_cases=3 mixed_models=NO",
                flush=True,
            )
            print(result.stdout[-400:], flush=True)
            print(proof.stdout[-1200:], flush=True)
            break

        # Invalid model names, malformed JSON or review-contract failures do
        # not justify falling back. Allow only explicit API 429/503.
        transient = bool(
            re.search(
                r"(?:\b429\b|\b503\b).{0,160}(?:UNAVAILABLE|RESOURCE_EXHAUSTED|ServerError|ClientError)"
                r"|(?:ServerError|ClientError).{0,160}(?:\b429\b|\b503\b)",
                result.stderr,
                flags=re.I | re.S,
            )
        )
        outcome["status"] = "transient_provider_429_503" if transient else "no_fallback_untrusted_error"
        summary.append(outcome)
        print(f"C_ONLY_TRIAL_STOP={outcome['status']} model={model}", flush=True)
        if not transient:
            break

    (attempt_root / "fallback_attempt_summary.json").write_text(
        json.dumps(
            {
                "selected_model": selected_model,
                "models_tried": summary,
                "policy": "no mixing, only provider 429/503, no publication",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if not selected_model:
        print("C_ONLY_FALLBACK_INCOMPLETE_NO_PUBLICATION", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
