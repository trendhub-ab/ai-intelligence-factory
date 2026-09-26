from __future__ import annotations

import json
import types
from pathlib import Path

import production_e2e_validation as e2e


class _Budget:
    def __init__(self, budget=12, used=0):
        self.budget = budget
        self.used = used


class _Logger:
    def info(self, *args, **kwargs):
        pass
    def warning(self, *args, **kwargs):
        pass


def _pipeline(evidence_state="SUFFICIENT"):
    p = types.SimpleNamespace()
    p.EVIDENCE_SUFFICIENT = "SUFFICIENT"
    p.EVIDENCE_SUPPLEMENT_REQUIRED = "SUPPLEMENT_REQUIRED"
    p.DEEP_DIVE_MODEL_BUDGET = _Budget()
    p.MAX_QUALITY_RETRIES = 1
    p.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE = True
    p.logger = _Logger()
    p.initialize_runtime = lambda: None
    p.legal_safety_gate = lambda repo: (True, "N/A")
    p.prepare_source_context = lambda repo: {
        "context": "official method implementation",
        "verification_context": "official method implementation",
        "deep_source_scanned": False,
        "evidence_documents": [{"url": "https://example.com"}],
        "primary_source_resolved": True,
    }
    p.resolve_followup_freshness = lambda info: {"triggered": False, "followup_found": False, "context": ""}
    p._truncate_source_context = lambda value: value
    p._merge_verification_context = lambda a, b: a + b
    p._build_evidence_metadata = lambda context, deep: {"coverage": {"method": "FOUND"}}
    p.supplement_source_evidence = lambda info: info
    p.assess_evidence_sufficiency = lambda info: {
        "state": evidence_state,
        "checks": {
            "primary_source_resolved": True,
            "technical_claims_available": True,
            "limitations_or_constraints_available": True,
            "conditions_for_numbers_available": True,
            "action_support_available": True,
            "freshness_status_available_if_time_sensitive": True,
        },
        "core_missing": [],
        "optional_missing": [],
        "blocking_missing": [],
        "documents_checked": 1,
        "decision_scope_safe": evidence_state == "SUFFICIENT",
        "action_risk_tier": "LOW",
        "action_supported_at_current_tier": True,
        "numeric_claims_allowed": True,
        "freshness_scope_limited": False,
    }
    return p


def test_eligible_evidence_requires_low_risk_and_primary_support():
    p = _pipeline()
    good = p.assess_evidence_sufficiency({})
    assert e2e._eligible_evidence(p, good) is True
    bad = dict(good)
    bad["action_risk_tier"] = "MEDIUM"
    assert e2e._eligible_evidence(p, bad) is False
    bad = dict(good)
    bad["checks"] = dict(good["checks"], primary_source_resolved=False)
    assert e2e._eligible_evidence(p, bad) is False


def test_select_candidate_uses_zero_provider_preflight_and_highest_screening(monkeypatch):
    p = _pipeline()
    items = [
        {"notion_page_id": "11111111-1111-1111-1111-111111111111", "screening_score": 70, "repo": {"nameWithOwner": "A", "source": "OfficialVendor"}},
        {"notion_page_id": "22222222-2222-2222-2222-222222222222", "screening_score": 90, "repo": {"nameWithOwner": "B", "source": "OfficialVendor"}},
    ]
    monkeypatch.setattr(e2e, "select_revalidation_items", lambda *args, **kwargs: items)
    monkeypatch.setattr(e2e, "rehydrate_recovery_repo", lambda pipeline, item: dict(item["repo"]))
    selected, diagnostics = e2e.select_candidate(p, limit=8)
    assert selected["repo"]["nameWithOwner"] == "B"
    assert selected["item"]["screening_score"] == 90
    assert len(diagnostics) == 2
    assert p.DEEP_DIVE_MODEL_BUDGET.used == 0


def test_select_candidate_prefers_complete_evidence_over_slightly_higher_screening(monkeypatch):
    p = _pipeline()
    items = [
        {"notion_page_id": "11111111-1111-1111-1111-111111111111", "screening_score": 80, "repo": {"nameWithOwner": "Higher score / incomplete", "source": "OfficialVendor"}},
        {"notion_page_id": "22222222-2222-2222-2222-222222222222", "screening_score": 78, "repo": {"nameWithOwner": "Lower score / complete", "source": "OfficialVendor"}},
    ]
    monkeypatch.setattr(e2e, "select_revalidation_items", lambda *args, **kwargs: items)
    monkeypatch.setattr(e2e, "rehydrate_recovery_repo", lambda pipeline, item: dict(item["repo"]))

    calls = {"n": 0}
    def assess(_info):
        calls["n"] += 1
        complete = calls["n"] == 2
        return {
            "state": "SUFFICIENT",
            "checks": {
                "primary_source_resolved": True,
                "technical_claims_available": True,
                "limitations_or_constraints_available": complete,
                "conditions_for_numbers_available": True,
                "actor_attribution_available": complete,
                "action_support_available": True,
                "comparison_support_available_if_comparison_is_needed": True,
                "freshness_status_available_if_time_sensitive": True,
            },
            "core_missing": [],
            "optional_missing": [] if complete else ["limitations_or_constraints_available"],
            "blocking_missing": [],
            "documents_checked": 3 if complete else 2,
            "decision_scope_safe": True,
            "action_risk_tier": "LOW",
            "action_supported_at_current_tier": True,
            "numeric_claims_allowed": True,
            "freshness_scope_limited": False,
        }
    p.assess_evidence_sufficiency = assess

    selected, diagnostics = e2e.select_candidate(p, limit=8)
    assert selected["repo"]["nameWithOwner"] == "Lower score / complete"
    assert selected["item"]["screening_score"] == 78
    assert len(diagnostics) == 2


def test_run_persists_exactly_one_selected_article_and_emits_sync_id(monkeypatch, tmp_path):
    p = _pipeline()
    page_id = "12345678-1234-1234-1234-1234567890ab"
    item = {
        "notion_page_id": page_id,
        "screening_score": 88,
        "screening_reason": "test",
        "repo": {"nameWithOwner": "Vendor / release", "source": "OfficialVendor"},
    }
    selected = {
        "item": item,
        "repo": dict(item["repo"]),
        "evidence": {"state": "SUFFICIENT"},
    }
    monkeypatch.setattr(e2e, "select_candidate", lambda pipeline: (selected, [{"eligible": True}]))
    e2e.AUDIT_PATH = tmp_path / "audit.json"
    calls = []
    def generate(repo, **kwargs):
        calls.append((repo, kwargs))
        p.DEEP_DIVE_MODEL_BUDGET.used += 2
        return "ready manuscript"
    p.generate_intelligence_report = generate

    result = e2e.run(p)
    assert result["ready"] == 1
    assert result["sync_id"] == "123456781234123412341234567890ab"
    assert result["provider_requests"] == 2
    assert len(calls) == 1
    assert calls[0][1]["persist_results"] is True
    assert calls[0][1]["candidate_origin"] == "production_e2e_validation"
    assert calls[0][1]["notion_page_id"] == page_id
    saved = json.loads(e2e.AUDIT_PATH.read_text(encoding="utf-8"))
    assert saved["ready"] == 1
    assert saved["candidate"] == "Vendor / release"



def test_prepare_only_pins_candidate_and_spends_zero_provider_budget(monkeypatch, tmp_path):
    p = _pipeline()
    page_id = "abcdefab-cdef-abcd-efab-cdefabcdefab"
    item = {
        "notion_page_id": page_id,
        "screening_score": 86,
        "screening_reason": "preflight",
        "repo": {"nameWithOwner": "Vendor / preflight", "source": "OfficialVendor"},
    }
    selected = {
        "item": item,
        "repo": dict(item["repo"]),
        "evidence": {"state": "SUFFICIENT"},
    }
    monkeypatch.setattr(e2e, "select_candidate", lambda pipeline: (selected, [{"eligible": True}]))
    monkeypatch.setenv("PRODUCTION_E2E_PREPARE_ONLY", "true")
    e2e.AUDIT_PATH = tmp_path / "audit.json"
    p.generate_intelligence_report = lambda *args, **kwargs: (_ for _ in ()).throw(
        AssertionError("prepare-only must stop before provider generation")
    )

    result = e2e.run(p)
    assert result["prepare_only"] is True
    assert result["ready"] == 0
    assert result["provider_requests"] == 0
    assert result["sync_id"] == "abcdefabcdefabcdefabcdefabcdefab"
    saved = json.loads(e2e.AUDIT_PATH.read_text(encoding="utf-8"))
    assert saved["prepare_only"] is True
    assert saved["candidate"] == "Vendor / preflight"


def test_run_with_no_preflight_candidate_spends_no_provider_budget(monkeypatch, tmp_path):
    p = _pipeline()
    monkeypatch.setattr(e2e, "select_candidate", lambda pipeline: (None, [{"eligible": False}]))
    e2e.AUDIT_PATH = tmp_path / "audit.json"
    p.generate_intelligence_report = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not call provider path"))
    result = e2e.run(p)
    assert result["ready"] == 0
    assert result["provider_requests"] == 0
    assert result["sync_id"] == ""


def test_one_shot_workflow_exposes_production_e2e_and_exact_note_target():
    root = Path(__file__).resolve().parents[1]
    source = (root / ".github/workflows/daily-one-shot.yml").read_text(encoding="utf-8")
    assert "- production_e2e_validation" in source
    assert 'VALIDATION_MODE:-}" = "production_e2e_validation"' in source
    assert 'article_audit/production_e2e_validation.json' in source
    assert '-f target_sync_id="$sync_id"' in source
    assert "e2e_prepare_only:" in source
    assert "PRODUCTION_E2E_PREPARE_ONLY: ${{ inputs.e2e_prepare_only }}" in source


def test_note_ready_sync_accepts_and_preflights_exact_target_sync_id():
    root = Path(__file__).resolve().parents[1]
    source = (root / ".github/workflows/note-ready-sync.yml").read_text(encoding="utf-8")
    assert "target_sync_id:" in source
    assert "TARGET_SYNC_ID: ${{ inputs.target_sync_id }}" in source
    assert 'preflight.preflight(os.environ.get("TARGET_SYNC_ID", ""))' in source


def test_local_skills_production_validation_uses_frozen_stack_and_persists_without_retry(monkeypatch, tmp_path):
    p = _pipeline()
    page_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    item = {
        "notion_page_id": page_id,
        "screening_score": 91,
        "screening_reason": "local-skills-production",
        "repo": {"nameWithOwner": "Vendor / local skills production", "source": "OfficialVendor"},
    }
    selected = {
        "item": item,
        "repo": dict(item["repo"]),
        "evidence": {"state": "SUFFICIENT"},
    }
    monkeypatch.setattr(e2e, "select_candidate", lambda pipeline: (selected, [{"eligible": True}]))
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_PRODUCTION_VALIDATION", "true")
    e2e.LOCAL_SKILLS_AUDIT_PATH = tmp_path / "local-skills-production.json"

    observed = {}
    def generate(repo, **kwargs):
        observed["retries"] = p.MAX_QUALITY_RETRIES
        observed["rescue"] = p.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE
        observed["kwargs"] = kwargs
        p._LOCAL_SKILLS_PRODUCTION_LAST_COMPILE = {
            "writer_blob_sha": "204cce30ab838e0d6dac9cbe762d0a82ff02f1aa",
            "canonicalizer_blob_sha": "414089a14c238f104b2866507ddf8521c2baf420",
            "evidence_boundary_version": "stage8-v4",
        }
        return "ready local skills manuscript"

    p.generate_intelligence_report = generate
    result = e2e.run(p)

    assert result["mode"] == "local_skills_production_validation"
    assert result["local_skills"] is True
    assert result["ready"] == 1
    assert observed["retries"] == 0
    assert observed["rescue"] is False
    assert observed["kwargs"]["persist_results"] is True
    assert observed["kwargs"]["candidate_origin"] == "local_skills_production_validation"
    assert p.MAX_QUALITY_RETRIES == 1
    assert p.ENABLE_DETERMINISTIC_PUBLICATION_RESCUE is True
    assert result["local_skills_compile"]["writer_blob_sha"] == "204cce30ab838e0d6dac9cbe762d0a82ff02f1aa"
    saved = json.loads(e2e.LOCAL_SKILLS_AUDIT_PATH.read_text(encoding="utf-8"))
    assert saved["ready"] == 1


def test_local_skills_production_validation_fails_closed_without_compile_proof(monkeypatch, tmp_path):
    p = _pipeline()
    item = {
        "notion_page_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "screening_score": 91,
        "screening_reason": "local-skills-production",
        "repo": {"nameWithOwner": "Vendor / missing compile", "source": "OfficialVendor"},
    }
    monkeypatch.setattr(e2e, "select_candidate", lambda pipeline: ({
        "item": item,
        "repo": dict(item["repo"]),
        "evidence": {"state": "SUFFICIENT"},
    }, [{"eligible": True}]))
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_PRODUCTION_VALIDATION", "true")
    e2e.LOCAL_SKILLS_AUDIT_PATH = tmp_path / "local-skills-production.json"
    p.generate_intelligence_report = lambda *args, **kwargs: "unexpected ready"

    import pytest
    with pytest.raises(RuntimeError, match="without frozen compiler metadata"):
        e2e.run(p)


def test_local_skills_precompiler_source_failure_returns_not_ready_without_contract_error(monkeypatch, tmp_path):
    p = _pipeline()
    item = {
        "notion_page_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "screening_score": 75,
        "screening_reason": "source unavailable before generation",
        "repo": {"nameWithOwner": "OpenAI Model Misalignment Report", "source": "HackerNews"},
    }
    monkeypatch.setattr(e2e, "select_candidate", lambda pipeline: ({
        "item": item,
        "repo": dict(item["repo"]),
        "evidence": {"state": "SUFFICIENT"},
    }, [{"eligible": True}]))
    monkeypatch.setenv("AIIF_LOCAL_SKILLS_PRODUCTION_VALIDATION", "true")
    e2e.LOCAL_SKILLS_AUDIT_PATH = tmp_path / "local-skills-production.json"
    p.generate_intelligence_report = lambda *args, **kwargs: None

    result = e2e.run(p)

    assert result["ready"] == 0
    assert result["sync_id"] == ""
    assert result["local_skills_compile"] == {}
    assert result["error"] == ""
