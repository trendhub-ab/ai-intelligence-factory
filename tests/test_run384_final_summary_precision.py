from __future__ import annotations

import types

import run249_final_publication_surface_gate as r249


def test_fragment_is_replaced_only_by_existing_complete_sentence():
    summary = {
        "what": "Agent Memoryの仕組みを整理しながら、",
        "why": "既存システムとの違いを確認できます。",
        "decision": "まず限定環境で試すのが妥当です。",
    }
    parsed = {
        "source_summary_text": "Agent Memoryをファイル形式として扱う考え方が示されました。",
    }
    repaired = r249.repair_reader_summary_from_existing_facts(summary, parsed)
    assert repaired["what"] == "Agent Memoryをファイル形式として扱う考え方が示されました。"


def test_fragment_without_existing_complete_candidate_stays_blocked():
    summary = {
        "what": "Agent Memoryの仕組みを整理しながら、",
        "why": "重要性を検討しつつ、",
        "decision": "判断条件を確認しながら、",
    }
    repaired = r249.repair_reader_summary_from_existing_facts(summary, {})
    assert repaired == summary
    joined = "\n".join(r249._summary_fragment_issues(repaired))
    assert "final_surface_summary_fragment:何が出た？" in joined
    assert "final_surface_summary_fragment:なぜ重要？" in joined
    assert "final_surface_summary_fragment:結論は？" in joined


def test_jargon_dense_row_prefers_plainer_existing_complete_candidate():
    summary = {
        "what": "MCP Native Runtime Adapter Pipeline Orchestratorを統合するコンポーネントです。",
        "why": "複数の技術要素をまとめて扱えます。",
        "decision": "まず限定環境で試すのが妥当です。",
    }
    parsed = {
        "source_summary_text": "複数の処理をまとめて扱うための仕組みが公開されました。",
    }
    assert r249._summary_row_is_jargon_dense(summary["what"])
    repaired = r249.repair_reader_summary_from_existing_facts(summary, parsed)
    assert repaired["what"] == "複数の処理をまとめて扱うための仕組みが公開されました。"
    assert not r249._summary_row_is_jargon_dense(repaired["what"])


def test_jargon_dense_row_without_safer_existing_sentence_remains_reviewable():
    dense = "MCP Native Runtime Adapter Pipeline Orchestratorを統合するコンポーネントです。"
    summary = {"what": dense, "why": dense, "decision": "限定環境で試します。"}
    repaired = r249.repair_reader_summary_from_existing_facts(summary, {})
    assert repaired["what"] == dense
    assert repaired["why"] == dense
    issues = r249._summary_reader_value_issues(repaired)
    assert any("final_surface_summary_jargon_cluster" in issue for issue in issues)


def test_decision_fragment_can_use_existing_decision_code_fallback_without_new_fact():
    summary = {
        "what": "新しい仕組みが公開されました。",
        "why": "既存方式との差を検証できます。",
        "decision": "導入条件を確認しながら、",
    }
    parsed = {"decision_text": "TRY"}
    repaired = r249.repair_reader_summary_from_existing_facts(summary, parsed)
    assert repaired["decision"] == "まずは限定した環境で小さく試し、条件を確かめる価値があります。"


def test_install_repairs_real_summary_before_final_surface_gate_and_persistence():
    raw_summary = {
        "what": "Agent Memoryの仕組みを整理しながら、",
        "why": "MCP Native Runtime Adapter Pipeline Orchestratorを統合するコンポーネントです。",
        "decision": "導入条件を確認しながら、",
    }

    def build_summary(parsed):
        return dict(raw_summary)

    def build_manuscript(article, repo_name, repo_url, spdx_id, source, **kwargs):
        summary = kwargs.get("reader_summary") or {}
        return r249._projection_from_parts(kwargs.get("title_text", ""), summary, article)

    p = types.SimpleNamespace(
        validate_human_appeal_gate=lambda parsed, peer_articles=None: ("ACCEPTABLE", []),
        build_clean_note_manuscript=build_manuscript,
        build_reader_first_summary=build_summary,
        logger=types.SimpleNamespace(warning=lambda *args, **kwargs: None),
    )
    r249.install(p)
    parsed = {
        "title_text": "Agent Memoryをどう見るか。",
        "note_draft": "本文です。",
        "source_summary_text": "Agent Memoryをファイル形式として扱う考え方が示されました。",
        "why_important_text": "複数の処理をまとめて扱えるか検証できます。",
        "decision_text": "TRY",
    }
    repaired = p.build_reader_first_summary(parsed)
    assert repaired["what"].endswith("。")
    assert repaired["why"].endswith("。")
    assert repaired["decision"].endswith("。")
    state, issues = p.validate_human_appeal_gate(parsed, [])
    assert state == "ACCEPTABLE"
    assert not any("final_surface_summary_fragment" in issue for issue in issues)
    manuscript = p.build_clean_note_manuscript(
        "本文です。", "repo", "", "", "Unknown",
        title_text="Agent Memoryをどう見るか。",
        reader_summary=repaired,
    )
    assert "Agent Memoryをファイル形式として扱う考え方が示されました。" in manuscript
