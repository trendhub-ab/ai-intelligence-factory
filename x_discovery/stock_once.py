"""Persist the observed Defense Factory Final as one Stock record, once."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from x_discovery.bounded_calibration_validation import BoundedCalibrationError
from x_discovery.bounded_factory_validation import (
    _canonical_existing_urls,
    build_screening_repo,
    validate_saved_candidate,
)


OPERATION = "defense-factory-stock-20260911"
REPOSITORY = "trendhub-ab/ai-intelligence-factory"
CLAIM_PATH = f".runtime/operations/{OPERATION}.json"
CALIBRATION_OPERATION = "defense-factory-calibration-20260911"
EXPECTED_OBSERVATION_SHA256 = "96d63796c6c4c615cab140f8fb996d371538ce9f5f0cdf27b3b276040ce616e1"


class StockOnceError(RuntimeError):
    """Fail-closed violation in the single saved Stock operation."""


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise StockOnceError(f"could not read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise StockOnceError(f"{label} must be an object")
    if label == "calibration observation" and hashlib.sha256(raw).hexdigest() != EXPECTED_OBSERVATION_SHA256:
        raise StockOnceError("calibration observation changed")
    return value


def claim_operation(pipeline: Any, evidence: Mapping[str, Any], put=None) -> None:
    """Acquire the non-renewable Stock authorization with a create-only write."""
    if put is None:
        import requests
        put = requests.put
    record = dict(evidence, operation=OPERATION, status="claimed_no_reissue",
                  claimed_at=datetime.now(timezone.utc).isoformat(),
                  run_id=os.environ.get("GITHUB_RUN_ID", ""))
    response = put(
        f"https://api.github.com/repos/{REPOSITORY}/contents/{CLAIM_PATH}",
        headers={"Authorization": f"Bearer {pipeline.GH_PAT}",
                 "Accept": "application/vnd.github+json"},
        json={"branch": "runtime-state", "message": f"claim {OPERATION} once",
              "content": base64.b64encode(json.dumps(record, sort_keys=True).encode()).decode()},
        timeout=30, allow_redirects=False,
    )
    if response.status_code != 201:
        raise StockOnceError("Stock operation not claimed; stop without Notion write")


def validate_inputs(pipeline: Any, candidate: Mapping[str, Any], observation: Mapping[str, Any]) -> tuple[dict, dict]:
    try:
        saved = validate_saved_candidate(candidate)
    except Exception as exc:
        raise StockOnceError(str(exc)) from exc
    expected = {
        "schema_version": 1,
        "lane": "x_saved_candidate_calibration_validation",
        "operation": CALIBRATION_OPERATION,
        "status": "CALIBRATION_COMPLETED",
        "calibration_executed": True,
        "model_calls": 1,
        "canonical_url": saved["canonical_url"],
        "x_post_id": saved["x_post_id"],
        "raw_score": 88,
        "final_score": 88,
        "stock_threshold": 60,
        "stock_score_eligible": True,
        "stock_persisted": False,
        "deep_dive_selected": False,
        "factory_write": False,
        "generation_executed": False,
        "publication_executed": False,
    }
    for key, value in expected.items():
        if observation.get(key) != value:
            raise StockOnceError(f"unexpected observed Calibration field: {key}")
    row = observation.get("calibration_result")
    if not isinstance(row, Mapping) or row.get("score") != 88:
        raise StockOnceError("valid calibrated result is required")
    if int(pipeline.NOTION_SAVE_THRESHOLD_SCORE) != 60 or observation["final_score"] < pipeline.NOTION_SAVE_THRESHOLD_SCORE:
        raise StockOnceError("observed Final does not satisfy current Stock policy")
    repo = build_screening_repo(saved)
    # The Notion source property represents the primary evidence source. X remains
    # discovery-only provenance and is retained in sourceDetails / the observation.
    repo["source"] = "OfficialVendor"
    repo["sourceDetails"] = {"x_discovery_provenance": repo.pop("x_discovery_provenance")}
    return saved, repo


def run_once(pipeline: Any, candidate: Mapping[str, Any], observation: Mapping[str, Any], claim=None) -> dict[str, Any]:
    saved, repo = validate_inputs(pipeline, candidate, observation)
    if os.environ.get("AIIF_X_STOCK_OPERATION") != OPERATION:
        raise StockOnceError("fixed Stock operation authorization is required")
    if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise StockOnceError("workflow reruns are prohibited")
    if not (pipeline.NOTION_API_KEY and (pipeline.NOTION_DATA_SOURCE_ID or pipeline.NOTION_DATABASE_ID)):
        raise StockOnceError("Notion credentials and destination are required")
    counter = pipeline.PERSISTENT_GEMINI_COUNTER
    if not (pipeline.GH_PAT and counter.branch == "runtime-state" and counter.repo == REPOSITORY):
        raise StockOnceError("runtime-state operation guard is required")
    if getattr(pipeline.GEMINI_BUDGET, "request_count", 0) != 0:
        raise StockOnceError("Stock operation must start with zero model requests")

    original_alert = pipeline.send_telegram_alert
    pipeline.send_telegram_alert = lambda *_args, **_kwargs: None
    try:
        existing = _canonical_existing_urls(pipeline.get_existing_repo_urls())
    finally:
        pipeline.send_telegram_alert = original_alert
    if saved["canonical_url"] in existing:
        raise StockOnceError("candidate already exists; stop without duplicate write")

    evidence = {
        "schema_version": 1,
        "lane": "x_saved_candidate_stock_once",
        "canonical_url": saved["canonical_url"],
        "x_post_id": saved["x_post_id"],
        "raw_score": observation["raw_score"],
        "final_score": observation["final_score"],
        "existing_url_count": len(existing),
        "dedup_verified": True,
        "notion_write_ceiling": 1,
        "model_calls": 0,
    }
    (claim or claim_operation)(pipeline, evidence)
    reason = str(observation["calibration_result"].get("reason") or "").strip()
    page_id = pipeline.save_screening_metadata_to_notion(repo, observation["final_score"], reason)
    if not page_id:
        raise StockOnceError("Notion Stock write failed or was ambiguous; no retry")
    if getattr(pipeline.GEMINI_BUDGET, "request_count", 0) != 0:
        raise StockOnceError("unexpected model request during Stock operation")
    return dict(evidence, operation=OPERATION, status="STOCK_SAVED",
                notion_page_id=page_id, notion_writes=1, source="OfficialVendor",
                stock_persisted=True, deep_dive_selected=False,
                generation_executed=False, publication_executed=False,
                factory_write=True)


def run_from_paths(pipeline: Any, candidate_path: Path, observation_path: Path) -> dict[str, Any]:
    result = run_once(pipeline, _load(candidate_path, "candidate"),
                      _load(observation_path, "calibration observation"))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result
