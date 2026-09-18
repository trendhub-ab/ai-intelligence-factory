"""Zero-API reproductions of cross-module defects found in the repository audit."""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import SimpleNamespace

import pytest

import article_revalidation
import content_db_contract_guard as schema
import cross_db_contract_guard as cross_schema
import evidence_authority
import note_manuscript
import note_ready_sync
import pending_retry_validation
import production_pipeline
import publication_contract
import run367_x_daily_discovery as xdaily

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("mode", ["ful", "pending_retry", "unexpected"])
def test_unknown_explicit_mode_cannot_select_production(mode, monkeypatch):
    monkeypatch.setenv("AIIF_ONE_SHOT_MODE", mode)
    with pytest.raises(RuntimeError, match="mode"):
        production_pipeline._workflow_dispatch_mode()


@pytest.mark.parametrize("body", ["{", '{"inputs": []}', '{"inputs": {"mode": "ful"}}'])
def test_broken_dispatch_event_cannot_fall_back_to_production(body, tmp_path, monkeypatch):
    event = tmp_path / "event.json"
    event.write_text(body)
    monkeypatch.delenv("AIIF_ONE_SHOT_MODE", raising=False)
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event))
    with pytest.raises(RuntimeError):
        production_pipeline._workflow_dispatch_mode()


def test_pending_mode_enters_existing_bounded_lane_before_production_setup(monkeypatch):
    # The external setup boundaries are replaced; the real dispatcher must choose the
    # bounded lane rather than the nonexistent pending_only article-validation API.
    import pipeline
    import run179_eyecatch_font_refinement
    import run203_runtime_state_channel

    monkeypatch.setenv("AIIF_ONE_SHOT_MODE", "pending_retry_validation")
    monkeypatch.setattr(production_pipeline, "install_runtime_layers", lambda p: p)
    monkeypatch.setattr(run179_eyecatch_font_refinement, "ensure_google_font_assets", lambda **kw: None)
    monkeypatch.setattr(run203_runtime_state_channel, "preflight_runtime_state_channel", lambda: None)
    for module_name in (
        "source_normalization", "run231_performance_telemetry", "run268_business_source_strategy",
        "run269_business_source_precision", "run283_numeric_evidence_equivalence",
        "run284_reader_recovery_precision", "run287_publication_date_provenance",
        "run346_backlog_budget_reserve", "run367_x_daily_discovery", "reader_quality_precision",
    ):
        module = __import__(module_name)
        monkeypatch.setattr(module, "install", lambda *args: None)
    monkeypatch.setattr(production_pipeline, "install_run349_score_narrative_negation_precision", lambda p: p)
    selected = []
    monkeypatch.setattr(pending_retry_validation, "main", lambda: selected.append("bounded_pending_lane"))
    monkeypatch.setattr(pipeline, "main", lambda: selected.append("full_production"))
    try:
        production_pipeline.main()
    except TypeError as exc:
        selected.append(str(exc))
    assert selected == ["bounded_pending_lane"]


@pytest.mark.parametrize("report", ["legacy manuscript", {"note_draft": "truthy draft"}, ("draft", "mystery")])
def test_article_validation_never_accepts_an_unverified_truthy_return(report, monkeypatch):
    p = SimpleNamespace(
        logger=logging.getLogger(__name__),
        DEEP_DIVE_MODEL_BUDGET=SimpleNamespace(budget=12),
        legal_safety_gate=lambda repo: (True, "N/A"),
        generate_intelligence_report=lambda *args, **kw: report,
        DailyQuotaExhaustedError=type("DailyQuotaExhaustedError", (Exception,), {}),
    )
    monkeypatch.setattr(article_revalidation, "select_revalidation_items", lambda *args, **kwargs: [{
        "repo": {"nameWithOwner": "existing candidate"}, "notion_page_id": "existing-page",
    }])
    result = article_revalidation.run_article_revalidation(p, limit=1)
    assert result["accepted"] == 0
    assert result.get("unverified") == 1


def _ready_page(source):
    return {"id": "12345678-1234-1234-1234-1234567890ab", "properties": {
        "記事状態": {"select": {"name": "Ready"}},
        "note記事タイトル": {"rich_text": [{"plain_text": "一次情報を検証した記事"}]},
        "情報源": {"select": {"name": source}},
        "元情報URL": {"url": "https://openai.com/index/release"},
    }}


def test_x_primary_candidate_has_consistent_public_and_note_ready_source_contract():
    p = SimpleNamespace(normalize_item=__import__("source_normalization").normalize_item)
    candidates = xdaily.queue_to_factory_candidates(p, {
        "queue_type": "x_primary_source_resolution", "evidence_status": "discovery_only",
        "factory_write": False, "items": [{
            "canonical_url": "https://openai.com/index/release", "is_evidence": False,
            "source_role": "discovery_signal", "x_post_urls": ["https://x.com/OpenAI/status/1"],
        }],
    })
    candidate = candidates[0]
    assert candidate["sourceContext"] == ""
    assert candidate["sourceDetails"]["is_evidence"] is False
    state = note_ready_sync._source_state(_ready_page(candidate["source"]))
    assert state is not None, "a verified X-origin Ready must not be excluded as unsupported_source"
    manuscript = note_manuscript.build_clean_note_manuscript(
        "一次情報を検証した本文です。", candidate["nameWithOwner"], candidate["primaryUrl"], "",
        source=candidate["source"], split_free_paid=lambda draft, name: (draft, ""),
        display_heading_aliases=lambda key: [], subscription_enabled=False,
        subscription_landing_url="", subscription_campaign_id="",
    )
    assert "X投稿自体は根拠に使用しません" in manuscript
    assert "https://x.com/OpenAI/status/1" not in manuscript
    # Admission of X as discovery never admits a raw/stale manuscript.
    assert not publication_contract.is_current_ready_block(manuscript, "AIIF_MANUSCRIPT:READY")
    assert note_ready_sync._source_state(_ready_page("ProductHunt")) is None


def _current_schema():
    props = {name: {"type": "select", "select": {"options": [{"name": x} for x in values]}}
             for name, values in schema.ENUM_CONTRACTS.items()}
    props[schema.p.PROP_SOURCE] = {"type": "select", "select": {"options": [
        {"name": x} for x in ("GitHub", "HackerNews", "ArXiv", "OfficialVendor", "X")
    ]}}
    return props


def test_schema_guard_accepts_current_sources_without_requiring_retired_product_hunt():
    schema.validate_enum_contracts(_current_schema())


@pytest.mark.parametrize("missing", ["OfficialVendor", "X"])
def test_schema_guard_rejects_missing_current_source(missing):
    props = _current_schema()
    props[schema.p.PROP_SOURCE]["select"]["options"] = [
        x for x in props[schema.p.PROP_SOURCE]["select"]["options"] if x["name"] != missing
    ]
    with pytest.raises(ValueError, match=missing):
        schema.validate_enum_contracts(props)


def test_member_schema_accepts_current_sources_without_retired_product_hunt():
    prop = {"type": "multi_select", "multi_select": {"options": [
        {"name": x} for x in ("GitHub", "HackerNews", "ArXiv", "OfficialVendor", "X", "Unknown")
    ]}}
    cross_schema.validate_enum_contracts({"source": prop}, {"source": cross_schema.SOURCE_OPTIONS}, "member")


@pytest.mark.parametrize("missing", ["OfficialVendor", "X"])
def test_member_schema_requires_each_current_source(missing):
    prop = {"type": "multi_select", "multi_select": {"options": [
        {"name": x} for x in ("GitHub", "HackerNews", "ArXiv", "OfficialVendor", "X", "ProductHunt", "Unknown")
        if x != missing
    ]}}
    with pytest.raises(ValueError, match=missing):
        cross_schema.validate_enum_contracts({"source": prop}, {"source": cross_schema.SOURCE_OPTIONS}, "member")


def test_rescue_survives_real_production_initialization_and_ready_accounting(tmp_path, monkeypatch):
    import pipeline as p
    import run346_backlog_budget_reserve as partition
    import run374_ready_rescue as rescue

    monkeypatch.chdir(tmp_path)
    events = []
    results = {}
    for flag in ("PUBLIC_DB_SYNC_MODE", "SYNTHETIC_REGRESSION_MODE", "INVENTORY_BOOTSTRAP_ACTIVE", "REGEN_TEST_MODE"):
        monkeypatch.setattr(p, flag, False)
    for flag in ("_run346_backlog_budget_reserve_installed", "_run374_ready_rescue_installed",
                 "_run374_ready_rescue_preflight_installed", "_run374_vague_rescue_installed"):
        monkeypatch.setattr(p, flag, False, raising=False)
    for name in ("_run346_original_deep_dive_budget", "_run374_ready_rescue_reserved_requests",
                 "_run374_ready_rescue_slot_consumed", "_run374_ready_rescue_preflight_generated",
                 "_run374_ready_rescue_preflight", "_READY_RESCUE_ACTIVE", "_READY_RESCUE_PROVIDER_SENDS"):
        monkeypatch.setattr(p, name, None, raising=False)

    class Budget:
        budget = 12
        used = 0

        def summary(self):
            return "offline budget"

    monkeypatch.setattr(p, "DEEP_DIVE_MODEL_BUDGET", Budget())
    monkeypatch.setattr(p, "TOP_N_FOR_DEEP_DIVE", 3)
    monkeypatch.setattr(p, "GEMINI_PENDING_RETRY_REQUEST_BUDGET", 2)
    monkeypatch.setattr(p, "DEFERRED_DEEP_DIVE_MAX_PER_RUN", 1)
    monkeypatch.delenv("GEMINI_BACKLOG_RESERVED_REQUESTS", raising=False)
    monkeypatch.delenv("GEMINI_READY_RESCUE_RESERVED_REQUESTS", raising=False)
    monkeypatch.setattr(p, "DEEP_DIVE_GATE_FUNNEL", p.DeepDiveGateFunnel())
    artifact = tmp_path / "rescue-audit.json"

    def reset_audit():
        events.append("reset_audit")
        artifact.unlink(missing_ok=True)

    monkeypatch.setattr(p, "reset_article_audit_for_production_run", reset_audit)
    monkeypatch.setattr(p, "reset_article_style_memory", lambda: events.append("reset_style"))
    monkeypatch.setattr(p, "initialize_runtime", lambda: events.append("initialize"))
    monkeypatch.setattr(p, "load_source_roi_state", lambda: {})
    monkeypatch.setattr(p, "compute_source_roi_profile", lambda state: {})
    monkeypatch.setattr(p, "allocate_source_fetch_limits", lambda *args: {})
    monkeypatch.setattr(p, "log_source_roi_profile", lambda *args: None)
    monkeypatch.setattr(p, "get_pending_retry_items", lambda **kw: [])
    monkeypatch.setattr(p, "check_stale_content", lambda: None)
    for fetch in ("fetch_github_trending", "fetch_hackernews_top", "fetch_arxiv_ai_ml", "fetch_producthunt_trending"):
        monkeypatch.setattr(p, fetch, lambda *args: [])
    monkeypatch.setattr(p, "get_existing_repo_urls", lambda: set())
    monkeypatch.setattr(p, "repair_existing_multilingual_notion_titles", lambda: 0)
    monkeypatch.setattr(p, "run_product_reviews", lambda: None)
    monkeypatch.setattr(p, "update_source_roi_state", lambda *args: {})
    monkeypatch.setattr(p, "run_product_delivery_maintenance", lambda: None)
    monkeypatch.setattr(p, "finalize_deep_dive_observability", lambda funnel: results.update(
        ready=funnel.counters["ready_count"], artifact=artifact.exists()))
    monkeypatch.setattr(p, "_apply_deterministic_publication_rescue", lambda parsed, reasons: (parsed, []))

    def backlog(items, generated, rank):
        results.update(delivered=generated, rank=rank, target=p.TOP_N_FOR_DEEP_DIVE)
        return generated, rank

    monkeypatch.setattr(p, "process_article_backlog", backlog)
    monkeypatch.setattr(p, "main", p.main)

    def recover(current, generated, rank, limit=1):
        events.append("rescue")
        current.DEEP_DIVE_MODEL_BUDGET.used += 1
        current.DEEP_DIVE_GATE_FUNNEL.incr("ready_count")
        artifact.write_text("offline successful rescue audit")
        return generated + 1, rank + 1

    monkeypatch.setattr(article_revalidation, "run_existing_editorial_recovery", recover)
    partition.install(p)
    p.main()
    assert events[:4] == ["reset_audit", "reset_style", "initialize", "rescue"]
    assert results == {"delivered": 1, "rank": 1, "target": 3, "ready": 1, "artifact": True}
    assert p.DEEP_DIVE_MODEL_BUDGET.used == 1
    assert p.DEEP_DIVE_MODEL_BUDGET.budget == 12


@pytest.mark.parametrize("resolved", [
    "https://x.com/OpenAI/status/1", "https://mobile.twitter.com/OpenAI/status/1", "https://t.co/unresolved",
    "https://x.com./OpenAI/status/1", "https://mobile.twitter.com./OpenAI/status/1", "https://t.co./unresolved",
])
def test_resolved_x_pages_never_become_evidence_or_generation_context(resolved, monkeypatch):
    import pipeline as p

    raw_post = "RAW_X_POST_UNSUPPORTED_CLAIM method architecture implementation beta limitation. " * 10

    class Response:
        status_code = 200
        headers = {"Content-Type": "text/plain"}
        url = resolved

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def iter_content(self, **kwargs):
            yield raw_post.encode()

    monkeypatch.setattr(p.requests, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(p, "_validate_public_http_url", lambda url: None)
    info = p.prepare_source_context({
        "source": "X", "nameWithOwner": "X-discovered official release",
        "url": "https://openai.com/index/release", "primaryUrl": "https://openai.com/index/release",
        "sourceContext": "", "sourceContextVerified": False,
    })
    assert info["primary_source_resolved"] is False
    assert "RAW_X_POST_UNSUPPORTED_CLAIM" not in info["context"]
    assert "RAW_X_POST_UNSUPPORTED_CLAIM" not in info["verification_context"]
    assert info["evidence_authority_summary"]["decision_eligible_documents"] == 0
    assert p.fetch_webpage_context("https://openai.com/index/release") == ""


@pytest.mark.parametrize("url", [
    "https://x.com/OpenAI/status/1", "https://twitter.com/OpenAI/status/1", "https://t.co/unresolved",
    "https://x.com./OpenAI/status/1", "https://twitter.com./OpenAI/status/1", "https://t.co./unresolved",
])
def test_raw_x_evidence_is_discovery_even_with_a_primary_role(url):
    classification = evidence_authority.classify_evidence(
        url=url, role="PRIMARY_SOURCE", pipeline_source="X", primary_url=url,
        raw_source_type="official_docs", origin="metadata",
    )
    assert classification["authority_class"] == "DISCOVERY"
    assert classification["decision_eligible"] is False


def test_malformed_fetch_url_remains_an_empty_result():
    import pipeline as p

    assert p._http_get_limited("https://[broken", ("text/plain",), 100) == (b"", "", "")


def _run_fanout(tmp_path, body):
    script = (ROOT / ".github/workflows/daily-one-shot.yml").read_text().split(
        "      - name: Explicit post-run fan-out with GH_PAT\n", 1)[1].split("        run: |\n", 1)[1]
    script = textwrap.dedent(script)
    audit = tmp_path / "article_audit"
    audit.mkdir()
    if body is not None:
        (audit / "ready_rescue_validation.json").write_text(body)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # No network: the actual workflow shell runs against a local gh executable.
    gh = bin_dir / "gh"
    gh.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$GH_CALL_LOG"\n')
    gh.chmod(0o755)
    env = dict(os.environ, VALIDATION_MODE="ready_rescue_validation", GH_TOKEN="test-only",
               GH_CALL_LOG=str(tmp_path / "calls"), GITHUB_STEP_SUMMARY=str(tmp_path / "summary"))
    env["PATH"] = str(bin_dir) + os.pathsep + os.path.dirname(sys.executable) + os.pathsep + env["PATH"]
    result = subprocess.run(["bash", "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True)
    calls = (tmp_path / "calls").read_text() if (tmp_path / "calls").exists() else ""
    return result, calls


@pytest.mark.parametrize("body", [None, "{", '{}', '{"ready": true}', '{"ready": -1}', '{"ready": "1"}'])
def test_rescue_fanout_rejects_invalid_audit_instead_of_reporting_noop_success(body, tmp_path):
    result, calls = _run_fanout(tmp_path, body)
    assert result.returncode != 0
    assert calls == ""


@pytest.mark.parametrize("ready", [0, 1])
def test_rescue_fanout_distinguishes_valid_zero_from_ready_success(ready, tmp_path):
    result, calls = _run_fanout(tmp_path, json.dumps({"ready": ready}))
    assert result.returncode == 0, result.stderr
    assert calls == ("workflow run note-ready-sync.yml --ref main -f create_private_draft=true\n" if ready else "")
