"""AIIF Rebuild V2-003 manual zero-model shadow observation.

This runner observes V2 live acquisition and deterministic screening without
allowing a Deep Dive or granting V2 any Production authority. Its only intended
side effect is writing one explicitly requested JSON observation artifact.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping

import requests

from v2_live_shadow_acquisition import LiveAcquisitionConfig, run_bounded_live_shadow


OBSERVATION_MODE = "manual_zero_model"
DEFAULT_OUTPUT_PATH = Path("article_audit/v2_shadow_observation.json")


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
    parser = argparse.ArgumentParser(description="Run bounded V2 zero-model shadow observation")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report = build_manual_observation(
        now=datetime.now(timezone.utc),
        run_id=args.run_id,
    )
    write_observation(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
