from __future__ import annotations

import json

import pytest

import fresh_protocol_quota_lock as lock


def test_current_four_source_fresh_protocol_matches_frozen_blobs_and_budget():
    report = lock.validate(source="GitHub")
    assert report["protocol"] == "fresh-four-source-fallback-bounded-v2"
    assert report["source"] == "GitHub"
    assert report["file_fingerprints_verified"] >= 18
    assert report["max_logical_calls_per_exact_source"] == {
        "screening": 2, "calibration": 1, "deep_dive": 1,
    }
    assert report["actual_provider_rpm_rpd_remaining"] == "NOT_MEASURED"
    assert report["safe_to_start_without_quota_review"] is False
    assert report["quality_measured"] is False


@pytest.mark.parametrize("source", ["ArXiv", "GitHub", "HackerNews", "OfficialVendor", ""])
def test_only_registered_source_targets_validate(source):
    report = lock.validate(source=source)
    assert report["source"] == (source or "unspecified_legacy_canary")


@pytest.mark.parametrize("source", ["github", "ProductHunt", "OfficialVendor ", "../GitHub"])
def test_unregistered_or_malformed_source_fails_before_protocol_use(source):
    with pytest.raises(RuntimeError, match="Invalid or unexpected"):
        lock.validate(source=source)


def test_file_fingerprint_drift_fails_closed(tmp_path):
    manifest = json.loads(lock.LOCK.read_text(encoding="utf-8"))
    manifest["file_blobs"]["local_skills/writer.py"] = "0" * 40
    changed = tmp_path / "lock.json"
    changed.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="local_skills/writer.py"):
        lock.validate(manifest_path=changed, source="GitHub")


def test_logical_budget_drift_fails_closed(tmp_path):
    manifest = json.loads(lock.LOCK.read_text(encoding="utf-8"))
    manifest["max_logical_calls_per_exact_source"]["deep_dive"] = 2
    changed = tmp_path / "lock.json"
    changed.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="logical call budget"):
        lock.validate(manifest_path=changed, source="ArXiv")


def test_workflow_settings_are_read_only_from_exact_production_entrypoint():
    workflow = (lock.ROOT / ".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    expected = {
        "GITHUB_FETCH_LIMIT": 50,
        "HN_FETCH_LIMIT": 50,
        "ARXIV_FETCH_LIMIT": 50,
        "OFFICIAL_VENDOR_FETCH_LIMIT": 50,
        "MAX_SCREENING_CANDIDATES": 200,
        "SCREENING_BATCH_SIZE": 25,
        "GLOBAL_CALIBRATION_BATCH_SIZE": 50,
        "GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET": 12,
    }
    assert {key: lock._workflow_value(workflow, key) for key in expected} == expected


def test_locked_protocol_does_not_claim_actual_provider_quota():
    report = lock.validate(source="OfficialVendor")
    assert report["actual_transport_attempts"] == "SEND_INVOCATIONS_BOUNDED_SDK_SINGLE_ATTEMPT_RUNTIME_REQUIRED"
    assert report["actual_provider_rpm_rpd_remaining"] == "NOT_MEASURED"
    assert report["safe_to_start_without_quota_review"] is False


def test_source_supply_experiment_is_not_part_of_unmodified_fresh_lock():
    manifest = json.loads(lock.LOCK.read_text(encoding="utf-8"))
    assert "fresh_candidate_supply_experiment.py" not in manifest["file_blobs"]
    assert manifest["base_main"] == "6bde024ecf05d8ebdbe189d6299312dc96eb7aca"



def test_bounded_fallback_is_registered_not_one_transport_call():
    report = lock.validate(source="GitHub")
    assert report["max_logical_calls_per_exact_source"]["deep_dive"] == 1
    assert report["max_provider_send_slots"] == {"total": 10, "pre_article": 6, "article": 4}
    assert report["article_model_fallback"] == "PRESERVED_WITHIN_BOUND"
    manifest = json.loads(lock.LOCK.read_text(encoding="utf-8"))
    assert manifest["max_article_candidates_after_send"] == 1
    assert manifest["max_quality_retries"] == 0
    assert manifest["file_blobs"]["gemini_provider_resilience.py"]
    assert manifest["file_blobs"]["fresh_model_fallback_budget.py"]


def test_malformed_hard_budget_manifest_is_rejected(tmp_path):
    manifest = json.loads(lock.LOCK.read_text(encoding="utf-8"))
    manifest["max_provider_send_slots"]["article"] = 99
    changed = tmp_path / "unsafe.json"
    changed.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RuntimeError, match="registered model-send cap drift"):
        lock.validate(manifest_path=changed, source="ArXiv")
