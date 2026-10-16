"""Bounded Gemini Flash-Lite semantic screening for AIIF V2 shadow only.

This module is intentionally isolated from Production authority. Each adapter
instance performs at most one batched Gemini request, exposes no persistence
hooks, and returns only a strict boolean classification contract keyed by
candidate identity. Variable fallback is owned by the V2 live proof wrapper so
Factory code remains the sole retry owner.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Mapping, Sequence

import requests

from run260_gemini_model_routing import DEFAULT_SCREENING_POOL


SEMANTIC_MODEL_POOL = tuple(DEFAULT_SCREENING_POOL)
DEFAULT_SEMANTIC_MODEL = SEMANTIC_MODEL_POOL[0]
GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
SEMANTIC_TIMEOUT_SECONDS = 90.0
MAX_SEMANTIC_CANDIDATES = 20
_REQUIRED_ITEM_KEYS = {
    "candidate_identity",
    "ai_relevant",
    "decision_value",
    "change_novelty",
    "applied_reader_value",
}
_SAFE_ERROR_CODES = {
    "semantic_provider_request_failed",
    "semantic_provider_http_400",
    "semantic_provider_http_401_403",
    "semantic_provider_http_404",
    "semantic_provider_http_429",
    "semantic_provider_http_5xx",
    "semantic_provider_timeout",
    "semantic_provider_connection_error",
    "semantic_provider_response_json_invalid",
    "semantic_provider_response_shape_invalid",
    "semantic_provider_contract_invalid",
}


class SemanticScreeningContractError(ValueError):
    """Gemini output did not satisfy the strict semantic screening contract."""


class SemanticScreeningError(RuntimeError):
    """Opaque provider-boundary failure safe for V2 diagnostics."""

    def __init__(self, safe_code: str) -> None:
        if safe_code not in _SAFE_ERROR_CODES:
            raise ValueError("unsupported semantic screening error code")
        self.safe_code = safe_code
        super().__init__(safe_code)


def _safe_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidate_identity": str(candidate.get("candidate_identity") or ""),
        "provider": str(candidate.get("provider") or ""),
        "primary_url": str(candidate.get("primary_url") or ""),
        "title": str(candidate.get("title") or ""),
        "description": str(candidate.get("description") or ""),
        "source_timestamp": candidate.get("source_timestamp"),
    }


def build_semantic_screening_prompt(candidates: Sequence[Mapping[str, Any]]) -> str:
    """Build a bounded prompt from source metadata only, never AIIF internal scores."""

    safe = [_safe_candidate(candidate) for candidate in candidates[:MAX_SEMANTIC_CANDIDATES]]
    return (
        "You are the bounded semantic screening judge for AIIF V2 shadow evaluation.\n"
        "Use ONLY the supplied source metadata. Do not browse, invent, or infer unsupported facts.\n"
        "For every candidate, classify four independent boolean dimensions:\n"
        "- ai_relevant: the subject is materially about AI/ML, models, agents, inference, robotics, or AI deployment.\n"
        "- decision_value: it can affect a business, product, technical, security, policy, cost, or adoption decision.\n"
        "- change_novelty: it describes a meaningful launch, release, update, benchmark, partnership, policy change, or new finding.\n"
        "- applied_reader_value: it has plausible practical value for implementation, workflow, productivity, coding, automation, integration, deployment, or customers.\n"
        "Return JSON only with exactly one top-level key named results.\n"
        "results must contain exactly one object per supplied candidate and no extras.\n"
        "Each object must contain exactly candidate_identity, ai_relevant, decision_value, change_novelty, applied_reader_value.\n"
        "All four classification fields must be JSON booleans. Preserve candidate_identity exactly.\n"
        "Candidates:\n"
        + json.dumps(safe, ensure_ascii=False, sort_keys=True)
    )


def parse_semantic_screening_result(
    text: str,
    *,
    expected_identities: Sequence[str],
) -> dict[str, dict[str, Any]]:
    """Parse strict JSON and require an exact identity-preserving result set."""

    if not isinstance(text, str):
        raise SemanticScreeningContractError("result_not_text")
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        raise SemanticScreeningContractError("result_invalid_json") from None
    if not isinstance(payload, Mapping) or set(payload) != {"results"}:
        raise SemanticScreeningContractError("result_shape_invalid")
    rows = payload.get("results")
    if not isinstance(rows, list) or len(rows) > MAX_SEMANTIC_CANDIDATES:
        raise SemanticScreeningContractError("results_invalid")

    parsed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != _REQUIRED_ITEM_KEYS:
            raise SemanticScreeningContractError("result_item_invalid")
        identity = row.get("candidate_identity")
        if not isinstance(identity, str) or not identity or identity in parsed:
            raise SemanticScreeningContractError("result_identity_invalid")
        for key in _REQUIRED_ITEM_KEYS - {"candidate_identity"}:
            if type(row.get(key)) is not bool:
                raise SemanticScreeningContractError("result_boolean_invalid")
        parsed[identity] = dict(row)

    expected = [str(identity) for identity in expected_identities]
    if len(expected) > MAX_SEMANTIC_CANDIDATES or set(parsed) != set(expected) or len(parsed) != len(expected):
        raise SemanticScreeningContractError("result_identities_invalid")
    return parsed


def _classify_http_status(status_code: int) -> str:
    if status_code == 400:
        return "semantic_provider_http_400"
    if status_code in {401, 403}:
        return "semantic_provider_http_401_403"
    if status_code == 404:
        return "semantic_provider_http_404"
    if status_code == 429:
        return "semantic_provider_http_429"
    if 500 <= status_code <= 599:
        return "semantic_provider_http_5xx"
    return "semantic_provider_request_failed"


class GeminiSemanticScreeningProvider:
    """One-batch Gemini Flash-Lite adapter for one approved V1 screening model."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_SEMANTIC_MODEL,
        http_post: Callable[..., Any] = requests.post,
    ) -> None:
        key = str(api_key or "").strip()
        if not key:
            raise ValueError("GEMINI_API_KEY is required")
        if model not in SEMANTIC_MODEL_POOL:
            raise ValueError("V2 semantic screening permits only the V1 Flash-Lite screening pool")
        self._api_key = key
        self.model = model
        self._http_post = http_post

    def __call__(self, candidates: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
        bounded = list(candidates[:MAX_SEMANTIC_CANDIDATES])
        if not bounded:
            return {}
        identities = [str(candidate.get("candidate_identity") or "") for candidate in bounded]
        if any(not identity for identity in identities) or len(set(identities)) != len(identities):
            raise SemanticScreeningError("semantic_provider_contract_invalid")

        request_payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": build_semantic_screening_prompt(bounded)}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": 1800,
                "responseMimeType": "application/json",
            },
        }
        url = GEMINI_GENERATE_URL.format(model=self.model)
        try:
            response = self._http_post(
                url,
                headers={"Content-Type": "application/json", "x-goog-api-key": self._api_key},
                json=request_payload,
                timeout=SEMANTIC_TIMEOUT_SECONDS,
            )
        except (requests.Timeout, TimeoutError):
            raise SemanticScreeningError("semantic_provider_timeout") from None
        except (requests.ConnectionError, ConnectionError):
            raise SemanticScreeningError("semantic_provider_connection_error") from None
        except Exception:
            raise SemanticScreeningError("semantic_provider_request_failed") from None

        status_code = getattr(response, "status_code", None)
        if isinstance(status_code, int) and status_code >= 400:
            raise SemanticScreeningError(_classify_http_status(status_code)) from None
        try:
            response.raise_for_status()
        except Exception:
            raise SemanticScreeningError("semantic_provider_request_failed") from None
        try:
            body = response.json()
        except (ValueError, TypeError):
            raise SemanticScreeningError("semantic_provider_response_json_invalid") from None
        except Exception:
            raise SemanticScreeningError("semantic_provider_request_failed") from None
        try:
            text = body["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError):
            raise SemanticScreeningError("semantic_provider_response_shape_invalid") from None
        try:
            return parse_semantic_screening_result(text, expected_identities=identities)
        except SemanticScreeningContractError:
            raise SemanticScreeningError("semantic_provider_contract_invalid") from None
