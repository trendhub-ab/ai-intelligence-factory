#!/usr/bin/env python3
"""Run170.4: final member-first UX guard for Decision Intelligence.

This presentation-only layer keeps the member product understandable for
non-engineers without changing Product Review scores, Evidence, article
quality logic, or the internal decision model.

Durable guarantees:
- homepage picks are editorially selected for broad member utility, while the
  score-based ranker remains as a fallback;
- featured records keep plain Japanese and concrete next actions after sync;
- generic actions across the catalog become category-specific actions;
- only safe, context-stable technical terms are expanded in list summaries;
  natural source copy wins over aggressive mechanical rewriting.

ZERO Gemini/model requests.
"""
from __future__ import annotations

import json
import re
import sys
from typing import Any

import member_human_language_ux as base
import member_presentation_sync as mps
import member_ux_body_fast as body_fast
import member_ux_guard as guard


EDITORIAL_HOME_SYNC_IDS = (
    "github:langgenius/dify",
    "github:mintplex-labs/anything-llm",
    "github:nvidia-nemo/guardrails",
)

EDITORIAL_COPY_OVERRIDES: dict[str, dict[str, str]] = {
    "github:langgenius/dify": {
        "plain_summary": (
            "画面上でAIチャットや社内向けAIアプリを組み立てられる開発・運用基盤です。"
            "プログラミングだけに頼らず、社内文書検索、問い合わせ対応、業務フローなどを試作できます。"
        ),
        "topic": (
            "社内でAI活用を増やしたいのに、案件ごとに個別開発するのが大変なら、"
            "共通の土台として検討する価値があります。"
        ),
        "judgment_reason": (
            "複数のAIモデル、社内文書検索、外部サービス連携を一つの画面で管理でき、"
            "試作から本番運用までつなげやすい。非エンジニアを含むチームでAI活用を広げる共通基盤として有力です。"
        ),
        "next_action": (
            "まず1つの業務（例：社内問い合わせ、資料検索、FAQ）を選び、少人数で試す。"
            "入力データの外部送信先、権限、月額費用を確認してから本番導入を判断する。"
        ),
        "main_risk": (
            "便利な分、社内データや認証情報が集まりやすい。誰が何を使えるか、"
            "どの情報が外部へ送られるかを決めずに全社展開すると情報管理が複雑になります。"
        ),
        "best_for": (
            "社内問い合わせ、文書検索、FAQ、定型業務の自動化など、"
            "複数の業務AIをチームで短期間に作って試したい組織。"
        ),
        "avoid_for": (
            "ごく小さな単機能だけを作る場合や、すべてを自社コードで細かく管理したい場合。"
        ),
    },
    "github:mintplex-labs/anything-llm": {
        "plain_summary": (
            "社内文書を読み込ませて、その内容についてAIに質問できる「社内AI」を比較的簡単に作れるツールです。"
            "自社PCやサーバーで動かす構成も選べます。"
        ),
        "topic": (
            "社内規程、マニュアル、営業資料などを「探す」のに時間がかかっているなら、"
            "専用開発の前に試す価値があります。"
        ),
        "judgment_reason": (
            "社内文書とのチャットやAIエージェントを一つの環境で試せるため、"
            "専用開発に入る前の小規模検証に向いています。"
        ),
        "next_action": (
            "公開しても問題ない資料を5〜10件だけ入れ、3〜5人で1週間試す。"
            "回答の正確さ、使いやすさ、データの保存場所とAIへの送信先を確認する。"
        ),
        "main_risk": (
            "社内文書、会話履歴、APIキーなどが一つの環境に集まります。重要情報を入れる前に、"
            "保存場所・アクセス権・バックアップ・外部送信先を確認してください。"
        ),
        "best_for": (
            "社内規程、マニュアル、営業資料などをAIに読ませ、"
            "社員が自然な言葉で検索・質問できる環境を小さく試したい組織。"
        ),
        "avoid_for": (
            "大企業の厳格な権限管理や監査システムへ深く統合する必要がある場合や、"
            "独自アプリへ細かく組み込むことが最優先の場合。"
        ),
    },
    "github:nvidia-nemo/guardrails": {
        "plain_summary": (
            "社内AIやチャットAIに「答えてはいけない内容」「使ってはいけない機能」などの安全ルールを追加する"
            "ためのNVIDIAの仕組みです。AI任せにせず、アプリ側でも事故を防ぎます。"
        ),
        "topic": (
            "社員や顧客が使うAIを本番運用するなら、誤回答や危険な操作を減らす仕組みは避けて通れません。"
        ),
        "judgment_reason": (
            "AIの誤回答や危険な操作をモデル任せにせず、アプリ側でも制御できます。"
            "社内や顧客向けにAIを本番利用するなら、安全対策の一つとして検討価値が高いです。"
        ),
        "next_action": (
            "自社AIで「答えてほしくない質問」「実行させたくない操作」を10〜20個挙げ、"
            "実際にブロックできるか小規模テストする。これだけで安全対策が完結すると考えない。"
        ),
        "main_risk": (
            "この仕組みだけでAIの事故を完全には防げません。権限管理、機密情報の扱い、"
            "外部サービス連携など、別の安全対策と組み合わせる必要があります。"
        ),
        "best_for": (
            "社内AI、顧客向けチャットAI、業務を実行するAIに、禁止事項や安全ルールを追加したい組織。"
        ),
        "avoid_for": (
            "この仕組みを入れるだけで、AIのセキュリティ対策がすべて終わると考える運用。"
        ),
    },
}

GENERIC_MEMBER_ACTIONS = {
    "導入候補として、自社要件との適合と運用条件を最終確認する。",
    "代表業務を1つ選び、小さく試して効果と運用負荷を確認する。",
    "次回レビューまで監視し、成熟度・保守状況の変化を確認する。",
    "新規採用は見送り、保守中の代替候補を比較する。",
    "導入前に、自社の要件・費用・運用体制に合うかを最終確認する。",
    "実際の業務を1つ選び、小さく試して品質・費用・運用負荷を確認する。",
    "今すぐ導入はせず、自社に関係する用途が出たときに最新の研究結果を確認する。",
    "今は導入せず、保守状況や後継版の動きが変わったときに再確認する。",
    "新規採用は見送り、現在も保守されている代替候補を比較する。",
}


def _deep_tech_reason(state: dict[str, Any]) -> str:
    status = base._clean(state.get("status"))
    if status == "TEST":
        return "研究結果をそのまま本番へ持ち込まず、小さな再現テストを前提に判断します。"
    if status == "WATCH":
        return "研究段階の情報なので、今は導入対象ではなく判断材料として追います。"
    return ""


def refine_judgment_reason(
    state: dict[str, Any], review_copy: dict[str, str] | None = None
) -> str:
    """Keep ``判断理由`` distinct from ``なぜ今見る？`` and ``次にやること``."""
    review_copy = review_copy or {}
    current = base._humanize_terms(state.get("judgment_reason"))
    topic_key = mps._norm_key(state.get("topic"))
    action_key = mps._norm_key(state.get("next_action"))

    if (
        current
        and not base.BAD_REASON_RE.search(current)
        and mps._norm_key(current) != topic_key
        and len(mps._sentences(current)) == 1
    ):
        return current

    raw = review_copy.get("short_rationale") or current
    raw = mps._clean_rationale(base._humanize_terms(raw))
    descriptive: list[str] = []
    for sentence in mps._sentences(raw):
        key = mps._norm_key(sentence)
        if not key:
            continue
        if action_key and key == action_key:
            continue
        if mps._is_action_sentence(sentence):
            continue
        if "一次情報の現状を前提に" in sentence:
            continue
        if base.BAD_REASON_RE.search(sentence):
            continue
        descriptive.append(sentence)

    distinct = [s for s in descriptive if mps._norm_key(s) != topic_key]
    if distinct:
        return distinct[0]

    risk_reason = base._natural_reason_from_risk(
        base._clean(state.get("status")), base._clean(state.get("main_risk"))
    )
    if risk_reason:
        return risk_reason

    if base._clean(state.get("classification")) == "Deep Tech":
        deep_reason = _deep_tech_reason(state)
        if deep_reason:
            return deep_reason

    if descriptive:
        return descriptive[0]
    return current


def _simplify_plain_summary(text: Any) -> str:
    """Explain only terms whose replacement is safe in ordinary sentence grammar."""
    value = base._humanize_terms(text)
    if not value:
        return ""
    if "RAG" in value and "文書を検索して回答に使う仕組み（RAG）" not in value:
        value = re.sub(
            r"(?<![A-Za-z0-9])RAG(?![A-Za-z0-9])",
            "文書を検索して回答に使う仕組み（RAG）",
            value,
        )
    if "Agent Harness" in value and "AIエージェントの実行環境" not in value:
        value = value.replace("Agent Harness", "AIエージェントの実行環境（Agent Harness）")
    if "Vector Database" in value and "意味の近さで情報を探す" not in value:
        value = value.replace("Vector Database", "意味の近さで情報を探すデータベース（Vector Database）")
    if "推論・サービング" in value:
        value = value.replace("推論・サービング", "AIモデルを動かして回答を返す処理")
    if "トレーシング" in value and "記録・追跡" not in value:
        value = value.replace("トレーシング", "処理の記録・追跡（トレーシング）")
    return value


def _member_first_action(state: dict[str, Any]) -> str:
    """Turn only generic actions into concrete, category-aware member actions."""
    current = base._clean(state.get("next_action"))
    if current and current not in GENERIC_MEMBER_ACTIONS:
        return current

    status = base._clean(state.get("status"))
    category = base._clean(state.get("category"))
    classification = base._clean(state.get("classification"))

    if status == "ADOPT":
        if category == "製品・サービス":
            return "実際の業務を1つ選び、5人程度で試し、現在の方法と比べて時間・費用・使いやすさを確認してから導入範囲を決める。"
        if category == "セキュリティ":
            return "守りたい情報と禁止したい操作を10件程度挙げ、検証環境で防げるか確認し、既存の安全対策との役割分担を決める。"
        if category in {"AIモデル", "エージェント", "マルチモーダル"}:
            return "代表的な業務タスクを20件程度用意し、現在の候補と同じ条件で品質・速度・費用を比較する。"
        if category in {"開発ツール", "基盤", "データ"}:
            return "代表的な1つの処理を検証環境で動かし、現在の方法と速度・費用・運用負荷を比較する。"
        return "実際の利用場面を1つ決め、小規模に試して効果・費用・運用負荷を確認してから導入を判断する。"

    if status == "TEST":
        if category == "製品・サービス":
            return "実際の利用者3〜5人で1週間ほど試し、使いやすさ・回答品質・費用を現在の方法と比較する。"
        if category == "セキュリティ":
            return "想定する事故や禁止操作を10件程度用意し、検証環境でどこまで防げるかを確認する。"
        if category in {"AIモデル", "エージェント", "マルチモーダル"}:
            return "代表タスクを20件程度用意し、小規模テストで品質・速度・費用を現行候補と比較する。"
        if category in {"開発ツール", "基盤", "データ"}:
            return "代表的な1つの処理だけを検証環境で動かし、導入前後の速度・費用・運用負荷を比較する。"
        return "実際の利用場面を1つ選び、小規模テストで効果・費用・運用負荷を確認する。"

    if status == "WATCH":
        if classification == "Deep Tech":
            return "自社に関係する用途を1つ決め、次回レビュー時に性能・再現性・公開実装の有無が変わったか確認する。"
        return "今は導入せず、次回レビュー時または大型更新時に、保守状況・価格・主要機能の変化を再確認する。"

    if status == "AVOID":
        return "新規採用は止め、同じ用途で現在も保守されている候補を2〜3件比較する。"

    return current or "利用場面を1つ決め、必要な条件を確認してから次の判断へ進む。"


def _eligible_home_pick(state: dict[str, Any]) -> bool:
    return bool(
        state.get("classification") == "実務判断"
        and state.get("status") in {"ADOPT", "TEST"}
        and state.get("confidence") != "低"
        and isinstance(state.get("score"), (int, float))
        and not isinstance(state.get("score"), bool)
    )


def install_editorial_home_ranker() -> None:
    """Put broad member utility before technical score; keep old ranker as fallback."""
    original_assign = mps.assign_home_ranks

    def editorial_assign_home_ranks(
        states: list[dict[str, Any]], *, limit: int = mps.MEMBER_HOME_MAX
    ) -> list[dict[str, Any]]:
        for state in states:
            state["rank"] = None

        wanted = max(1, int(limit))
        eligible_by_id = {
            str(state.get("sync_id") or ""): state
            for state in states
            if _eligible_home_pick(state) and state.get("sync_id")
        }
        selected: list[dict[str, Any]] = []
        for sync_id in EDITORIAL_HOME_SYNC_IDS:
            state = eligible_by_id.get(sync_id)
            if state and state not in selected:
                selected.append(state)
                if len(selected) >= wanted:
                    break

        if len(selected) < wanted:
            selected_ids = {id(state) for state in selected}
            fallback_pool = [state for state in states if id(state) not in selected_ids]
            fallback = original_assign(fallback_pool, limit=wanted - len(selected))
            selected.extend(fallback)

        for state in states:
            state["rank"] = None
        for rank, state in enumerate(selected[:wanted], 1):
            state["rank"] = rank
        return selected[:wanted]

    mps.assign_home_ranks = editorial_assign_home_ranks


def _apply_editorial_copy(state: dict[str, Any]) -> bool:
    override = EDITORIAL_COPY_OVERRIDES.get(str(state.get("sync_id") or ""))
    if not override:
        return False
    state.update(override)
    return True


def install_refined_language_guard() -> tuple[dict[str, int], dict[str, int]]:
    summary_stats = guard.install_presentation_guard()
    install_editorial_home_ranker()
    guarded_source_state = mps._source_state
    index = base.load_review_copy_index()
    stats = {
        "review_copy_used": 0,
        "reasons_role_separated": 0,
        "summaries_simplified": 0,
        "generic_actions_made_specific": 0,
        "editorial_copy_overrides": 0,
        "bad_reasons_remaining": 0,
        "generic_topics_remaining": 0,
    }

    def refined_source_state(page: dict[str, Any]) -> dict[str, Any] | None:
        state = guarded_source_state(page)
        if not state:
            return None
        reviewed = base.review_copy_for_state(state, index)
        if reviewed:
            stats["review_copy_used"] += 1
        state = base.humanize_state(state, reviewed)

        before_summary = base._clean(state.get("plain_summary"))
        state["plain_summary"] = _simplify_plain_summary(before_summary)
        if base._clean(state.get("plain_summary")) != before_summary:
            stats["summaries_simplified"] += 1

        before_action = base._clean(state.get("next_action"))
        state["next_action"] = _member_first_action(state)
        if base._clean(state.get("next_action")) != before_action:
            stats["generic_actions_made_specific"] += 1

        before = base._clean(state.get("judgment_reason"))
        after = refine_judgment_reason(state, reviewed)
        state["judgment_reason"] = after
        if before != after:
            stats["reasons_role_separated"] += 1

        if _apply_editorial_copy(state):
            stats["editorial_copy_overrides"] += 1
        if base.BAD_REASON_RE.search(base._clean(state.get("judgment_reason"))):
            stats["bad_reasons_remaining"] += 1
        if base.GENERIC_TOPIC_RE.match(base._clean(state.get("topic"))):
            stats["generic_topics_remaining"] += 1
        return state

    mps._source_state = refined_source_state
    return summary_stats, stats


def run_presentation_sync() -> dict[str, Any]:
    summary_stats, refine_stats = install_refined_language_guard()
    result = mps.sync_member_presentation()
    result["summary_guard"] = summary_stats
    result["human_language_v2"] = refine_stats
    result["homepage_contract"] = guard.HOME_SHORTLIST_SIZE
    result["homepage_policy"] = "editorial_member_utility_first"
    result["editorial_home_sync_ids"] = list(EDITORIAL_HOME_SYNC_IDS)
    result["zero_gemini_calls"] = True
    if summary_stats.get("missing"):
        raise RuntimeError("Member summary guard left missing summaries")
    if refine_stats["bad_reasons_remaining"]:
        raise RuntimeError(
            f"Member copy still contains {refine_stats['bad_reasons_remaining']} malformed reasons"
        )
    if result.get("source_records", 0) >= guard.HOME_SHORTLIST_SIZE and result.get("homepage_count") != guard.HOME_SHORTLIST_SIZE:
        raise RuntimeError(
            f"Member homepage contract mismatch: expected {guard.HOME_SHORTLIST_SIZE}, got {result.get('homepage_count')}"
        )
    return result


def run_body_sync() -> dict[str, Any]:
    base.install_human_body_builder()
    result = body_fast.sync_member_page_bodies_fast()
    result["reader_order"] = ["これは何？", "いまの判断", "なぜ今見る？", "次にやること"]
    result["zero_gemini_calls"] = True
    return result


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) != 1 or args[0] not in {"presentation", "body"}:
        raise SystemExit("usage: python member_human_language_ux_v2.py [presentation|body]")
    result = run_presentation_sync() if args[0] == "presentation" else run_body_sync()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
