"""AIIF Rebuild V2-005 measured four-source live shadow proof.

This module wraps the V2 four-source shadow path with safe measurement only.
Semantic Screening uses the V1 Flash-Lite lane with health-aware distinct-model
fallback; rank-1 Evidence uses the V1 full-Flash Deep Dive lane the same way.
A valid Evidence verdict, including insufficient evidence, stops fallback. Only
provider/transport/contract failure advances to another distinct model. V2 does
not grant Production authority and does not write Notion, note, Ready state,
queues, delivery ledgers, or publication state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

import requests

from run260_gemini_model_routing import (
    DEFAULT_DEEP_DIVE_POOL,
    DEFAULT_SCREENING_POOL,
    _health_ranked_pool,
    _health_ranked_screening_pool,
    _load_provider_health_history,
)
from v2_four_source_live import FourSourceLiveConfig, run_four_source_live
from v2_semantic_screening import (
    GeminiSemanticScreeningProvider,
    SemanticScreeningError,
)
from v2_shadow_observation import (
    DEFAULT_DEEP_DIVE_OUTPUT_PATH,
    GeminiEvidenceError,
    GeminiEvidenceProvider,
    PROVIDER_BACKED_MODE,
    write_observation,
)


PROOF_VERSION = "V2-005"
PROMOTION_DECISION = "human_review_required"
SEMANTIC_MODEL_POOL = tuple(DEFAULT_SCREENING_POOL)
EVIDENCE_MODEL_POOL = tuple(DEFAULT_DEEP_DIVE_POOL)
_TERMINAL_SEMANTIC_ERRORS = {
    "semantic_provider_http_400",
    "semantic_provider_http_401_403",
}
_TERMINAL_EVIDENCE_ERRORS = {
    "provider_http_400",
    "provider_http_401_403",
}
_SAFE_CANDIDATE_FIELDS = (
    "candidate_identity",
    "provider",
    "title",
    "source_timestamp",
    "screening_score",
    "screening_reasons",
)


def extract_usage_metadata(body: Any) -> dict[str, int] | None:
    """Return only complete non-negative integer Gemini token usage metadata."""

    if not isinstance(body, Mapping):
        return None
    usage = body.get("usageMetadata")
    if not isinstance(usage, Mapping):
        return None

    source_keys = {
        "prompt_token_count": "promptTokenCount",
        "candidate_token_count": "candidatesTokenCount",
        "total_token_count": "totalTokenCount",
    }
    normalized: dict[str, int] = {}
    for target, source in source_keys.items():
        value = usage.get(source)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        normalized[target] = value
    return normalized


class _RecordingHttpPost:
    """Observe request attempts and safe token usage without changing semantics."""

    def __init__(self, delegate: Callable[..., Any]) -> None:
        self._delegate = delegate
        self.attempt_count = 0
        self.usage: dict[str, int] | None = None

    def __call__(self, url: str, **kwargs: Any) -> Any:
        self.attempt_count += 1
        response = self._delegate(url, **kwargs)
        try:
            body = response.json()
        except Exception:
            self.usage = None
        else:
            self.usage = extract_usage_metadata(body)
        return response


def _safe_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {field: candidate.get(field) for field in _SAFE_CANDIDATE_FIELDS}


def _provider_health_history(
    *,
    github_token: str | None,
    provided: Sequence[Mapping[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Read V1 provider-health history without granting V2 any write authority."""

    if provided is not None:
        return [dict(row) for row in provided if isinstance(row, Mapping)]
    if not github_token:
        return []
    adapter = SimpleNamespace(
        GH_PAT=github_token,
        AIIF_RUNTIME_STATE_BRANCH="runtime-state",
        requests=requests,
    )
    history, _ = _load_provider_health_history(adapter)
    return history


def build_live_proof(
    *,
    now: datetime,
    run_id: str,
    api_key: str,
    config: FourSourceLiveConfig | None = None,
    http_get: Callable[..., Any] = requests.get,
    http_post: Callable[..., Any] = requests.post,
    github_token: str | None = None,
    v1_reference: str | None = None,
    provider_health_history: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run one bounded V2 four-source live proof with V1-parity model routing."""

    history = _provider_health_history(
        github_token=github_token,
        provided=provider_health_history,
    )
    semantic_pool = _health_ranked_screening_pool(SEMANTIC_MODEL_POOL, history, now=now)
    evidence_pool = _health_ranked_pool(EVIDENCE_MODEL_POOL, history, now=now)
    if not semantic_pool:
        semantic_pool = list(SEMANTIC_MODEL_POOL)
    if not evidence_pool:
        evidence_pool = list(EVIDENCE_MODEL_POOL)

    semantic_recording_post = _RecordingHttpPost(http_post)
    evidence_recording_post = _RecordingHttpPost(http_post)
    evaluated_candidate: dict[str, Any] | None = None
    provider_result: dict[str, Any] | None = None
    provider_error_category: str | None = None
    evidence_contract_reason: str | None = None
    semantic_provider_error_category: str | None = None
    semantic_selected_model: str | None = None
    selected_evidence_model: str | None = None
    semantic_attempts: list[dict[str, str]] = []
    evidence_attempts: list[dict[str, str]] = []

    def recording_semantic_screen(
        candidates: list[Mapping[str, Any]],
    ) -> Mapping[str, Mapping[str, Any]]:
        nonlocal semantic_provider_error_category, semantic_selected_model
        last_error: Exception | None = None
        for model in semantic_pool:
            provider = GeminiSemanticScreeningProvider(
                api_key=api_key,
                model=model,
                http_post=semantic_recording_post,
            )
            try:
                result = provider(candidates)
            except SemanticScreeningError as exc:
                semantic_provider_error_category = exc.safe_code
                semantic_attempts.append({"model": model, "result": exc.safe_code})
                last_error = exc
                if exc.safe_code in _TERMINAL_SEMANTIC_ERRORS:
                    break
                continue
            except Exception as exc:
                semantic_provider_error_category = type(exc).__name__
                semantic_attempts.append({"model": model, "result": "semantic_provider_request_failed"})
                last_error = exc
                break
            semantic_selected_model = model
            semantic_provider_error_category = None
            semantic_attempts.append({"model": model, "result": "success"})
            return result
        if last_error is not None:
            raise last_error
        raise SemanticScreeningError("semantic_provider_request_failed")

    def recording_deep_dive(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal evaluated_candidate, provider_result, provider_error_category
        nonlocal evidence_contract_reason, selected_evidence_model
        evaluated_candidate = _safe_candidate(candidate)
        last_error: Exception | None = None
        for model in evidence_pool:
            provider = GeminiEvidenceProvider(
                api_key=api_key,
                model=model,
                http_post=evidence_recording_post,
            )
            try:
                raw_result = provider(candidate)
            except GeminiEvidenceError as exc:
                provider_error_category = exc.safe_code
                evidence_contract_reason = exc.evidence_contract_reason
                evidence_attempts.append({"model": model, "result": exc.safe_code})
                last_error = exc
                if exc.safe_code in _TERMINAL_EVIDENCE_ERRORS:
                    break
                continue
            except Exception as exc:
                provider_error_category = type(exc).__name__
                evidence_attempts.append({"model": model, "result": "provider_request_failed"})
                last_error = exc
                break
            provider_result = dict(raw_result)
            selected_evidence_model = model
            provider_error_category = None
            evidence_contract_reason = None
            evidence_attempts.append({"model": model, "result": "success"})
            return provider_result
        if last_error is not None:
            raise last_error
        raise GeminiEvidenceError("provider_request_failed")

    report = run_four_source_live(
        semantic_screen=recording_semantic_screen,
        deep_dive=recording_deep_dive,
        now=now,
        run_id=run_id,
        config=config,
        http_get=http_get,
        github_token=github_token,
        v1_reference=v1_reference,
    )
    return {
        **report,
        "observation": {
            "mode": PROVIDER_BACKED_MODE,
            "semantic_model_pool": list(semantic_pool),
            "semantic_model": semantic_selected_model or semantic_pool[0],
            "semantic_selected_model": semantic_selected_model,
            "semantic_request_budget": len(semantic_pool),
            "semantic_provider_error_category": semantic_provider_error_category,
            "evidence_model_pool": list(evidence_pool),
            "model": selected_evidence_model or evidence_pool[0],
            "selected_evidence_model": selected_evidence_model,
            "request_budget": len(evidence_pool),
            "total_model_request_budget": len(semantic_pool) + len(evidence_pool),
            "provider_result": provider_result,
            "provider_error_category": provider_error_category,
            "evidence_contract_reason": evidence_contract_reason,
            "production_authority": "v1",
            "diagnostic_only": True,
        },
        "v2_005_measurement": {
            "proof_version": PROOF_VERSION,
            "evaluated_candidate": evaluated_candidate,
            "semantic_attempts": semantic_attempts,
            "semantic_provider_usage": semantic_recording_post.usage,
            "semantic_provider_request_count": semantic_recording_post.attempt_count,
            "evidence_attempts": evidence_attempts,
            "provider_usage": evidence_recording_post.usage,
            "provider_request_count": evidence_recording_post.attempt_count,
            "total_model_request_count": (
                semantic_recording_post.attempt_count + evidence_recording_post.attempt_count
            ),
            "production_mutation_authorized": False,
            "promotion_decision": PROMOTION_DECISION,
        },
    }


def write_live_proof(report: Mapping[str, Any], output_path: str | Path) -> Path:
    """Write deterministic V2 JSON using the existing artifact contract."""

    return write_observation(report, output_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run measured V2 four-source live shadow proof")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", default=str(DEFAULT_DEEP_DIVE_OUTPUT_PATH))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_live_proof(
        now=datetime.now(timezone.utc),
        run_id=args.run_id,
        api_key=os.environ.get("GEMINI_API_KEY", ""),
        github_token=os.environ.get("GITHUB_TOKEN", "") or None,
    )
    write_live_proof(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
