from __future__ import annotations

import json

import pytest

import fresh_protocol_quota_lock as lock


def test_current_four_source_fresh_protocol_matches_frozen_blobs_and_budget():
    report = lock.validate(source="GitHub")
    assert report["protocol"] == "fresh-unmodified-four-source-v439-v1"
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
    assert report["actual_transport_attempts"] == "NOT_BOUNDED_BY_THIS_OFFLINE_CHECK"
    assert report["actual_provider_rpm_rpd_remaining"] == "NOT_MEASURED"
    assert report["safe_to_start_without_quota_review"] is False


def test_source_supply_experiment_is_not_part_of_unmodified_fresh_lock():
    manifest = json.loads(lock.LOCK.read_text(encoding="utf-8"))
    assert "fresh_candidate_supply_experiment.py" not in manifest["file_blobs"]
    assert manifest["base_main"] == "f149bda8c176dd0a9997d89396b0acee0f0d1611"
