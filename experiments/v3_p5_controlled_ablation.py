"""Private-only manual P5 creative-call ablation. Default is ZERO Gemini calls.

One frozen Elastic input, Gemini 3.8 Flash; independent A/B/C/D interventions,
optional E integrated persona/token-cap. No note/Notion/publish. No raw drafts
in public GitHub/Actions. All live sends use canonical persistent Gemini budget.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import secrets
import time
from typing import Any, Callable
from zoneinfo import ZoneInfo

from experiments.v3_p5_baseline_repro import frozen_case_prompts
from experiments.v3_p5_golden_cases import READY_CASES
from local_skills.v3_p5_one_shot import _extract_bundle, _p5_prompt

MODEL = "gemini-3.8-flash"
CONFIRM = "RUN_P5_ABLATION_ONCE"
PACE_SECONDS = 90
REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Arm:
    code: str
    transport: str
    prompt: str
    config: dict[str, Any] | None


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_arms() -> tuple[Arm, ...]:
    cases = [x for x in READY_CASES if x.case.title == "Your Transformer Is Secretly Elastic"]
    if len(cases) != 1:
        raise RuntimeError("Frozen Elastic case not unique")
    item = cases[0]
    original = dict(frozen_case_prompts())[item.case.case_id]
    managed = _p5_prompt(
        item.case, dict(item.management),
        {"evidence_result": {}, "evidence_metadata": {}},
        writer_boundary="managed",
    )
    if not managed.startswith(original.rstrip()) or managed == original:
        raise RuntimeError("Invalid managed prompt comparison")
    low = {"thinking_config": {"thinking_level": "low"}}
    return (
        Arm("A", "generate_content", original, None),
        Arm("B", "chat", original, None),
        Arm("C", "chat", original, low),
        Arm("D", "chat", managed, low),
        Arm("E", "chat", managed, low),
    )


def manifest_for(arms: tuple[Arm, ...]) -> dict:
    return {
        "status": "PROVIDER_FREE_PREFLIGHT",
        "model": MODEL, "case": "Elastic",
        "arms": [x.code for x in arms],
        "prompt_sha256": {x.code: sha(x.prompt) for x in arms},
        "transport": {x.code: x.transport for x in arms},
        "config_flags": {x.code: bool(x.config) for x in arms},
        "uses_extra_editor_persona": "E" in [x.code for x in arms],
        "gemini_requests": 0,
        "human_quality_approved": False, "publication_approved": False,
        "note_write": False, "notion_write": False,
        "causality": "Exploratory single-sample comparison, NOT statistical proof",
    }


def private_directory(path: Path) -> Path:
    path = path.expanduser().resolve()
    if path == REPO_ROOT or REPO_ROOT in path.parents:
        raise RuntimeError("Cannot write private article in public repository")
    if path.exists():
        raise RuntimeError("Refusing existing private output directory")
    path.mkdir(parents=True, mode=0o700, exist_ok=False)
    os.chmod(path, 0o700)
    return path


def private_write(path: Path, text: str) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def run_private(arms: tuple[Arm, ...], output: Path,
                send: Callable[[Arm], Any],
                sleep: Callable[[int], None] = time.sleep) -> dict:
    output = private_directory(output)
    blind = list("ABCDE"[:len(arms)])
    secrets.SystemRandom().shuffle(blind)
    key = dict(zip((x.code for x in arms), blind))
    result = manifest_for(arms)
    result["status"] = "IN_PROGRESS_UNREVIEWED"
    result["candidates"] = {}
    try:
        for index, arm in enumerate(arms):
            if index:
                sleep(PACE_SECONDS)
            result["gemini_requests"] += 1
            response = send(arm)
            article, stages = _extract_bundle(str(getattr(response, "text", "") or ""))
            label = key[arm.code]
            private_write(output / ("Candidate_" + label + ".md"), article + "\n")
            stage_json = json.dumps(stages, ensure_ascii=False, indent=2)
            private_write(output / ("Stages_Candidate_" + label + ".json"), stage_json + "\n")
            result["candidates"][label] = {
                "sha256": sha(article), "characters": len(article),
                "stage_count": len(stages), "stages_sha256": sha(stage_json),
                "writing_stage_chars": len(stages["Persona Article Generation"]),
                "review_stage_chars": len(stages["Fact-Safe Review"]),
            }
        result["status"] = "ALL_VALID_AWAITING_BLIND_HUMAN_REVIEW"
    except Exception as error:
        result["status"] = "INCOMPLETE_TECHNICAL_NO_GO"
        result["error_type"] = type(error).__name__
        raise
    finally:
        private_write(output / "KEY_OPEN_AFTER_SCORING.json",
                      json.dumps(key, ensure_ascii=False, indent=2))
        private_write(output / "manifest.json",
                      json.dumps(result, ensure_ascii=False, indent=2))
    return result


def native_sender() -> tuple[Callable[[Arm], Any], Callable[[], None]]:
    if not os.environ.get("GH_PAT") or not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Live experiment requires GH_PAT and GEMINI_API_KEY")
    from google import genai
    import pipeline as p
    persistent = getattr(p, "PERSISTENT_GEMINI_COUNTER", None)
    if persistent is None or getattr(persistent, "enabled", False) is not True:
        raise RuntimeError("Canonical persistent Gemini counter must be enabled")
    old_client = p.client
    client = genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options={"timeout": 240000, "retry_options": {"attempts": 1}},
    )
    p.client = client
    from canonical_article_contract import aiif_editor_persona

    def send(arm: Arm) -> Any:
        config = arm.config
        if arm.code == "E":
            config = {
                **dict(arm.config or {}),
                "system_instruction": aiif_editor_persona(),
                "max_output_tokens": p.GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS,
            }
        request_context = "p5_causal_ablation:" + arm.code
        if arm.transport == "chat":
            return p._generate_via_chat(
                MODEL, arm.prompt, config=config,
                request_kind="deep_dive",
                request_origin="article_revalidation",
                request_context=request_context,
                count_as_deep_dive=True,
            )
        # Original Phase0 transport. Reserve the SAME native budget before call.
        audit = p._consume_gemini_request(
            "deep_dive", model_name=MODEL,
            request_context=request_context,
            count_as_deep_dive=True, request_origin="article_revalidation",
        )
        try:
            response = client.models.generate_content(
                model=MODEL, contents=arm.prompt,
            )
        except Exception as exc:
            p.GEMINI_USAGE_AUDIT.record_outcome(audit, "error", exc)
            # Conservative fail-closed: do not release an ambiguous request.
            raise
        p.GEMINI_USAGE_AUDIT.record_outcome(audit, "success")
        p.GEMINI_USAGE_AUDIT.record_response_usage(audit, response)
        return response

    def close() -> None:
        p.client = old_client
        client.close()

    return send, close


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--include-e", action="store_true")
    parser.add_argument("--private-output", type=Path)
    args = parser.parse_args()
    arms = build_arms()[:5 if args.include_e else 4]
    if not args.live:
        print(json.dumps(manifest_for(arms), ensure_ascii=False, indent=2))
        return
    if args.confirm != CONFIRM or args.private_output is None:
        raise RuntimeError("Manual confirmation and --private-output are required")
    if os.environ.get("GITHUB_ACTIONS") == "true":
        authorized = (
            os.environ.get("AIIF_P5_CONFIDENTIAL_REVIEW") == "fernet_telegram_private"
            and os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch"
            and os.environ.get("GITHUB_RUN_ATTEMPT") == "1"
            and os.environ.get("GITHUB_ACTOR") == "trendhub-ab"
            and os.environ.get("GITHUB_REF") == "refs/heads/main"
        )
        if not authorized:
            raise RuntimeError("GitHub Actions require P5 protected manual dispatch with encrypted private handoff")
    if datetime.now(ZoneInfo("Asia/Tokyo")).hour < 17:
        raise RuntimeError("Live P5 proof requires 17:00 JST or later")
    target = args.private_output.expanduser().resolve()
    if target.exists() or target == REPO_ROOT or REPO_ROOT in target.parents:
        raise RuntimeError("Choose a NEW private directory outside the repository")
    sender, close = native_sender()
    try:
        result = run_private(arms, target, sender)
        print("P5_ABLATION_COMPLETE; requests=" + str(result["gemini_requests"])
              + "; human_approved=false; publication=false")
    finally:
        close()


if __name__ == "__main__":
    main()
