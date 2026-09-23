"""Cross-gate counterexamples: real production gates, only external I/O replaced."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
URL = "https://github.com/example/router"
CONTEXT = "Author: Lab A. Method: routing algorithm. Documentation describes message routing."
LOW_ACTION = "公式資料を確認する。"
MEDIUM_ACTION = "限定ユーザーへ導入する。"


@pytest.fixture
def production(monkeypatch, tmp_path):
    # Enter the actual dispatcher to install precisely the live order and current overlays.
    # Runtime installers also patch shared rendering modules. Restore their namespace
    # so integration probes cannot contaminate historical isolated-layer unit tests.
    namespaces = [
        (module, dict(vars(module))) for module in list(sys.modules.values())
        if module is not None and getattr(module, "__file__", None)
        and Path(module.__file__).resolve().parent == ROOT
    ]
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("SYNTHETIC_REGRESSION_MODE", "true")
    monkeypatch.delenv("AIIF_ONE_SHOT_MODE", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    spec = importlib.util.spec_from_file_location("gate_reachability_pipeline", ROOT / "pipeline.py")
    p = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p)
    monkeypatch.setitem(sys.modules, "pipeline", p)
    import production_pipeline
    main = p.main
    p.main = lambda: None
    production_pipeline.main()
    p.main = main
    monkeypatch.setattr(p, "REGEN_TEST_OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(p, "generate_note_editorial_eyecatch", lambda *a, **kw: None)
    monkeypatch.setattr(p, "save_regen_test_manuscript", lambda *a, **kw: None)
    yield p
    for module, namespace in namespaces:
        vars(module).clear()
        vars(module).update(namespace)


def source_info(p):
    return {
        "primary_source_resolved": True, "primary_url": URL,
        "context": CONTEXT, "verification_context": CONTEXT,
        "method": p.GROUNDING_SOURCE_NATIVE, "source": "GitHub",
        "source_details": {}, "supplement_candidates": [],
        "evidence_documents": [{"url": URL, "retrieved": True}],
        "evidence_urls": [URL], "deep_source_scanned": False,
        "evidence_metadata": p._build_evidence_metadata(CONTEXT, False),
    }


def response(action=LOW_ACTION, *, numeric_defect=False, summary_defect=False):
    summary = "応答時間は42msです。" if summary_defect else "メッセージの配送先を振り分ける手法の公式資料。"
    draft = (
        "## 配送先を決める仕組み。\n"
        "メッセージの配送先を振り分ける手法が公開された。待ち時間を減らせるかが気になる。\n\n"
        "## 使う前に確認したいこと。\n"
        "公開資料だけでは運用時の制約までは確認できない。私なら" + action
        + "判断に必要な条件を確認する。"
    )
    if numeric_defect:
        draft += "\n\n応答時間は42msです。"
    return "\n".join([
        "・Decision: TRY", "・Decision Score: 合計: 72 / 100",
        "・Decision Reason: 一次情報を確認し、利用条件を調べる価値がある。",
        "・Action: " + action, "・Source Summary: " + summary,
        "===NOTE_DRAFT_START===", "メッセージの配送先をどう決めるか。", "", draft,
        "===NOTE_DRAFT_END===",
    ])


def run_responses(p, monkeypatch, responses, *, persist=False, origin="new"):
    info = source_info(p)
    monkeypatch.setattr(p, "prepare_source_context", lambda repo: deepcopy(info))
    monkeypatch.setattr(p, "resolve_followup_freshness", lambda info: {
        "triggered": False, "followup_found": False, "context": "",
    })
    queue = iter(responses)
    requests = []

    def model(prompt, repo, source, **kwargs):
        requests.append(kwargs["request_kind"])
        return SimpleNamespace(text=next(queue), candidates=[]), {
            "grounding_status": p.GROUNDING_SOURCE_NATIVE, "evidence_urls": [URL],
        }

    monkeypatch.setattr(p, "call_gemini_grounded_deep_dive", model)
    repo = {"nameWithOwner": "example/router", "url": URL, "primaryUrl": URL,
            "source": "GitHub", "licenseInfo": {"spdxId": "MIT"},
            "description": "Method: routing algorithm."}
    result = p.generate_intelligence_report(
        repo, persist_results=persist, notion_page_id="existing-page" if persist else None,
        candidate_origin=origin,
    )
    return result, requests


def test_all_real_gates_have_a_safe_jointly_satisfiable_path(production, monkeypatch):
    result, requests = run_responses(production, monkeypatch, [response()])
    assert result[1] == "accepted"
    assert LOW_ACTION in result[0]
    assert requests == ["deep_dive"]


def test_retry_to_low_risk_clears_previous_action_restriction(production, monkeypatch):
    result, requests = run_responses(production, monkeypatch, [response(MEDIUM_ACTION), response()])
    assert result[1] == "accepted"
    assert MEDIUM_ACTION not in result[0]
    assert requests == ["deep_dive", "quality_retry"]


def test_numeric_rescue_cannot_erase_independent_action_failure(production, monkeypatch):
    result, _ = run_responses(production, monkeypatch, [response(MEDIUM_ACTION, numeric_defect=True)] * 3)
    assert result[1] == "rejected"


def test_summary_assembly_cannot_introduce_ungrounded_number_after_fact_pass(production, monkeypatch):
    result, _ = run_responses(production, monkeypatch, [response(summary_defect=True)] * 3)
    assert result[1] == "rejected"


@pytest.mark.parametrize("summary,status", [
    ("この手法は投資対効果を改善する。", "rejected"),
    ("この手法の投資対効果を評価する。", "accepted"),
])
def test_outer_precision_filter_uses_same_summary_surface(production, monkeypatch, summary, status):
    raw = response().replace("メッセージの配送先を振り分ける手法の公式資料。", summary)
    raw = raw.replace("===NOTE_DRAFT_END===", "投資対効果を評価する。\n===NOTE_DRAFT_END===")
    result, _ = run_responses(production, monkeypatch, [raw] * 3)
    assert result[1] == status


def test_rescue_helper_enforces_evidence_action_scope(production):
    p = production
    info = source_info(p)
    info["requested_action_risk_tier"] = "MEDIUM"
    info["evidence_result"] = p.assess_evidence_sufficiency(info)
    info["sufficient"] = True
    info["decision_scope_safe"] = True
    assert info["evidence_result"]["action_risk_downgraded_from"] == "MEDIUM"
    parsed = p._parse_gemini_response(response(MEDIUM_ACTION))
    ready, diagnostics = p._publication_rescue_can_be_ready(
        parsed, CONTEXT, "GitHub", info["evidence_metadata"], info, {},
    )
    assert not ready
    assert any("MEDIUM_RISK_ACTION_UNSUPPORTED" in f for f in diagnostics["fact_failures"])


@pytest.mark.parametrize("origin", ["new", "deferred", "pending_retry", "existing_editorial_recovery", "existing_stale_ready_recovery"])
@pytest.mark.parametrize("saved", [False, True])
def test_ready_requires_joint_gates_and_persistence(production, monkeypatch, origin, saved):
    p = production
    funnel = p.reset_deep_dive_gate_funnel()
    p.reset_article_style_memory()
    # Only external delivery/storage is substituted. Ready accounting is production code.
    monkeypatch.setattr(p, "upgrade_notion_page_with_report", lambda *a, **kw: saved)
    monkeypatch.setattr(p, "upload_eyecatch_to_github", lambda *a, **kw: "")
    monkeypatch.setattr(p, "send_telegram_alert", lambda *a, **kw: None)
    monkeypatch.setattr(p, "save_subscription_attribution_record", lambda *a, **kw: "")
    monkeypatch.setattr(p, "save_article_audit_package", lambda *a, **kw: None)
    result, requests = run_responses(p, monkeypatch, [response()], persist=True, origin=origin)
    assert requests == ["deep_dive"]
    assert bool(result) is saved
    assert funnel.records[-1]["final_status"] == ("Ready" if saved else p.CONTENT_STATUS_PERSISTENCE_FAILED)
    assert funnel.records[-1]["article_saved"] is saved


@pytest.mark.parametrize("has_second_candidate", [False, True])
def test_full_recovery_does_not_repeat_consumed_preflight_candidate(production, monkeypatch, has_second_candidate):
    import article_revalidation
    import run346_backlog_budget_reserve
    p = production
    monkeypatch.setattr(p, "NOTION_API_KEY", "test-key")
    monkeypatch.setattr(p, "TOP_N_FOR_DEEP_DIVE", 3)
    p.DEEP_DIVE_MODEL_BUDGET.budget = 12
    p.DEEP_DIVE_MODEL_BUDGET.used = 0
    monkeypatch.setattr(p, "_model_pool_has_session_candidate", lambda pool: True)
    item = {"repo": {"nameWithOwner": "example/router", "url": URL, "primaryUrl": URL,
                     "source": "GitHub", "licenseInfo": {"spdxId": "MIT"}},
            "notion_page_id": "same-page", "screening_score": 72}
    rows = [item]
    if has_second_candidate:
        rows.append({**item, "notion_page_id": "second-page"})
    monkeypatch.setattr(p, "get_regen_test_items", lambda *a: rows)
    monkeypatch.setattr(article_revalidation, "_read_current_statuses", lambda *a: (
        p.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW, p.CONTENT_STATUS_DEEP_DIVE,
    ))
    attempts = []

    def rejected(repo, **kwargs):
        attempts.append(kwargs["notion_page_id"])
        p.DEEP_DIVE_MODEL_BUDGET.used += 1
        return None

    monkeypatch.setattr(p, "generate_intelligence_report", rejected)
    monkeypatch.setattr(p, "process_article_backlog", lambda rows, count, rank: (count, rank))
    article_revalidation.install_full_recovery(p)
    run346_backlog_budget_reserve.install(p)
    count, rank = p._run374_ready_rescue_preflight()
    p.process_article_backlog([], count, rank)
    assert attempts == (["same-page", "second-page"] if has_second_candidate else ["same-page"])
