"""One durable, non-renewable authorization for Defense Factory calibration."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import datetime, timezone

from x_discovery.bounded_calibration_validation import (
    BoundedCalibrationError, build_calibration_item, run_calibration_boundary,
)

OPERATION = "defense-factory-calibration-20260911"
REPOSITORY = "trendhub-ab/ai-intelligence-factory"
MODEL = "gemini-3.5-flash-lite"
CLAIM_PATH = f".runtime/operations/{OPERATION}.json"


def claim_operation(pipeline, evidence, put=None):
    """Create-only GitHub write: no SHA, retry, release, or stale-lock expiry.

    An ambiguous HTTP outcome consumes the authorization conservatively. GitHub
    rejects a second creation at the same path, including concurrent processes.
    """
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
        raise BoundedCalibrationError("operation not claimed; stop without model request")


def run_once(p, candidate, screening, claim=None):
    evidence = run_calibration_boundary(p, candidate, screening)
    if os.environ.get("AIIF_X_CALIBRATION_OPERATION") != OPERATION:
        raise BoundedCalibrationError("fixed operation authorization is required")
    if os.environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise BoundedCalibrationError("workflow reruns are prohibited")
    if (evidence["canonical_url"] != "https://openai.com/the-defense-factory"
            or evidence["x_post_id"] != "2097786616311840853" or evidence["raw_score"] != 88):
        raise BoundedCalibrationError("only saved Defense Factory Raw 88 is authorized")
    counter = p.PERSISTENT_GEMINI_COUNTER
    if not (counter.enabled and counter.branch == "runtime-state"
            and counter.repo == REPOSITORY and counter.counter_scope and p.GH_PAT):
        raise BoundedCalibrationError("durable runtime-state quota counter is required")
    if (p.GEMINI_BUDGET.daily_budget != 1 or p.GEMINI_BUDGET.request_count != 0
            or p.GEMINI_BUDGET.screening_retry_budget != 0
            or p.SCREENING_MODEL_POOL != [MODEL] or p.client is None):
        raise BoundedCalibrationError("one unused request and one model with no retries required")
    item = build_calibration_item(candidate, screening)
    prompt = p._calibration_prompt([item])
    if hashlib.sha256(prompt.encode()).hexdigest() != evidence["calibration_prompt_sha256"]:
        raise BoundedCalibrationError("calibration prompt changed before claim")
    evidence["input_sha256"] = hashlib.sha256(json.dumps(
        [candidate, screening], sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if evidence["input_sha256"] != "9ddf2cf6080de9c5a1b52f97f56f056a5ea9bfd1d7adc8fb05cf6ddb53a24acd":
        raise BoundedCalibrationError("saved inputs changed; stop before claim")
    # Validate SDK config before the irreversible claim. attempts=1 includes the
    # initial HTTP attempt. AFC is disabled to prohibit additional model turns.
    from google.genai import types
    config = types.GenerateContentConfig(
        response_mime_type="application/json", max_output_tokens=1000,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1)),
    )
    (claim or claim_operation)(p, evidence)
    # Never call a model pool: production pool helpers retry/fallback on errors.
    response = p._generate_via_chat(
        MODEL, prompt, config=config, request_kind="global_calibration",
        request_context=OPERATION, count_as_deep_dive=False, request_origin="new",
    )
    parsed, missing, diagnostic = p._parse_batch_screening_response(
        getattr(response, "text", ""), {"X0001"}, include_diagnostic=True)
    row = parsed.get("X0001")
    if (missing or diagnostic or not row or type(row.get("score")) is not int
            or not 0 <= row["score"] <= 100 or row.get("commercial_score") is None
            or row.get("shelf_life_score") is None or not row.get("topic_valid")
            or p.GEMINI_BUDGET.request_count != 1):
        raise BoundedCalibrationError("invalid Calibration response; no Final, no retry")
    from x_discovery.post_calibration_dry_run import _select_with_real_stock_guard
    threshold = int(p.NOTION_SAVE_THRESHOLD_SCORE)
    selected = _select_with_real_stock_guard(
        final_score=row["score"], stock_threshold=threshold, persisted=False)
    if selected:
        raise BoundedCalibrationError("unpersisted item reached Deep Dive selector")
    usage = getattr(response, "usage_metadata", None)
    return dict(evidence, operation=OPERATION, status="CALIBRATION_COMPLETED",
                calibration_executed=True, model_calls=1, model=MODEL,
                final_score=row["score"], calibration_result=row,
                stock_threshold=threshold, stock_score_eligible=row["score"] >= threshold,
                unpersisted_deep_dive_guard_verified=True,
                usage_metadata=usage.model_dump(mode="json") if usage else None)
