"""AIIF Rebuild V2-004 provider-backed evidence shadow slice.

V2-004 is deliberately diagnostic-only. It reuses V2-002 bounded public
metadata acquisition and V2-001 rank-1-only Deep Dive selection, then permits
one provider request to one approved non-Lite model. It never grants Production
authority and never writes Notion, note, queues, Ready state, or publication
state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from v2_live_shadow_acquisition import LiveAcquisitionConfig, run_bounded_live_shadow


DEFAULT_MODEL = "gemini-3.6-flash"
GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
PROVIDER_TIMEOUT_SECONDS = 120.0
MAX_EVIDENCE_POINTS = 5
MAX_EVIDENCE_POINT_CHARS = 500
_ALLOWED_REASON_CODES = {
    "sufficient_source_evidence",
    "insufficient_source_evidence",
}
_REQUIRED_RESULT_KEYS = {
    "evidence_sufficient",
    "reason_code",
    "evidence_points",
}


class EvidenceContractError(ValueError):
    """Provider output did not satisfy the V2-004 strict evidence contract."""


class GeminiEvidenceError(RuntimeError):
    """Opaque Gemini boundary failure safe for V2 structured reporting."""


def _validate_evidence_mapping(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise EvidenceContractError("result_not_object")
    if set(payload.keys()) != _REQUIRED_RESULT_KEYS:
        raise EvidenceContractError("result_keys_invalid")

    sufficient = payload.get("evidence_sufficient")
    if type(sufficient) is not bool:  # bool only; int 0/1 is forbidden
        raise EvidenceContractError("evidence_sufficient_not_boolean")

    reason_code = payload.get("reason_code")
    if not isinstance(reason_code, str) or reason_code not in _ALLOWED_REASON_CODES:
        raise EvidenceContractError("reason_code_invalid")
    expected_reason = "sufficient_source_evidence" if sufficient else "insufficient_source_evidence"
    if reason_code != expected_reason:
        raise EvidenceContractError("reason_code_contradicts_boolean")

    points = payload.get("evidence_points")
    if not isinstance(points, list) or not 1 <= len(points) <= MAX_EVIDENCE_POINTS:
        raise EvidenceContractError("evidence_points_invalid")
    normalized_points: list[str] = []
    for point in points:
        if not isinstance(point, str):
            raise EvidenceContractError("evidence_point_not_text")
        text = " ".join(point.split()).strip()
        if not text or len(text) > MAX_EVIDENCE_POINT_CHARS:
            raise EvidenceContractError("evidence_point_invalid")
        normalized_points.append(text)

    return {
        "evidence_sufficient": sufficient,
        "reason_code": reason_code,
        "evidence_points": normalized_points,
    }


def parse_evidence_result(text: str) -> dict[str, Any]:
    """Parse strict JSON only. Markdown fences or any non-JSON wrapper fail closed."""

    if not isinstance(text, str):
        raise EvidenceContractError("result_not_text")
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        raise EvidenceContractError("result_invalid_json") from None
    return _validate_evidence_mapping(payload)


def build_deep_dive_prompt(candidate: Mapping[str, Any]) -> str:
    """Build a bounded prompt from fields already acquired by V2-001/V2-002."""

    payload = {
        "candidate_identity": str(candidate.get("candidate_identity") or ""),
        "provider": str(candidate.get("provider") or ""),
        "primary_url": str(candidate.get("primary_url") or ""),
        "title": str(candidate.get("title") or ""),
        "description": str(candidate.get("description") or ""),
        "source_timestamp": candidate.get("source_timestamp"),
        "screening_score": int(candidate.get("screening_score") or 0),
        "screening_reasons": list(candidate.get("screening_reasons") or []),
    }
    return (
        "You are the bounded Evidence judge for AIIF V2 shadow evaluation.\n"
        "Use ONLY the supplied candidate metadata. Do not invent, browse, or infer unsupported facts.\n"
        "Decide whether this metadata alone contains enough concrete evidence to justify a shadow winner.\n"
        "Return JSON only with exactly these keys: evidence_sufficient, reason_code, evidence_points.\n"
        "reason_code must be sufficient_source_evidence when true, otherwise insufficient_source_evidence.\n"
        "evidence_points must contain 1 to 5 concise factual points grounded only in the supplied metadata.\n"
        "Candidate metadata:\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


class GeminiEvidenceProvider:
    """One-request Gemini adapter with no retry and no model fallback."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_MODEL,
        http_post: Callable[..., Any] = requests.post,
    ) -> None:
        key = str(api_key or "").strip()
        if not key:
            raise ValueError("GEMINI_API_KEY is required")
        if model != DEFAULT_MODEL:
            raise ValueError("V2-004 permits only gemini-3.6-flash")
        self._api_key = key
        self.model = model
        self._http_post = http_post

    def __call__(self, candidate: Mapping[str, Any]) -> Mapping[str, Any]:
        url = GEMINI_GENERATE_URL.format(model=self.model)
        request_payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_deep_dive_prompt(candidate)}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 700,
                "responseMimeType": "application/json",
            },
        }
        try:
            response = self._http_post(
                url,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self._api_key,
                },
                json=request_payload,
                timeout=PROVIDER_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
        except Exception:
            raise GeminiEvidenceError("provider_request_failed") from None

        try:
            candidates = body["candidates"]
            first = candidates[0]
            parts = first["content"]["parts"]
            text = parts[0]["text"]
        except (KeyError, IndexError, TypeError):
            raise GeminiEvidenceError("provider_response_shape_invalid") from None
        try:
            return parse_evidence_result(text)
        except EvidenceContractError:
            raise GeminiEvidenceError("provider_evidence_contract_invalid") from None


def build_provider_backed_observation(
    *,
    now: datetime,
    run_id: str,
    config: LiveAcquisitionConfig | None = None,
    http_get: Callable[..., Any] = requests.get,
    deep_dive: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    api_key: str | None = None,
    http_post: Callable[..., Any] = requests.post,
    model: str = DEFAULT_MODEL,
    v1_reference: str | None = None,
) -> dict[str, Any]:
    """Run bounded live acquisition and one strict rank-1 evidence request."""

    provider: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    if deep_dive is None:
        provider = GeminiEvidenceProvider(
            api_key=str(api_key or ""),
            model=model,
            http_post=http_post,
        )
    else:
        provider = deep_dive

    provider_result: dict[str, Any] | None = None
    provider_error_category: str | None = None

    def audited_deep_dive(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal provider_result, provider_error_category
        try:
            raw_result = provider(candidate)
            provider_result = _validate_evidence_mapping(raw_result)
            return provider_result
        except Exception as exc:
            provider_error_category = type(exc).__name__
            raise

    report = run_bounded_live_shadow(
        deep_dive=audited_deep_dive,
        now=now,
        run_id=run_id,
        config=config,
        http_get=http_get,
        v1_reference=v1_reference,
        max_deep_dive_attempts=1,
    )
    return {
        **report,
        "observation": {
            "mode": "provider_backed_one_shot",
            "model": model,
            "request_budget": 1,
            "provider_result": provider_result,
            "provider_error_category": provider_error_category,
            "production_authority": "v1",
            "diagnostic_only": True,
        },
    }


def write_observation(report: Mapping[str, Any], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(report), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run V2-004 provider-backed shadow evidence observation")
    parser.add_argument("--output", default="article_audit/v2_shadow_deep_dive.json")
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    report = build_provider_backed_observation(
        now=datetime.now(timezone.utc),
        run_id=args.run_id,
        api_key=os.environ.get("GEMINI_API_KEY"),
    )
    output = write_observation(report, args.output)
    print(
        json.dumps(
            {
                "artifact": str(output),
                "mode": report["observation"]["mode"],
                "model": report["observation"]["model"],
                "deep_dive_calls": report["actual_calls"]["deep_dive"],
                "v2_selected_candidate_identity": report["v2_selected_candidate_identity"],
                "production_authority": "v1",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
