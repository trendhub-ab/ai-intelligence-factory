from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import fresh_zero_model_preflight as preflight


def _source_rows(source, urls):
    return [
        {"nameWithOwner": "offline " + url, "source": source, "url": url}
        for url in urls
    ]


def _offline_pipeline():
    calls = []
    groups = {
        "GitHub": _source_rows("GitHub", ["https://example.invalid/gh/1", "https://example.invalid/gh/2"]),
        "HackerNews": _source_rows("HackerNews", ["https://example.invalid/hn/1"]),
        "ArXiv": _source_rows("ArXiv", ["https://example.invalid/ar/1"]),
        "OfficialVendor": _source_rows("OfficialVendor", ["https://example.invalid/vendor/1"]),
    }

    def fetch(source):
        def inner(n):
            calls.append("fetch:" + source)
            return [dict(row) for row in groups[source][:n]]
        return inner

    def forbidden(*_args, **_kwargs):
        raise AssertionError("model or persistence path was touched")

    p = SimpleNamespace(
        GH_PAT="fixture-only",
        NOTION_API_KEY="fixture-only",
        NOTION_DATA_SOURCE_ID="fixture-only",
        GEMINI_API_KEY=None,
        GITHUB_FETCH_LIMIT=50,
        HN_FETCH_LIMIT=50,
        ARXIV_FETCH_LIMIT=50,
        OFFICIAL_VENDOR_FETCH_LIMIT=50,
        MAX_SCREENING_CANDIDATES=200,
        fetch_github_trending=fetch("GitHub"),
        fetch_hackernews_top=fetch("HackerNews"),
        fetch_arxiv_ai_ml=fetch("ArXiv"),
        fetch_producthunt_trending=fetch("OfficialVendor"),
        round_robin_candidates=lambda source_groups, limit: [
            *source_groups["GitHub"],
            *source_groups["HackerNews"],
            *source_groups["ArXiv"],
            *source_groups["ProductHunt"],
        ][:limit],
        legal_safety_gate=lambda row: (True, "synthetic fixture"),
        get_existing_repo_urls=lambda: {"https://example.invalid/gh/2"},
        candidate_identity_urls=lambda row: {row["url"]},
        _normalize_title_for_match=lambda title: title.lower(),
        initialize_runtime=forbidden,
        screen_candidates_in_batches=forbidden,
        calibrate_candidates=forbidden,
        generate_intelligence_report=forbidden,
        persist_results=forbidden,
    )
    return p, calls


def _allow(monkeypatch):
    monkeypatch.setenv("FRESH_SOURCE_PREFLIGHT_CONFIRM", preflight.CONFIRM_VALUE)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", raising=False)
    monkeypatch.delenv("FRESH_SUPPLY_TRIAL_PROTOCOL", raising=False)
    monkeypatch.delenv("FRESH_SUPPLY_TRIAL_APPROVAL", raising=False)


def test_live_preflight_uses_only_whitelisted_source_dedupe_functions(tmp_path, monkeypatch):
    _allow(monkeypatch)
    p, calls = _offline_pipeline()
    target = tmp_path / "preflight.json"
    report = preflight.run_live(p, audit_path=target)
    assert calls == ["fetch:GitHub", "fetch:HackerNews", "fetch:ArXiv", "fetch:OfficialVendor"]
    assert report["model_provider_calls"] == 0
    assert report["note_or_notion_article_writes"] == 0
    assert report["quality_measured"] is False
    assert report["gate_result"] == "NOT_MEASURED"
    assert report["source_attrition"]["fresh_by_source"] == {
        "ArXiv": 1, "GitHub": 1, "HackerNews": 1, "OfficialVendor": 1,
    }
    assert report["source_attrition"]["existing_notion_duplicate_by_source"]["GitHub"] == 1
    assert all(status == "FRESH_PRE_SCREEN_ONLY" for status in report["source_status"].values())
    assert json.loads(target.read_text(encoding="utf-8")) == report
    assert "https://example.invalid" not in target.read_text(encoding="utf-8")
    assert "fixture-only" not in target.read_text(encoding="utf-8")


@pytest.mark.parametrize("missing", ("confirmation", "github", "notion", "gemini", "source"))
def test_live_preflight_refuses_unsafe_configuration_before_source_access(tmp_path, monkeypatch, missing):
    _allow(monkeypatch)
    p, calls = _offline_pipeline()
    if missing == "confirmation":
        monkeypatch.delenv("FRESH_SOURCE_PREFLIGHT_CONFIRM")
    elif missing == "github":
        p.GH_PAT = None
    elif missing == "notion":
        p.NOTION_API_KEY = None
    elif missing == "gemini":
        monkeypatch.setenv("GEMINI_API_KEY", "must never reach provider")
    elif missing == "source":
        monkeypatch.setenv("AIIF_LOCAL_SKILLS_CANARY_SOURCE", "GitHub")
    with pytest.raises(RuntimeError):
        preflight.run_live(p, audit_path=tmp_path / "never-created.json")
    assert calls == []
    assert not (tmp_path / "never-created.json").exists()


def test_preflight_zero_fresh_is_unmeasured_not_a_gate_fail(tmp_path, monkeypatch):
    _allow(monkeypatch)
    p, _ = _offline_pipeline()
    p.get_existing_repo_urls = lambda: {
        "https://example.invalid/gh/1", "https://example.invalid/gh/2",
    }
    result = preflight.run_live(p, audit_path=tmp_path / "diag.json")
    assert result["source_status"]["GitHub"] == "NO_FRESH_CANDIDATES"
    assert result["gate_result"] == "NOT_MEASURED"
    assert result["source_attrition"]["fresh_by_source"]["GitHub"] == 0


def test_preflight_dedup_unavailable_fails_closed_before_audit(tmp_path, monkeypatch):
    _allow(monkeypatch)
    p, _ = _offline_pipeline()
    p.get_existing_repo_urls = lambda: None
    with pytest.raises(RuntimeError, match="cannot verify Notion dedupe state"):
        preflight.run_live(p, audit_path=tmp_path / "diag.json")
    assert not (tmp_path / "diag.json").exists()


def test_preflight_rejects_missing_source_counter():
    keys = ("collected_by_source", "round_robin_by_source", "legal_safe_by_source",
            "dedupe_excluded_by_source", "existing_notion_duplicate_by_source",
            "intra_run_duplicate_by_source", "observed_excluded_by_source", "fresh_by_source")
    stages = {k: dict.fromkeys(preflight.STRATIFIED_SOURCES, 0) for k in keys}
    stages["fresh_by_source"].pop("GitHub")
    with pytest.raises(RuntimeError, match="four required"):
        preflight._summarize({"source_attrition": stages}, provenance="SYNTHETIC")


def test_workflow_is_manual_only_without_provider_credentials_or_note_sync():
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "fresh-zero-model-preflight.yml").read_text(encoding="utf-8")
    standalone = (root / "fresh_zero_model_preflight.py").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "\\n  schedule:" not in workflow
    assert "\\n  push:" not in workflow
    assert "GEMINI_API_KEY: ''" in workflow
    assert "gh workflow run" not in workflow
    assert "run: python fresh_zero_model_preflight.py" in workflow
    assert "install_runtime_layers(pipeline)" in standalone
    assert "install_run268(pipeline)" in standalone
    assert "install_run269(pipeline)" in standalone
    assert "pipeline.initialize_runtime()" not in standalone


def test_trial_is_explicit_and_never_escapes_baseline_source_guard(tmp_path, monkeypatch):
    import fresh_candidate_supply_experiment as supply

    _allow(monkeypatch)
    p, calls = _offline_pipeline()
    p.normalize_item = lambda **kwargs: kwargs
    p.requests = SimpleNamespace(post=lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("unapproved trial made source request")
    ))
    monkeypatch.setenv("FRESH_SUPPLY_TRIAL_PROTOCOL", supply.PROTOCOL_ID)
    with pytest.raises(RuntimeError, match="exact preregistered approval"):
        preflight.run_live(p, audit_path=tmp_path / "no.json")
    assert calls == []

    monkeypatch.setenv("FRESH_SUPPLY_TRIAL_PROTOCOL", "unregistered")
    monkeypatch.setenv("FRESH_SUPPLY_TRIAL_APPROVAL", "ALLOW_3_GITHUB_READS")
    with pytest.raises(RuntimeError, match="exact preregistered approval"):
        preflight.run_live(p, audit_path=tmp_path / "no.json")
    assert calls == []

    monkeypatch.delenv("FRESH_SUPPLY_TRIAL_PROTOCOL")
    with pytest.raises(RuntimeError, match="cannot leak into baseline"):
        preflight.run_live(p, audit_path=tmp_path / "no.json")
    assert calls == []


def test_approved_trial_provenance_is_not_production_evidence(tmp_path, monkeypatch):
    import fresh_candidate_supply_experiment as supply

    _allow(monkeypatch)
    p, calls = _offline_pipeline()
    p.normalize_item = lambda **kwargs: kwargs
    p.requests = SimpleNamespace()
    monkeypatch.setenv("FRESH_SUPPLY_TRIAL_PROTOCOL", supply.PROTOCOL_ID)
    monkeypatch.setenv("FRESH_SUPPLY_TRIAL_APPROVAL", "ALLOW_3_GITHUB_READS")

    def fake_fetcher(_pipeline, *, capture):
        capture.update({"protocol": supply.PROTOCOL_ID, "github_graphql_queries": 3})
        return lambda limit: _source_rows("GitHub", ["https://example.invalid/trial/1"])[:limit]

    monkeypatch.setattr(supply, "make_fetcher", fake_fetcher)
    result = preflight.run_live(p, audit_path=tmp_path / "trial.json")
    assert result["provenance"] == "EXPERIMENTAL_GITHUB_SOURCE_SUPPLY_NOT_PRODUCTION"
    assert result["experimental_github"]["github_graphql_queries"] == 3
    assert result["quality_measured"] is False
    assert result["gate_result"] == "NOT_MEASURED"
    assert "fetch:GitHub" not in calls
