"""Exact-original P5 C-only three-case replay. Never a Production writer.

Run without credentials to verify prompt/call parity:
  python -m experiments.v3_p5_baseline_repro
Optional owner-approved bounded live proof requires P5_GOLDEN_REPLAY_ONCE.
Three calls on ONE explicit non-preview model; no auto retry, persistence or publish.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

from experiments.editorial_engine_v3_phase0.cases import READY_CASES
from experiments.editorial_engine_v3_phase0.prompts import (
    build_editorial_bundle_prompt as selected_p5_prompt,
)
from local_skills.v3_p5_call_contract import pure_p5_writer_config
from local_skills.v3_p5_one_shot import _extract_bundle
from local_skills.v3_p5_prompts import (
    build_editorial_bundle_prompt as production_snapshot_prompt,
)

BASELINE = "95016a65701979063f56130bf181bca831661f5d"
BASELINE_LIVE_RUN = 39963513015
BASELINE_HUMAN_SCORES = {"FFT": 75, "Elastic": 85, "Claude": 88}
ALLOWED_MODELS = frozenset({
    "gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash",
})
OUTPUT = Path("p5_baseline_repro_artifact")
CONFIRMATION = "P5_GOLDEN_REPLAY_ONCE"


def frozen_case_prompts() -> list[tuple[str, str]]:
    if len(READY_CASES) != 3:
        raise RuntimeError("P5 golden source set must have exactly three cases")
    result = []
    for case in READY_CASES:
        original = selected_p5_prompt(case.case)
        integrated = production_snapshot_prompt(case.case)
        if original != integrated:
            raise RuntimeError("P5 selected source prompt changed in integration")
        result.append((case.case.case_id, original))
    return result


def build_manifest(model: str) -> dict:
    prompts = frozen_case_prompts()
    config = pure_p5_writer_config(
        {"system_instruction": "MUST_NOT_SURVIVE", "max_output_tokens": 18000},
        editorial_style="v3_p5", writer_boundary="original",
        request_origin="article_revalidation", request_kind="deep_dive",
    )
    if config:
        raise RuntimeError("Baseline proof call has added generation config")
    return {
        "baseline_commit": BASELINE,
        "baseline_run": BASELINE_LIVE_RUN,
        "human_scores": BASELINE_HUMAN_SCORES,
        "mean_human_score": 83,
        "selected_model": model,
        "selected_model_allowed": model in ALLOWED_MODELS,
        "prompt_sha256": {
            case_id: hashlib.sha256(prompt.encode()).hexdigest()
            for case_id, prompt in prompts
        },
        "system_instruction": False,
        "generation_config_overrides": False,
        "mode": "validation_only",
        "provider_attempts": 0,
        "note_write": False,
        "notion_write": False,
        "publication": False,
        "human_quality_approval": False,
    }


def main() -> None:
    model = os.getenv("AIIF_P5_PROOF_MODEL", "gemini-3.5-flash")
    manifest = build_manifest(model)
    if model not in ALLOWED_MODELS:
        raise RuntimeError("Forbidden or unknown P5 model (Preview/Lite excluded)")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if os.getenv("AIIF_P5_LIVE_CONFIRM") != CONFIRMATION:
        manifest["status"] = "PROVIDER_FREE_BASELINE_PREFLIGHT_PASS"
        (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        print("P5_BASELINE_REPRO_PREFLIGHT=PASS; provider_calls=0; quality_not_proven")
        return
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY required for explicitly confirmed live proof")

    from google import genai
    # Transport retries disabled to keep the exactly-three-call model budget.
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options={"timeout": 120000, "retry_options": {"attempts": 1}},
    )
    manifest["status"] = "IN_PROGRESS"
    try:
        for idx, (case_id, prompt) in enumerate(frozen_case_prompts()):
            if idx:
                time.sleep(30)
            manifest["provider_attempts"] += 1
            (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
            # Match the selected Phase0 creative call: NO separate config or system instruction.
            response = client.models.generate_content(model=model, contents=prompt)
            final, stages = _extract_bundle(str(getattr(response, "text", "") or ""))
            (OUTPUT / f"sample_{idx+1}.md").write_text(final + "\n", encoding="utf-8")
            (OUTPUT / f"stages_{idx+1}.json").write_text(
                json.dumps(stages, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        manifest["status"] = "THREE_VALID_BUNDLES_AWAIT_BLIND_HUMAN_EDITORIAL_REVIEW"
    except Exception as exc:
        manifest["status"] = "TECHNICAL_NO_GO"
        manifest["error_type"] = type(exc).__name__
        raise
    finally:
        (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        client.close()


if __name__ == "__main__":
    main()
