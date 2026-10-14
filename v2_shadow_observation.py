"""AIIF Rebuild V2-003/V2-004 bounded shadow observation runner.

Default behaviour remains the V2-003 manual zero-model observation. V2-004 adds
an explicitly selected provider-backed mode that permits exactly one evidence
request for eligible rank 1. Neither mode grants V2 Production authority or
writes Notion, note, queues, Ready state, or publication state.
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


OBSERVATION_MODE = "manual_zero_model"
PROVIDER_BACKED_MODE = "provider_backed_one_shot"
DEFAULT_OUTPUT_PATH = Path("article_audit/v2_shadow_observation.json")
DEFAULT_DEEP_DIVE_OUTPUT_PATH = Path("article_audit/v2_shadow_deep_dive.json")
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
_SAFE_PROVIDER_ERROR_CODES = {
    "provider_request_failed",
    "provider_http_400",
    "provider_http_401_403",
    "provider_http_404",
    "provider_http_429",
    "provider_http_5xx",
    "provider_timeout",
    "provider_connection_error",
    "provider_response_json_invalid",
    "provider_response_shape_invalid",
    "provider_evidence_contract_invalid",
}


class EvidenceContractError(ValueError):
    """Provider output did not satisfy the V2-004 strict evidence contract."""


class GeminiEvidenceError(RuntimeError):
    """Opaque provider-boundary failure safe for structured shadow reporting."""

    def __init__(self, safe_code: str) -> None:
        if safe_code not in _SAFE_PROVIDER_ERROR_CODES:
            raise ValueError("unsupported Gemini evidence error code")
        self.safe_code = safe_code
        super().__init__(safe_code)


def _forbidden_deep_dive(_: Mapping[str, Any]) -> Mapping[str, Any]:
    raise RuntimeError("zero-model observation attempted Deep Dive")


def derive_pre_deep_dive_leader(report: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return rank 1 as observation metadata, never as a selected winner."""

    screening = report.get("screening")
    if not isinstance(screening, list) or not screening:
        return None
    first = screening[0]
    if not isinstance(first, Mapping):
        return None
    return {
        "candidate_identity": first.get("candidate_identity"),
        "provider": first.get("provider"),
        "screening_score": first.get("screening_score"),
        "eligible": bool(first.get("eligible")),
    }


def build_manual_observation(
    *,
    now: datetime,
    run_id: str,
    config: LiveAcquisitionConfig | None = None,
    http_get: Callable[..., Any] = requests.get,
) -> dict[str, Any]:
    """Build one bounded live observation with Deep Dive physically disabled."""

    report = run_bounded_live_shadow(
        deep_dive=_forbidden_deep_dive,
        now=now,
        run_id=run_id,
        config=config,
        http_get=http_get,
        v1_reference=None,
        max_deep_dive_attempts=0,
    )

    actual_calls = report.get("actual_calls")
    if report.get("deep_dive_attempted_count") != 0:
        raise RuntimeError("zero-model observation recorded a Deep Dive attempt")
    if not isinstance(actual_calls, Mapping) or actual_calls.get("deep_dive") != 0:
        raise RuntimeError("zero-model observation recorded a Deep Dive call")
    if report.get("v2_selected_candidate_identity") is not None:
        raise RuntimeError("zero-model observation must not claim a V2 winner")

    return {
        **report,
        "observation": {
            "mode": OBSERVATION_MODE,
            "production_authority": "v1",
            "artifact_role": "diagnostic",
        },
        "pre_deep_dive_leader": derive_pre_deep_dive_leader(report),
    }


def _validate_evidence_mapping(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise EvidenceContractError("result_not_object")
    if set(payload.keys()) != _REQUIRED_RESULT_KEYS:
        raise EvidenceContractError("result_keys_invalid")

    sufficient = payload.get("evidence_sufficient")
    if type(sufficient) is not bool:
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
    """Parse strict JSON only; wrappers such as Markdown fences fail closed."""

    if not isinstance(text, str):
        raise EvidenceContractError("result_not_text")
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        raise EvidenceContractError("result_invalid_json") from None
    return _validate_evidence_mapping(payload)


def build_deep_dive_prompt(candidate: Mapping[str, Any]) -> str:
    """Build a bounded prompt only from metadata already acquired by V2-001/002."""

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


def _classify_provider_http_status(status_code: int) -> str:
    if status_code == 400:
        return "provider_http_400"
    if status_code in {401, 403}:
        return "provider_http_401_403"
    if status_code == 404:
        return "provider_http_404"
    if status_code == 429:
        return "provider_http_429"
    if 500 <= status_code <= 599:
        return "provider_http_5xx"
    return "provider_request_failed"


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
        except (requests.Timeout, TimeoutError):
            raise GeminiEvidenceError("provider_timeout") from None
        except (requests.ConnectionError, ConnectionError):
            raise GeminiEvidenceError("provider_connection_error") from None
        except Exception:
            raise GeminiEvidenceError("provider_request_failed") from None

        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int) and status_code >= 400:
            raise GeminiEvidenceError(_classify_provider_http_status(status_code)) from None

        try:
            response.raise_for_status()
        except Exception:
            raise GeminiEvidenceError("provider_request_failed") from None

        try:
            body = response.json()
        except (ValueError, TypeError):
            raise GeminiEvidenceError("provider_response_json_invalid") from None
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
    """Run bounded acquisition and at most one strict rank-1 evidence request."""

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
            provider_error_category = (
                exc.safe_code if isinstance(exc, GeminiEvidenceError) else type(exc).__name__
            )
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
            "mode": PROVIDER_BACKED_MODE,
            "model": model,
            "request_budget": 1,
            "provider_result": provider_result,
            "provider_error_category": provider_error_category,
            "production_authority": "v1",
            "diagnostic_only": True,
        },
    }


def write_observation(report: Mapping[str, Any], output_path: str | Path) -> Path:
    """Write exactly one deterministic UTF-8 JSON observation artifact."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        dict(report),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    path.write_text(payload, encoding="utf-8")
    return path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded V2 shadow observation")
    parser.add_argument("--output", default=None)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--mode",
        choices=(OBSERVATION_MODE, PROVIDER_BACKED_MODE),
        default=OBSERVATION_MODE,
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.mode == PROVIDER_BACKED_MODE:
        report = build_provider_backed_observation(
            now=datetime.now(timezone.utc),
            run_id=args.run_id,
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
        output = args.output or str(DEFAULT_DEEP_DIVE_OUTPUT_PATH)
    else:
        report = build_manual_observation(
            now=datetime.now(timezone.utc),
            run_id=args.run_id,
        )
        output = args.output or str(DEFAULT_OUTPUT_PATH)
    write_observation(report, output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
