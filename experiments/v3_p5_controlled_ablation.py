"""Private-only manual P5 creative-call ablation. Default is ZERO Gemini calls.

One frozen Elastic input, Gemini 3.8/3.6 Flash; independent A/B/C/D interventions,
optional E integrated persona/token-cap. No note/Notion/publish. No raw drafts
in public GitHub/Actions. All live sends use canonical persistent Gemini budget.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import secrets
import time
from typing import Any, Callable

from experiments.v3_p5_baseline_repro import frozen_case_prompts
from experiments.v3_p5_golden_cases import READY_CASES
from local_skills.v3_p5_one_shot import _extract_bundle, _p5_prompt

MODEL = "gemini-3.8-flash"
FALLBACK_MODEL = "gemini-3.6-flash"
MIXED_MODEL_PLAN = {"B": FALLBACK_MODEL, "D": FALLBACK_MODEL}
MAX_PROVIDER_REQUESTS = None  # No P5 cumulative cap; canonical persistent quota and 3 attempts per arm remain.
FALLBACK_PROVIDER_CODES = frozenset({404, 429, 503})
CONFIRM = "RUN_P5_ABLATION_ONCE"
PACE_SECONDS = 90
REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Arm:
    code: str
    transport: str
    prompt: str
    config: dict[str, Any] | None
    model: str = MODEL


def provider_error_code(exc: BaseException) -> int | None:
    """Only structured provider 404/429/503 qualifies; no guess from text."""
    for field in ("status_code", "code"):
        value = getattr(exc, field, None)
        if type(value) is int:
            return value
    return None


def dispatch_with_fallback(
    arm: Arm, attempt: Callable[[Arm, str], Any],
    sleep: Callable[[int], None] = time.sleep,
    can_retry: Callable[[], bool] = lambda: True,
) -> tuple[Any, str]:
    """Bounded 503/429 retry; 3.8 may downgrade once, never reverse upgrade.

    Reserve calls for all remaining arms BEFORE spending retry budget.
    HTTP 404 may switch 3.8 to 3.6 once, but is not retried on 3.6.
    """
    model = arm.model
    for retry_index in range(3):
        try:
            return attempt(arm, model), model
        except Exception as exc:
            code = provider_error_code(exc)
            if code not in FALLBACK_PROVIDER_CODES or not can_retry():
                raise
            if model == MODEL and code in FALLBACK_PROVIDER_CODES:
                model = FALLBACK_MODEL
            elif model == FALLBACK_MODEL and code in (429, 503):
                if retry_index >= 2:
                    raise
            else:
                raise
            sleep(PACE_SECONDS * (retry_index + 1))
    raise RuntimeError("P5 impossible provider retry state")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_arms(mixed_models: bool = False) -> tuple[Arm, ...]:
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
        Arm("B", "chat", original, None,
            MIXED_MODEL_PLAN["B"] if mixed_models else MODEL),
        Arm("C", "chat", original, low),
        Arm("D", "chat", managed, low,
            MIXED_MODEL_PLAN["D"] if mixed_models else MODEL),
        Arm("E", "chat", managed, low),
    )


def manifest_for(arms: tuple[Arm, ...]) -> dict:
    return {
        "status": "PROVIDER_FREE_PREFLIGHT",
        "checkpoint_schema": "p5-resume-v1",
        "model": MODEL if len({arm.model for arm in arms}) == 1 else "MIXED",
        "primary_models_by_arm": {arm.code: arm.model for arm in arms},
        "max_provider_requests": MAX_PROVIDER_REQUESTS,
        "case": "Elastic",
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
                sleep: Callable[[int], None] = time.sleep,
                resume_bundle: Path | None = None,
                resume_key: str = "") -> dict:
    result = manifest_for(arms)
    start_at = 0
    saved_files: dict[str, bytes] = {}
    if resume_bundle is not None:
        from experiments.v3_p5_checkpoint import open_checkpoint
        result, key, saved_files, start_at = open_checkpoint(
            resume_bundle, resume_key, result,
        )
        actual_models = dict(key["__actual_models_by_arm__"])
        if result.get("max_provider_requests") == 8:
            result["legacy_checkpoint_max_provider_requests"] = 8
        result["max_provider_requests"] = None
        result.pop("error_type", None)
    else:
        blind = list("ABCDE"[:len(arms)])
        secrets.SystemRandom().shuffle(blind)
        key = dict(zip((x.code for x in arms), blind))
        actual_models: dict[str, str] = {}
        result["candidates"] = {}
    output = private_directory(output)
    for name, data in saved_files.items():
        fd = os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
    result["status"] = "IN_PROGRESS_UNREVIEWED"
    if hasattr(send, "max_request_attempts"):
        send.max_request_attempts = None  # Previous attempt counts are kept for audit, not a restart cap.
    try:
        for index, arm in enumerate(arms):
            if index < start_at:
                continue
            if index > 0 and index != start_at:
                sleep(PACE_SECONDS)
            if hasattr(send, "remaining_arms"):
                send.remaining_arms = len(arms) - index - 1
            before = getattr(send, "request_attempts", None)
            try:
                sent = send(arm)
            finally:
                after = getattr(send, "request_attempts", None)
                count = max(1, after - before) if type(before) is int and type(after) is int else 1
                result["gemini_requests"] += count
            response, actual_model = sent if isinstance(sent, tuple) else (sent, arm.model)
            if actual_model not in (MODEL, FALLBACK_MODEL):
                raise RuntimeError("Unapproved P5 response model")
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
            actual_models[arm.code] = actual_model
        result["status"] = "ALL_VALID_AWAITING_BLIND_HUMAN_REVIEW"
    except Exception as error:
        result["status"] = "INCOMPLETE_TECHNICAL_NO_GO"
        result["error_type"] = type(error).__name__
        raise
    finally:
        key["__actual_models_by_arm__"] = actual_models
        key["__fallback_used_by_arm__"] = {
            code: actual_models[code] != next(arm.model for arm in arms if arm.code == code)
            for code in actual_models
        }
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

    def provider_attempt(arm: Arm, model_name: str) -> Any:
        send.request_attempts += 1
        config = arm.config
        if arm.code == "E":
            config = {
                **dict(arm.config or {}),
                "system_instruction": aiif_editor_persona(),
                "max_output_tokens": p.GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS,
            }
        request_context = "p5_causal_ablation:" + arm.code + ":" + model_name
        if arm.transport == "chat":
            return p._generate_via_chat(
                model_name, arm.prompt, config=config,
                request_kind="deep_dive",
                request_origin="article_revalidation",
                request_context=request_context,
                count_as_deep_dive=True,
            )
        audit = p._consume_gemini_request(
            "deep_dive", model_name=model_name,
            request_context=request_context,
            count_as_deep_dive=True, request_origin="article_revalidation",
        )
        try:
            response = client.models.generate_content(
                model=model_name, contents=arm.prompt,
            )
        except Exception as exc:
            p.GEMINI_USAGE_AUDIT.record_outcome(audit, "error", exc)
            # Provider-reported attempts remain reserved, including retryable 503.
            raise
        p.GEMINI_USAGE_AUDIT.record_outcome(audit, "success")
        p.GEMINI_USAGE_AUDIT.record_response_usage(audit, response)
        return response

    def send(arm: Arm) -> tuple[Any, str]:
        def can_retry() -> bool:
            # Retry count is already limited to three inside dispatch_with_fallback.
            # Canonical persistent Gemini quotas remain authoritative per attempt.
            return True
        return dispatch_with_fallback(
            arm, provider_attempt, can_retry=can_retry,
        )

    send.request_attempts = 0
    send.max_request_attempts = MAX_PROVIDER_REQUESTS
    send.remaining_arms = 0

    def close() -> None:
        p.client = old_client
        client.close()

    return send, close


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--include-e", action="store_true")
    parser.add_argument("--mix-models", action="store_true",
                        help="A/C/E use 3.8, B/D use 3.6; 3.8 404/429/503 may fall back")
    parser.add_argument("--private-output", type=Path)
    parser.add_argument("--resume-bundle", type=Path,
                        help="Encrypted partial artifact from reviewed earlier P5 run")
    args = parser.parse_args()
    arms = build_arms(mixed_models=args.mix_models)[:5 if args.include_e else 4]
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
    target = args.private_output.expanduser().resolve()
    if target.exists() or target == REPO_ROOT or REPO_ROOT in target.parents:
        raise RuntimeError("Choose a NEW private directory outside the repository")
    if args.resume_bundle is not None and not os.environ.get("AIIF_P5_RESUME_KEY"):
        raise RuntimeError("Resume requires P5 key via Actions repository secret")
    sender, close = native_sender()
    try:
        if args.resume_bundle is None:
            result = run_private(arms, target, sender)
        else:
            result = run_private(
                arms, target, sender, resume_bundle=args.resume_bundle,
                resume_key=os.environ["AIIF_P5_RESUME_KEY"],
            )
        print("P5_ABLATION_COMPLETE; requests=" + str(result["gemini_requests"])
              + "; human_approved=false; publication=false")
    finally:
        close()


if __name__ == "__main__":
    main()
