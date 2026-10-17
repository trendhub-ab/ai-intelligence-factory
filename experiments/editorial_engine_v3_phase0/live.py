from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from local_skills.compiler import compile_snapshot

from .cases import READY_CASES, ReplayCase
from .contract import EDITORIAL_STAGES
from .prompts import build_editorial_bundle_prompt, build_persona_only_prompt
from .runner import build_blind_package, build_current_writer_snapshot

DEFAULT_MODEL = "gemini-3.6-flash"
B_CALLS_PER_CASE = 1
C_CALLS_PER_CASE = 1
EXPECTED_CASES = 3
MAX_PROVIDER_CALLS = EXPECTED_CASES * (B_CALLS_PER_CASE + C_CALLS_PER_CASE)


def _provider_text(client: Any, *, model: str, prompt: str) -> str:
    response = client.models.generate_content(model=model, contents=prompt)
    text = str(getattr(response, "text", "") or "").strip()
    if not text:
        raise RuntimeError("Gemini returned an empty Phase 0 response")
    return text


def _current_writer_article(item: ReplayCase) -> str:
    snapshot = build_current_writer_snapshot(item)
    compiled = compile_snapshot(snapshot, evidence_context="\n".join(item.case.evidence))
    parsed = dict(compiled["parsed"])
    title = str(parsed.get("title_text") or "").strip()
    body = str(parsed.get("note_draft") or "").strip()
    if not title or not body:
        raise RuntimeError(f"Current Writer produced an incomplete article for {item.case.case_id}")
    return f"# {title}\n\n{body}".strip()


def _persona_only_article(client: Any, *, model: str, item: ReplayCase) -> str:
    return _provider_text(client, model=model, prompt=build_persona_only_prompt(item.case))


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

    return stages["Editorial Review"], stages


def _editorial_article(client: Any, *, model: str, item: ReplayCase) -> tuple[str, dict[str, str]]:
    bundle = _provider_text(client, model=model, prompt=build_editorial_bundle_prompt(item.case))
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


def run_phase0(output_dir: str | Path) -> dict[str, Any]:
    api_key = str(os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for Phase 0 live proof")
    model = str(os.environ.get("AIIF_PHASE0_MODEL") or DEFAULT_MODEL).strip()
    if not model or "lite" in model.lower():
        raise RuntimeError("Phase 0 requires one fixed non-Lite Gemini model")
    if len(READY_CASES) != EXPECTED_CASES:
        raise RuntimeError(f"Phase 0 live proof requires exactly {EXPECTED_CASES} cases")

    from google import genai

    client = genai.Client(api_key=api_key)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_cases: list[dict[str, Any]] = []
    blind_packages: list[dict[str, Any]] = []
    blind_mapping: dict[str, dict[str, str]] = {}
    provider_calls = 0

    for item in READY_CASES:
        current = _current_writer_article(item)
        persona = _persona_only_article(client, model=model, item=item)
        provider_calls += B_CALLS_PER_CASE
        editorial, stages = _editorial_article(client, model=model, item=item)
        provider_calls += C_CALLS_PER_CASE
        if provider_calls > MAX_PROVIDER_CALLS:
            raise RuntimeError("Phase 0 provider call budget exceeded")

        outputs = {
            "A_CURRENT_WRITER": current,
            "B_PERSONA_ONLY": persona,
            "C_EDITORIAL_ENGINE": editorial,
        }
        blind, mapping = build_blind_package(item.case.case_id, outputs)
        blind_packages.append(blind)
        blind_mapping[item.case.case_id] = mapping
        raw_cases.append(
            {
                "case_id": item.case.case_id,
                "theme": item.theme,
                "input_digest": _input_digest(item),
                "outputs": outputs,
                "editorial_stage_outputs": stages,
            }
        )

    if provider_calls != MAX_PROVIDER_CALLS:
        raise RuntimeError(f"unexpected provider call count: {provider_calls}")

    raw = {
        "model": model,
        "provider_calls": provider_calls,
        "case_count": len(raw_cases),
        "cases": raw_cases,
    }
    (out_dir / "raw_results.json").write_text(
        json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "blind_mapping.json").write_text(
        json.dumps(blind_mapping, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "blind_packages.json").write_text(
        json.dumps(blind_packages, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    sections = [
        "# Editorial Engine v3 Phase 0 — Blind Human Evaluation",
        "",
        "各ケースのX/Y/Zを、生成方式を推測せずに評価してください。主評価は『最後まで読みたいか』『冒頭で続きを読みたいか』『内容が頭に残るか』『AI臭を感じるか』です。",
    ]
    for package in blind_packages:
        sections.extend(["", f"## Case {package['case_id']}"])
        for candidate in package["candidates"]:
            sections.extend(["", f"### Candidate {candidate['label']}", "", candidate["article"]])
    (out_dir / "blind_evaluation.md").write_text("\n".join(sections).strip() + "\n", encoding="utf-8")

    return raw


def main() -> None:
    output_dir = os.environ.get("AIIF_PHASE0_OUTPUT_DIR", "phase0_artifacts")
    result = run_phase0(output_dir)
    print(
        f"Phase 0 live proof complete: cases={result['case_count']} "
        f"provider_calls={result['provider_calls']} model={result['model']}"
    )


if __name__ == "__main__":
    main()
