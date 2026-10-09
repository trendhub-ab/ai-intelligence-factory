from __future__ import annotations

from datetime import datetime, timezone

import member_human_language_ux_v2 as ux_v2
import member_monthly_decision_brief_sync as brief
import member_presentation_body_sync as body
import member_reader_quality_policy as quality
import run307_use_decision_member_surface as run307


def _state(**overrides):
    state = {
        "page_id": "a" * 32,
        "sync_id": "github:ggml-org/llama.cpp",
        "name": "ggml-org/llama.cpp",
        "classification": "実務判断",
        "category": "基盤",
        "status": "ADOPT",
        "score": 94,
        "confidence": "高",
        "readiness": "高",
        "plain_summary": (
            "幅広いCPU・GPU環境で大規模言語モデル（LLM）をローカル実行できる推論基盤です。"
        ),
        "topic": "ローカル大規模言語モデル（LLM）の標準比較基盤として採用価値が高い。",
        "judgment_reason": (
            "量子化形式・モデル変換・ハードウェアバックエンドによって品質と速度が変わるため、"
            "同じモデル名でも構成を固定して評価する必要がある。"
        ),
        "main_risk": (
            "量子化形式・モデル変換・ハードウェアバックエンドによって品質と速度が変わるため、"
            "同じモデル名でも構成を固定して評価する必要がある。"
        ),
        "best_for": (
            "PC・Mac・エッジ端末・低コストサーバーでローカル大規模言語モデル（LLM）を動かし、"
            "量子化モデルとハードウェア効率を重視するチーム。"
        ),
        "avoid_for": "マネージドAPIだけで運用したい組織。",
        "next_action": "対象端末のメモリ・速度・量子化品質を測り、用途別にモデルを固定する。",
        "last_reviewed": "2026-10-02",
        "primary_url": "https://github.com/ggml-org/llama.cpp",
        "evidence": "https://github.com/ggml-org/llama.cpp",
        "related_article": "",
        "rank": 1,
        "current_month_change": False,
        "delta": 0,
        "change_reason": "",
    }
    state.update(overrides)
    return state


def _texts(blocks):
    return [text for _, text in body._body_fingerprint(blocks) if text]


def test_reader_benefit_uses_benefit_label_only_for_actual_benefit_copy():
    benefit = _state(
        topic="問い合わせ対応の手作業を減らし、同じ質問への回答をまとめて扱えます。",
    )
    neutral = _state()

    before = dict(neutral)
    assert quality.reader_benefit(benefit) == (
        "何が楽になる？",
        "問い合わせ対応の手作業を減らし、同じ質問への回答をまとめて扱えます。",
    )
    assert quality.reader_benefit(neutral) == (
        "何ができる？",
        neutral["plain_summary"],
    )
    assert neutral == before


def test_detail_page_matches_brief_decision_path_and_drops_old_primary_headings():
    headings = [
        text
        for kind, text in body._body_fingerprint(run307._build_children(_state()))
        if kind.startswith("heading_")
    ]

    expected = [
        "これは何？",
        quality.DATE_PREFIX,
        "いまの判断",
        "何ができる？",
        "誰・どんな仕事向け？",
        "まず何を試す？",
        "注意点",
        "根拠にした情報",
    ]
    assert headings == expected
    for old in (
        "いま、使える？",
        "こんな時に向いています",
        "今、見る理由",
        "ここは確認してください",
        "まずやること",
    ):
        assert old not in headings


def test_adopt_reason_never_falls_back_to_the_same_risk_llama_shape():
    state = _state()
    before = dict(state)

    assert ux_v2.refine_judgment_reason(state, {}) == ""
    reviewed = {
        "short_rationale": (
            "幅広いCPU・GPU環境で動作し、ローカル実行の選択肢を広げられる。"
        )
    }
    assert ux_v2.refine_judgment_reason(state, reviewed) == reviewed["short_rationale"]
    assert state == before
    assert state["status"] == "ADOPT"
    assert state["score"] == 94


def test_brief_uses_shared_dynamic_benefit_label_for_technical_topic():
    _, blocks, top_count, _ = brief.build_blocks(
        [_state()],
        now=datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc),
    )
    rendered = str(blocks)
    assert top_count == 1
    assert "何ができる？：" in rendered
    assert "何が楽になる？：" not in rendered
    assert _state()["plain_summary"] in rendered


def test_brief_keeps_benefit_label_when_source_copy_states_a_real_benefit():
    record = _state(
        topic="検索や確認にかかる手作業を減らし、必要な情報をまとめて扱えます。",
    )
    _, blocks, top_count, _ = brief.build_blocks(
        [record],
        now=datetime(2026, 10, 10, 3, 0, tzinfo=timezone.utc),
    )
    rendered = str(blocks)
    assert top_count == 1
    assert "何が楽になる？：" in rendered
    assert record["topic"] in rendered
