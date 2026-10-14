"""AIIF Rebuild V2-005 measured live shadow proof.

This module wraps the existing V2-004 provider-backed shadow observation with
safe measurement only. It does not grant Production authority and does not
write Notion, note, Ready state, queues, delivery ledgers, or publication state.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from v2_live_shadow_acquisition import LiveAcquisitionConfig
from v2_shadow_observation import (
    DEFAULT_DEEP_DIVE_OUTPUT_PATH,
    DEFAULT_MODEL,
    GeminiEvidenceProvider,
    build_provider_backed_observation,
    write_observation,
)


PROOF_VERSION = "V2-005"
PROMOTION_DECISION = "human_review_required"
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


def build_live_proof(
    *,
    now: datetime,
    run_id: str,
    api_key: str,
    config: LiveAcquisitionConfig | None = None,
    http_get: Callable[..., Any] = requests.get,
    http_post: Callable[..., Any] = requests.post,
    v1_reference: str | None = None,
) -> dict[str, Any]:
    """Run one bounded V2-005 live proof with safe measurement only."""

    recording_post = _RecordingHttpPost(http_post)
    provider = GeminiEvidenceProvider(
        api_key=api_key,
        model=DEFAULT_MODEL,
        http_post=recording_post,
    )
    evaluated_candidate: dict[str, Any] | None = None

    def recording_deep_dive(candidate: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal evaluated_candidate
        evaluated_candidate = _safe_candidate(candidate)
        return provider(candidate)

    report = build_provider_backed_observation(
        now=now,
        run_id=run_id,
        config=config,
        http_get=http_get,
        deep_dive=recording_deep_dive,
        model=DEFAULT_MODEL,
        v1_reference=v1_reference,
    )
    return {
        **report,
        "v2_005_measurement": {
            "proof_version": PROOF_VERSION,
            "evaluated_candidate": evaluated_candidate,
            "provider_usage": recording_post.usage,
            "provider_request_count": recording_post.attempt_count,
            "production_mutation_authorized": False,
            "promotion_decision": PROMOTION_DECISION,
        },
    }


def write_live_proof(report: Mapping[str, Any], output_path: str | Path) -> Path:
    """Write deterministic V2-005 JSON using the existing V2 artifact contract."""

    return write_observation(report, output_path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run measured V2-005 live shadow proof")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", default=str(DEFAULT_DEEP_DIVE_OUTPUT_PATH))
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_live_proof(
        now=datetime.now(timezone.utc),
        run_id=args.run_id,
        api_key=os.environ.get("GEMINI_API_KEY", ""),
    )
    write_live_proof(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
