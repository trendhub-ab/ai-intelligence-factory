from __future__ import annotations

import hashlib
import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from local_skills.compiler import compile_snapshot

from .cases import READY_CASES, ReplayCase
from .contract import EDITORIAL_STAGES, validate_article_layout
from .prompts import build_editorial_bundle_prompt, build_persona_only_prompt
from .runner import build_blind_package, build_current_writer_snapshot

DEFAULT_MODEL_CANDIDATES = ("gemini-3.8-flash", "gemini-3.6-flash")
B_CALLS_PER_CASE = 1
C_CALLS_PER_CASE = 1
EXPECTED_CASES = 3
MAX_PROVIDER_CALLS = EXPECTED_CASES * (B_CALLS_PER_CASE + C_CALLS_PER_CASE)
C_ONLY_MAX_PROVIDER_CALLS = EXPECTED_CASES * C_CALLS_PER_CASE
LOCKED_MODEL_ATTEMPTS = 2
BACKOFF_BASE_SECONDS = 20.0
DEFAULT_CASE_COOLDOWN_SECONDS = 45.0
CHECKPOINT_NAME = "checkpoint.json"
C_REFINEMENT_RESUME_SCHEMA_VERSION = 1


@dataclass(slots=True)
class ModelSession:
    candidates: tuple[str, ...]
    locked_model: str | None = None
    provider_attempts: int = 0


def _model_candidates() -> tuple[str, ...]:
    raw = str(os.environ.get("AIIF_PHASE0_MODELS") or "").strip()
    candidates = tuple(part.strip() for part in raw.split(",") if part.strip()) if raw else DEFAULT_MODEL_CANDIDATES
    if not candidates or any("lite" in model.lower() for model in candidates):
        raise RuntimeError("Phase 0 requires non-Lite Gemini model candidates")
    if len(set(candidates)) != len(candidates):
        raise RuntimeError("Phase 0 model candidates must be unique")
    return candidates


def _case_cooldown_seconds() -> float:
    raw = str(os.environ.get("AIIF_PHASE0_CASE_COOLDOWN_SECONDS") or DEFAULT_CASE_COOLDOWN_SECONDS).strip()
    try:
        value = float(raw)
    except ValueError as exc:
        raise RuntimeError("Phase 0 case cooldown must be numeric") from exc
    if value < 0:
        raise RuntimeError("Phase 0 case cooldown must be non-negative")
    return value


def _env_truthy(name: str) -> bool:
    return str(os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _is_transient_error(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status in (429, 503, "429", "503"):
        return True
    text = str(exc).upper()
    return "429" in text or "503" in text or "RESOURCE_EXHAUSTED" in text or "UNAVAILABLE" in text


def _call_model(client: Any, *, model: str, prompt: str) -> str:
    response = client.models.generate_content(model=model, contents=prompt)
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty Phase 0 response")
    return text


def _sleep_backoff(attempt_index: int, sleep_fn: Callable[[float], None]) -> None:
    base = BACKOFF_BASE_SECONDS * (2**attempt_index)
    sleep_fn(base + random.uniform(0.0, 5.0))


def _provider_text_resilient(
    client: Any,
    *,
    session: ModelSession,
    prompt: str,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> str:
    if session.locked_model:
        last_error: BaseException | None = None
        for attempt in range(LOCKED_MODEL_ATTEMPTS):
            session.provider_attempts += 1
            try:
                return _call_model(client, model=session.locked_model, prompt=prompt)
            except BaseException as exc:
                if not _is_transient_error(exc):
                    raise
                last_error = exc
                if attempt + 1 < LOCKED_MODEL_ATTEMPTS:
                    _sleep_backoff(attempt, sleep_fn)
        assert last_error is not None
        raise last_error

    last_error: BaseException | None = None
    for index, model in enumerate(session.candidates):
        session.provider_attempts += 1
        try:
            text = _call_model(client, model=model, prompt=prompt)
        except BaseException as exc:
            if not _is_transient_error(exc):
                raise
            last_error = exc
            if index + 1 < len(session.candidates):
                _sleep_backoff(index, sleep_fn)
            continue
        session.locked_model = model
        return text
    assert last_error is not None
    raise last_error


def _current_writer_article(item: ReplayCase) -> str:
    snapshot = build_current_writer_snapshot(item)
    compiled = compile_snapshot(snapshot, evidence_context="\n".join(item.case.evidence))
    parsed = dict(compiled["parsed"])
    title = str(parsed.get("title_text") or "").strip()
    body = str(parsed.get("note_draft") or "").strip()
    if not title or not body:
        raise RuntimeError(f"Current Writer produced an incomplete article for {item.case.case_id}")
    return f"# {title}\n\n{body}".strip()


def _persona_only_article(client: Any, *, session: ModelSession, item: ReplayCase) -> str:
    return _provider_text_resilient(client, session=session, prompt=build_persona_only_prompt(item.case))


def _strip_json_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline >= 0:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    return cleaned.strip()


def _parse_editorial_bundle(text: str) -> tuple[str, dict[str, str]]:
    try:
        payload = json.loads(_strip_json_fence(text))
    except (TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("invalid editorial bundle JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("invalid editorial bundle: object required")

    stages: dict[str, str] = {}
    for stage in EDITORIAL_STAGES:
        value = str(payload.get(stage) or "").strip()
        if not value:
            raise RuntimeError(f"invalid editorial bundle: missing stage {stage}")
        stages[stage] = value

    for stage in ("Persona Article Generation", "Fact-Safe Review"):
        try:
            validate_article_layout(stages[stage])
        except ValueError as exc:
            raise RuntimeError(f"invalid editorial bundle: {stage}: {exc}") from exc

    return stages["Fact-Safe Review"], stages


def _editorial_article(
    client: Any,
    *,
    session: ModelSession,
    item: ReplayCase,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> tuple[str, dict[str, str]]:
    bundle = _provider_text_resilient(
        client,
        session=session,
        prompt=build_editorial_bundle_prompt(item.case),
        sleep_fn=sleep_fn,
    )
    return _parse_editorial_bundle(bundle)


def _input_digest(item: ReplayCase) -> str:
    payload = {
        "case_id": item.case.case_id,
        "title": item.case.title,
        "evidence": item.case.evidence,
        "facts": item.case.facts,
        "sources": item.case.sources,
        "target_reader": item.case.target_reader,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _c_refinement_fingerprint() -> str:
    payload = {
        "schema_version": C_REFINEMENT_RESUME_SCHEMA_VERSION,
        "stages": list(EDITORIAL_STAGES),
        "cases": [
            {
                "case_id": item.case.case_id,
                "input_digest": _input_digest(item),
                "editorial_bundle_prompt": build_editorial_bundle_prompt(item.case),
            }
            for item in READY_CASES
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _checkpoint_path(output_dir: str | Path) -> Path:
    return Path(output_dir) / CHECKPOINT_NAME


def _write_checkpoint(output_dir: str | Path, payload: dict[str, Any]) -> None:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = _checkpoint_path(out_dir)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)


def _load_checkpoint(output_dir: str | Path) -> dict[str, Any] | None:
    target = _checkpoint_path(output_dir)
    if not target.exists():
        return None
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("invalid Phase 0 checkpoint")
    return payload


def _completed_case_ids(checkpoint: dict[str, Any] | None) -> set[str]:
    if not checkpoint:
        return set()
    return {str(case.get("case_id") or "") for case in checkpoint.get("cases", []) if case.get("case_id")}


def _write_evaluation_artifacts(output_dir: Path, state: dict[str, Any]) -> None:
    raw = {
        "model": state.get("selected_model"),
        "mode": state.get("mode", "FULL"),
        "provider_calls": state.get("provider_calls", 0),
        "provider_attempts": state.get("provider_attempts", 0),
        "baseline_provider_calls": state.get("baseline_provider_calls", 0),
        "baseline_provider_attempts": state.get("baseline_provider_attempts", 0),
        "c_refinement_fingerprint": state.get("c_refinement_fingerprint"),
        "c_completed_case_ids": state.get("c_completed_case_ids", []),
        "c_refinement_provider_calls_total": state.get("c_refinement_provider_calls_total", 0),
        "c_refinement_provider_attempts_total": state.get("c_refinement_provider_attempts_total", 0),
        "case_count": len(state.get("cases", [])),
        "cases": state.get("cases", []),
    }
    (output_dir / "raw_results.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "blind_mapping.json").write_text(
        json.dumps(state.get("blind_mapping", {}), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    packages = state.get("blind_packages", [])
    (output_dir / "blind_packages.json").write_text(json.dumps(packages, ensure_ascii=False, indent=2), encoding="utf-8")

    sections = [
        "# Editorial Engine v3 Phase 0 — Blind Human Evaluation",
        "",
        "各ケースのX/Y/Zを、生成方式を推測せずに評価してください。主評価は『最後まで読みたいか』『冒頭で続きを読みたいか』『内容が頭に残るか』『AI臭を感じるか』です。",
    ]
    for package in packages:
        sections.extend(["", f"## Case {package['case_id']}"])
        for candidate in package["candidates"]:
            sections.extend(["", f"### Candidate {candidate['label']}", "", candidate["article"]])
    (output_dir / "blind_evaluation.md").write_text("\n".join(sections).strip() + "\n", encoding="utf-8")


def _validate_checkpoint(checkpoint: dict[str, Any] | None) -> None:
    if not checkpoint:
        return
    canonical = {item.case.case_id: _input_digest(item) for item in READY_CASES}
    seen: set[str] = set()
    for case in checkpoint.get("cases", []):
        case_id = str(case.get("case_id") or "")
        if not case_id or case_id in seen or canonical.get(case_id) != case.get("input_digest"):
            raise RuntimeError("Phase 0 checkpoint does not match current immutable inputs")
        seen.add(case_id)


def _rebuild_blind_state(state: dict[str, Any]) -> None:
    packages: list[dict[str, Any]] = []
    mapping: dict[str, dict[str, str]] = {}
    cases = list(state.get("cases", []))
    if state.get("mode") == "C_ONLY_REFINEMENT":
        completed = {str(case_id) for case_id in state.get("c_completed_case_ids", []) if str(case_id)}
        known = {str(case.get("case_id") or "") for case in cases if case.get("case_id")}
        if not completed.issubset(known):
            raise RuntimeError("C-only refinement completed cases do not match checkpoint cases")
        cases = [case for case in cases if str(case.get("case_id") or "") in completed]

    for case in cases:
        outputs = dict(case.get("outputs") or {})
        if set(outputs) != {"A_CURRENT_WRITER", "B_PERSONA_ONLY", "C_EDITORIAL_ENGINE"}:
            raise RuntimeError("C-only refinement requires complete A/B/C baseline outputs")
        blind, case_mapping = build_blind_package(str(case["case_id"]), outputs)
        packages.append(blind)
        mapping[str(case["case_id"])] = case_mapping
    state["blind_packages"] = packages
    state["blind_mapping"] = mapping


def _valid_completed_c_case(case: dict[str, Any]) -> bool:
    outputs = dict(case.get("outputs") or {})
    stages = dict(case.get("editorial_stage_outputs") or {})
    if set(stages) != set(EDITORIAL_STAGES):
        return False
    if any(not str(stages.get(stage) or "").strip() for stage in EDITORIAL_STAGES):
        return False
    final = str(outputs.get("C_EDITORIAL_ENGINE") or "").strip()
    if not final or final != str(stages.get("Fact-Safe Review") or "").strip():
        return False
    try:
        validate_article_layout(str(stages["Persona Article Generation"]))
        validate_article_layout(final)
    except ValueError:
        return False
    return True


def _run_c_only_refinement(
    client: Any,
    *,
    session: ModelSession,
    state: dict[str, Any],
    output_dir: str | Path,
    cooldown: float,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if len(state.get("cases", [])) != EXPECTED_CASES:
        raise RuntimeError("C-only refinement requires a complete three-case baseline checkpoint")
    if not session.locked_model:
        raise RuntimeError("C-only refinement requires the baseline locked model")
    selected_model = str(state.get("selected_model") or "").strip()
    if not selected_model or selected_model != session.locked_model:
        raise RuntimeError("C-only refinement requires the same locked model as the checkpoint")

    baseline_by_id = {str(case.get("case_id") or ""): dict(case) for case in state["cases"]}
    canonical_ids = {item.case.case_id for item in READY_CASES}
    if set(baseline_by_id) != canonical_ids:
        raise RuntimeError("C-only refinement baseline cases do not match current Phase 0 cases")

    for item in READY_CASES:
        baseline_case = baseline_by_id[item.case.case_id]
        if baseline_case.get("input_digest") != _input_digest(item):
            raise RuntimeError("C-only refinement baseline inputs do not match current Phase 0 cases")
        outputs = dict(baseline_case.get("outputs") or {})
        if not outputs.get("A_CURRENT_WRITER") or not outputs.get("B_PERSONA_ONLY"):
            raise RuntimeError("C-only refinement requires preserved A and B outputs")

    current_fingerprint = _c_refinement_fingerprint()
    prior_fingerprint = str(state.get("c_refinement_fingerprint") or "")
    declared_completed = {str(case_id) for case_id in state.get("c_completed_case_ids", []) if str(case_id)}
    prior_calls_total = int(state.get("c_refinement_provider_calls_total", 0) or 0)
    prior_attempts_total = int(state.get("c_refinement_provider_attempts_total", 0) or 0)

    reuse_valid = prior_fingerprint == current_fingerprint
    if reuse_valid:
        invalid_resume = (
            not declared_completed.issubset(canonical_ids)
            or prior_calls_total != len(declared_completed)
            or prior_attempts_total < prior_calls_total
            or any(not _valid_completed_c_case(baseline_by_id[case_id]) for case_id in declared_completed)
        )
        if invalid_resume:
            # Never replay a current-fingerprint completion to repair corrupted
            # data: that would silently consume another provider call. Remove
            # human-facing blind artifacts, but retain raw C for diagnosis.
            state["blind_packages"] = []
            state["blind_mapping"] = {}
            _write_checkpoint(output_dir, state)
            _write_evaluation_artifacts(Path(output_dir), state)
            raise RuntimeError("invalid current C-only refinement checkpoint: resume rejected without provider call")

    if reuse_valid:
        reusable_completed = declared_completed
        cumulative_calls = prior_calls_total
        cumulative_attempts = prior_attempts_total
    else:
        reusable_completed = set()
        cumulative_calls = 0
        cumulative_attempts = 0

    state["mode"] = "C_ONLY_REFINEMENT"
    state.setdefault("baseline_provider_calls", int(state.get("provider_calls", 0)))
    state.setdefault("baseline_provider_attempts", int(state.get("provider_attempts", 0)))
    state["provider_calls"] = 0
    state["provider_attempts"] = 0
    state["c_refinement_fingerprint"] = current_fingerprint
    state["c_completed_case_ids"] = [
        item.case.case_id for item in READY_CASES if item.case.case_id in reusable_completed
    ]
    state["c_refinement_provider_calls_total"] = cumulative_calls
    state["c_refinement_provider_attempts_total"] = cumulative_attempts
    session.provider_attempts = 0

    ordered_cases: list[dict[str, Any]] = []
    for item in READY_CASES:
        case = dict(baseline_by_id[item.case.case_id])
        if item.case.case_id not in reusable_completed:
            outputs = dict(case.get("outputs") or {})
            outputs.pop("C_EDITORIAL_ENGINE", None)
            case["outputs"] = outputs
            case["editorial_stage_outputs"] = {}
        ordered_cases.append(case)

    state["cases"] = ordered_cases
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Normalize all human-facing artifacts before the first provider call. If the
    # first call fails, no stale C from an older fingerprint remains reviewable.
    _rebuild_blind_state(state)
    _write_checkpoint(out_dir, state)
    _write_evaluation_artifacts(out_dir, state)

    missing = [
        (index, item)
        for index, item in enumerate(READY_CASES)
        if item.case.case_id not in reusable_completed
    ]
    successful_calls = 0
    attempts_accounted = 0

    for missing_index, (index, item) in enumerate(missing):
        baseline_case = ordered_cases[index]
        outputs = dict(baseline_case.get("outputs") or {})
        attempts_before = session.provider_attempts
        try:
            editorial, stages = _editorial_article(
                client,
                session=session,
                item=item,
                sleep_fn=sleep_fn,
            )
        except BaseException:
            attempt_delta = session.provider_attempts - attempts_before
            state["provider_attempts"] = session.provider_attempts
            state["c_refinement_provider_attempts_total"] = cumulative_attempts + attempts_accounted + attempt_delta
            _write_checkpoint(out_dir, state)
            _write_evaluation_artifacts(out_dir, state)
            raise

        attempt_delta = session.provider_attempts - attempts_before
        attempts_accounted += attempt_delta
        successful_calls += 1
        cumulative_calls += 1
        outputs["C_EDITORIAL_ENGINE"] = editorial
        ordered_cases[index] = {
            "case_id": item.case.case_id,
            "theme": item.theme,
            "input_digest": _input_digest(item),
            "outputs": outputs,
            "editorial_stage_outputs": stages,
        }
        reusable_completed.add(item.case.case_id)
        state["provider_calls"] = successful_calls
        state["provider_attempts"] = session.provider_attempts
        state["c_refinement_provider_calls_total"] = cumulative_calls
        state["c_refinement_provider_attempts_total"] = cumulative_attempts + attempts_accounted
        state["c_completed_case_ids"] = [
            candidate.case.case_id for candidate in READY_CASES if candidate.case.case_id in reusable_completed
        ]
        state["cases"] = ordered_cases
        _rebuild_blind_state(state)
        _write_checkpoint(out_dir, state)
        _write_evaluation_artifacts(out_dir, state)

        if missing_index + 1 < len(missing) and cooldown:
            sleep_fn(cooldown)

    if reusable_completed != canonical_ids:
        raise RuntimeError(
            f"C-only refinement incomplete after resume: {len(reusable_completed)}/{EXPECTED_CASES}"
        )
    if int(state.get("c_refinement_provider_calls_total", 0)) != C_ONLY_MAX_PROVIDER_CALLS:
        raise RuntimeError(
            "unexpected cumulative C-only provider call count: "
            f"{state.get('c_refinement_provider_calls_total', 0)}"
        )
    return state


def run_phase0(output_dir: str | Path) -> dict[str, Any]:
    api_key = str(os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for Phase 0 live proof")
    if len(READY_CASES) != EXPECTED_CASES:
        raise RuntimeError(f"Phase 0 live proof requires exactly {EXPECTED_CASES} cases")

    from google import genai

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = _load_checkpoint(out_dir)
    _validate_checkpoint(checkpoint)
    candidates = _model_candidates()
    selected_model = str((checkpoint or {}).get("selected_model") or "").strip() or None
    session = ModelSession(candidates=candidates, locked_model=selected_model)
    client = genai.Client(api_key=api_key)
    cooldown = _case_cooldown_seconds()

    if _env_truthy("AIIF_PHASE0_REGENERATE_C_ONLY"):
        if not checkpoint:
            raise RuntimeError("C-only refinement requires a restored baseline checkpoint")
        state = _run_c_only_refinement(
            client,
            session=session,
            state=checkpoint,
            output_dir=out_dir,
            cooldown=cooldown,
        )
        return {
            "model": state.get("selected_model"),
            "mode": state.get("mode"),
            "provider_calls": state.get("provider_calls", 0),
            "provider_attempts": state.get("provider_attempts", 0),
            "case_count": len(state["cases"]),
            "cases": state["cases"],
        }

    state: dict[str, Any] = checkpoint or {
        "selected_model": None,
        "mode": "FULL",
        "provider_calls": 0,
        "provider_attempts": 0,
        "cases": [],
        "blind_packages": [],
        "blind_mapping": {},
    }
    session.provider_attempts = int(state.get("provider_attempts", 0))
    completed = _completed_case_ids(state)
    remaining = [item for item in READY_CASES if item.case.case_id not in completed]

    for index, item in enumerate(remaining):
        current = _current_writer_article(item)
        persona = _persona_only_article(client, session=session, item=item)
        editorial, stages = _editorial_article(client, session=session, item=item)

        provider_calls = int(state.get("provider_calls", 0)) + B_CALLS_PER_CASE + C_CALLS_PER_CASE
        if provider_calls > MAX_PROVIDER_CALLS:
            raise RuntimeError("Phase 0 provider call budget exceeded")

        outputs = {
            "A_CURRENT_WRITER": current,
            "B_PERSONA_ONLY": persona,
            "C_EDITORIAL_ENGINE": editorial,
        }
        blind, mapping = build_blind_package(item.case.case_id, outputs)
        state["selected_model"] = session.locked_model
        state["provider_calls"] = provider_calls
        state["provider_attempts"] = session.provider_attempts
        state["cases"].append(
            {
                "case_id": item.case.case_id,
                "theme": item.theme,
                "input_digest": _input_digest(item),
                "outputs": outputs,
                "editorial_stage_outputs": stages,
            }
        )
        state["blind_packages"].append(blind)
        state["blind_mapping"][item.case.case_id] = mapping
        _write_checkpoint(out_dir, state)
        _write_evaluation_artifacts(out_dir, state)

        if index + 1 < len(remaining) and cooldown:
            time.sleep(cooldown)

    if len(state["cases"]) != EXPECTED_CASES:
        raise RuntimeError(f"Phase 0 incomplete after replay: {len(state['cases'])}/{EXPECTED_CASES}")
    if int(state.get("provider_calls", 0)) != MAX_PROVIDER_CALLS:
        raise RuntimeError(f"unexpected provider call count: {state.get('provider_calls', 0)}")

    raw = {
        "model": state.get("selected_model"),
        "mode": state.get("mode", "FULL"),
        "provider_calls": state.get("provider_calls", 0),
        "provider_attempts": state.get("provider_attempts", 0),
        "case_count": len(state["cases"]),
        "cases": state["cases"],
    }
    return raw


def main() -> None:
    output_dir = os.environ.get("AIIF_PHASE0_OUTPUT_DIR", "phase0_artifacts")
    result = run_phase0(output_dir)
    print(
        f"Phase 0 live proof complete: mode={result.get('mode', 'FULL')} cases={result['case_count']} "
        f"provider_calls={result['provider_calls']} attempts={result['provider_attempts']} model={result['model']}"
    )


if __name__ == "__main__":
    main()
