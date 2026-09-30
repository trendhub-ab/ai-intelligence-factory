from __future__ import annotations

import re

from local_skills.compiler import compile_snapshot
from local_skills.production_canary import _completion_boundary
from editorial_naturalness import classify_article_claims


def _historical_snapshot() -> dict:
    return {
        "schema": "aiif_local_writer_snapshot_v1",
        "case_id": "openai-2015-topic-fit-regression",
        "canonical_entity_id": "url:https://openai.com/index/introducing-openai/",
        "name": "OpenAI 2015 founding announcement",
        "reader_title": "OpenAIの原点を読み直す",
        "source": "OfficialVendor",
        "source_summary": (
            "2015年、OpenAIが非営利のAI研究機関として設立され、"
            "当時の目的と原則を公式に発表した記録です。"
        ),
        "what": "設立時の公式発表に書かれた目的、組織方針、公開姿勢を確認します。",
        "why_important": "後年の公式発表と比較するときの基準点になるためです。",
        "decision": "WATCH",
        "decision_score": 65,
        "decision_reason": "現在の組織や方針を直接説明する資料ではなく、2015年時点の記録だからです。",
        "action": "2015年の発表内容を基準点として記録し、後年の公式発表と比較する。",
        "primary_risk": "2015年時点の説明を現在の事実として扱わないことです。",
        "best_for": "公式発表の変化を時系列で比較したい読者。",
        "avoid_for": "一つの過去資料だけで現在の方針を断定したい読者。",
        "evidence_urls": ["https://openai.com/index/introducing-openai/"],
    }


def test_historical_topic_stays_out_of_adoption_and_poc_framing():
    result = compile_snapshot(_historical_snapshot())
    article = result["parsed"]["note_draft"]
    action = result["canonicalized_snapshot"]["action"]

    assert action == "2015年の発表内容を基準点として記録し、後年の公式発表と比較する。"
    assert "限定的な検証として" not in action
    assert "基準点として追跡し、次の情報と比較する" in article
    assert "判断材料" in article
    for forbidden in (
        "どこまで試すか",
        "本格導入",
        "全面採用",
        "試すならここまで",
        "本番へ急がない理由",
        "小さな検証",
        "採用",
        "導入",
        "結局、何をするもの",
        "何のためのもの",
    ):
        assert forbidden not in article


def test_technical_adoption_topic_keeps_existing_limited_verification_path():
    snapshot = _historical_snapshot()
    snapshot.update({
        "case_id": "technical-adoption-control",
        "canonical_entity_id": "url:https://example.invalid/tool",
        "name": "New coding tool",
        "reader_title": "New coding tool",
        "source": "GitHub",
        "source_summary": "開発作業を補助する新しいツールが公開されました。",
        "what": "コード変更の確認を補助するツールです。",
        "why_important": "既存の開発フローで使えるかを判断する材料になります。",
        "decision_reason": "対象範囲が限定されており、本番利用には追加確認が必要です。",
        "action": "ログを注視する。",
        "primary_risk": "本番条件は未確認です。",
        "best_for": "小さく試せる開発チーム。",
        "avoid_for": "検証なしで本番導入したいチーム。",
        "evidence_urls": ["https://example.invalid/tool"],
    })
    result = compile_snapshot(snapshot)
    assert result["canonicalized_snapshot"]["action"].startswith("限定的な検証として、")


def test_management_completion_does_not_reinject_adoption_language_for_history():
    parsed = {
        "decision_text": "WATCH",
        "source_summary_text": "2015年に組織が設立され、当時の方針が公式発表された記録です。",
        "what_text": "設立時の公式発表を確認します。",
        "why_important_text": "後年との比較基準になります。",
        "decision_reason_text": "当時の記録なので現在事実への一般化はできません。",
        "action_text": "当時の発表を基準点として記録し、後年の公式発表と比較する。",
        "main_risk_text": "",
        "best_for_text": "",
        "avoid_for_text": "",
    }
    values, sources = _completion_boundary(parsed)
    joined = " ".join(values.values())

    assert sources == {
        "primary_risk": "deterministic_publication_boundary",
        "best_for": "deterministic_publication_boundary",
        "avoid_for": "deterministic_publication_boundary",
    }
    assert "基準点" in values["best_for"]
    assert not re.search(r"導入|採用|本番適用|限定した検証", joined)


def test_all_observational_decisions_expose_gate_recognizable_decision_voice():
    expected = {
        "NOW": "比較する",
        "TRY": "検証する",
        "WATCH": "比較する",
        "WAIT": "待つ",
        "AVOID": "見送る",
    }
    for decision, marker in expected.items():
        snapshot = _historical_snapshot()
        snapshot["case_id"] = f"observational-decision-voice-{decision.lower()}"
        snapshot["decision"] = decision
        result = compile_snapshot(snapshot)
        article = result["parsed"]["note_draft"]
        claims = classify_article_claims(result["parsed"])

        assert marker in article
        assert claims["decision"] >= 1, (decision, article)


def test_kvm_escape_incident_shape_keeps_observational_topic_and_decision_voice():
    snapshot = _historical_snapshot()
    snapshot.update({
        "case_id": "fresh-kvm-escape-decision-voice-regression",
        "canonical_entity_id": "url:https://pwn.ai/blog/kvmescape",
        "name": "An AI agent escaped Google's kvmCTF sandbox",
        "reader_title": "AIエージェントのサンドボックス脱出事例をどう見るか",
        "source": "HackerNews",
        "source_summary": "AIエージェントによるサンドボックス脱出の事例が報告されました。",
        "what": "攻撃事例として、確認できた挙動と条件を整理します。",
        "why_important": "AIエージェントへ与える権限境界を見直す判断材料になるためです。",
        "decision": "WATCH",
        "decision_score": 78,
        "decision_reason": "一つの攻撃事例を一般化せず、再現条件と影響範囲を分けて見る必要があります。",
        "action": "確認済みの条件を基準点として記録し、次の公式情報と比較する。",
        "primary_risk": "一事例から全環境へ危険性を一般化しないことです。",
        "best_for": "AIエージェントの権限設計を見直すチーム。",
        "avoid_for": "事例だけで全AIエージェントの危険性を断定したいチーム。",
        "evidence_urls": ["https://pwn.ai/blog/kvmescape"],
    })
    result = compile_snapshot(snapshot)
    article = result["parsed"]["note_draft"]
    claims = classify_article_claims(result["parsed"])

    assert "本格導入" not in article
    assert "基準点として追跡し、次の情報と比較する" in article
    assert claims["decision"] >= 1
