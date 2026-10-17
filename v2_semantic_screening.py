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
_SEMANTIC_BOOLEAN_FIELDS = (
    "ai_relevant",
    "decision_value",
    "change_novelty",
    "applied_reader_value",
)
SEMANTIC_FIELDS = _SEMANTIC_BOOLEAN_FIELDS
_REQUIRED_ITEM_KEYS = {"candidate_identity", *_SEMANTIC_BOOLEAN_FIELDS}
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
    "semantic_provider_uninformative_saturated",
}
_GOLD_TOP_LEVEL_KEYS = {"benchmark_version", "label_contract", "cases"}
_GOLD_CASE_KEYS = {
    "case_id",
    "title",
    "description",
    "source_family",
    "gold",
    "rationale",
    "label_provenance",
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


class GoldBenchmarkContractError(ValueError):
    """Offline Gold benchmark input did not satisfy the strict contract."""


def validate_gold_dataset(payload: Any) -> list[dict[str, Any]]:
    """Validate and copy the human-authored V2 Semantic Gold dataset."""

    if not isinstance(payload, Mapping) or set(payload) != _GOLD_TOP_LEVEL_KEYS:
        raise GoldBenchmarkContractError("gold_dataset_shape_invalid")
    if payload.get("benchmark_version") != "v1":
        raise GoldBenchmarkContractError("gold_benchmark_version_invalid")
    if payload.get("label_contract") != "v2_semantic_screening":
        raise GoldBenchmarkContractError("gold_label_contract_invalid")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise GoldBenchmarkContractError("gold_cases_invalid")

    seen: set[str] = set()
    validated: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, Mapping) or set(case) != _GOLD_CASE_KEYS:
            raise GoldBenchmarkContractError("gold_case_shape_invalid")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            raise GoldBenchmarkContractError("gold_case_id_invalid")
        for key in ("title", "description", "source_family", "rationale", "label_provenance"):
            if not isinstance(case.get(key), str):
                raise GoldBenchmarkContractError(f"gold_case_{key}_invalid")
        if not str(case.get("rationale") or "").strip() or not str(case.get("label_provenance") or "").strip():
            raise GoldBenchmarkContractError("gold_case_review_metadata_invalid")
        gold = case.get("gold")
        if not isinstance(gold, Mapping) or set(gold) != set(SEMANTIC_FIELDS):
            raise GoldBenchmarkContractError("gold_vector_shape_invalid")
        if any(type(gold.get(field)) is not bool for field in SEMANTIC_FIELDS):
            raise GoldBenchmarkContractError("gold_vector_boolean_invalid")
        seen.add(case_id)
        validated.append(
            {
                "case_id": case_id,
                "title": case["title"],
                "description": case["description"],
                "source_family": case["source_family"],
                "gold": {field: gold[field] for field in SEMANTIC_FIELDS},
                "rationale": case["rationale"],
                "label_provenance": case["label_provenance"],
            }
        )
    return validated


def _validate_gold_predictions(
    gold_cases: Sequence[Mapping[str, Any]],
    predictions: Any,
) -> dict[str, dict[str, bool]]:
    if not isinstance(predictions, Mapping):
        raise GoldBenchmarkContractError("prediction_shape_invalid")
    case_ids = [str(case.get("case_id") or "") for case in gold_cases]
    if set(predictions) != set(case_ids) or len(predictions) != len(case_ids):
        raise GoldBenchmarkContractError("prediction_case_ids_invalid")
    validated: dict[str, dict[str, bool]] = {}
    for case_id in case_ids:
        row = predictions.get(case_id)
        if not isinstance(row, Mapping) or set(row) != set(SEMANTIC_FIELDS):
            raise GoldBenchmarkContractError("prediction_vector_shape_invalid")
        if any(type(row.get(field)) is not bool for field in SEMANTIC_FIELDS):
            raise GoldBenchmarkContractError("prediction_vector_boolean_invalid")
        validated[case_id] = {field: row[field] for field in SEMANTIC_FIELDS}
    return validated


def _safe_ratio(numerator: int, denominator: int) -> float:
    return float(numerator / denominator) if denominator else 0.0


def evaluate_gold_predictions(
    gold_cases: Sequence[Mapping[str, Any]],
    predictions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Evaluate predictions against reviewed Gold labels without provider calls."""

    cases = list(gold_cases)
    validated_predictions = _validate_gold_predictions(cases, predictions)
    dimensions: dict[str, dict[str, int | float]] = {}
    exact_matches = 0
    all_positive = 0

    for field in SEMANTIC_FIELDS:
        tp = fp = tn = fn = 0
        for case in cases:
            case_id = str(case.get("case_id") or "")
            gold = case.get("gold")
            if not isinstance(gold, Mapping) or type(gold.get(field)) is not bool:
                raise GoldBenchmarkContractError("gold_cases_not_validated")
            expected = gold[field]
            predicted = validated_predictions[case_id][field]
            if expected and predicted:
                tp += 1
            elif not expected and predicted:
                fp += 1
            elif not expected and not predicted:
                tn += 1
            else:
                fn += 1
        precision = _safe_ratio(tp, tp + fp)
        recall = _safe_ratio(tp, tp + fn)
        f1 = _safe_ratio(2 * precision * recall, precision + recall)
        dimensions[field] = {
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    for case in cases:
        case_id = str(case.get("case_id") or "")
        gold = case.get("gold")
        if not isinstance(gold, Mapping):
            raise GoldBenchmarkContractError("gold_cases_not_validated")
        predicted = validated_predictions[case_id]
        if all(predicted[field] is gold[field] for field in SEMANTIC_FIELDS):
            exact_matches += 1
        if all(predicted[field] is True for field in SEMANTIC_FIELDS):
            all_positive += 1

    sample_count = len(cases)
    macro = {
        metric: sum(float(dimensions[field][metric]) for field in SEMANTIC_FIELDS) / len(SEMANTIC_FIELDS)
        for metric in ("precision", "recall", "f1")
    }
    return {
        "sample_count": sample_count,
        "dimensions": dimensions,
        "macro": macro,
        "exact_match_accuracy": _safe_ratio(exact_matches, sample_count),
        "all_positive_saturation_rate": _safe_ratio(all_positive, sample_count),
    }


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
        "Classify each candidate independently and conservatively. A true value requires direct support in the supplied title or description.\n"
        "When evidence is missing, ambiguous, or merely plausible, classify that dimension false.\n"
        "Provider or source identity alone is not evidence, and engagement metadata such as scores or comment counts is not semantic evidence.\n"
        "Do not make every candidate positive merely because this is an AI screening task. It is valid for many candidates to be false.\n"
        "For every candidate, classify four boolean dimensions:\n"
        "- ai_relevant: AI/ML, models, agents, inference, robotics, or AI deployment is a material core subject, not merely a tangential association.\n"
        "- decision_value: the metadata states a concrete decision lever such as capability, pricing, cost, API behavior, compatibility, security, policy, deployment, availability, or measurable performance. Generic interest is false.\n"
        "- change_novelty: the metadata explicitly states what meaningfully launched, changed, improved, partnered, became available, or was newly found. Recency or feed appearance alone is false.\n"
        "- applied_reader_value: the metadata directly supports implementation, workflow, productivity, coding, automation, integration, deployment, or customer-use implications. Hypothetical usefulness is false.\n"
        "If ai_relevant is false, the other three dimensions must also be false.\n"
        "Calibration examples: an electric sports-car product page with only engagement counts is all false; historical cryptography research with no AI subject is all false; an AI inference API release with explicit pricing, security, and deployment changes can be all true.\n"
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


def _is_uninformative_positive_saturation(parsed: Mapping[str, Mapping[str, Any]]) -> bool:
    """Reject a large batch when almost every row is indiscriminately all-positive."""

    rows = [row for row in parsed.values() if isinstance(row, Mapping)]
    if len(rows) < 4:
        return False
    all_positive = sum(
        1
        for row in rows
        if all(row.get(field) is True for field in _SEMANTIC_BOOLEAN_FIELDS)
    )
    return all_positive * 10 >= len(rows) * 9


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
            parsed = parse_semantic_screening_result(text, expected_identities=identities)
        except SemanticScreeningContractError:
            raise SemanticScreeningError("semantic_provider_contract_invalid") from None
        if _is_uninformative_positive_saturation(parsed):
            raise SemanticScreeningError("semantic_provider_uninformative_saturated")
        return parsed
