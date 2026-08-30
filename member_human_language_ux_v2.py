#!/usr/bin/env python3
"""Run170.2: final member-first UX guard for Decision Intelligence.

This presentation-only layer keeps the member product understandable for
non-engineers without changing Product Review scores, Evidence, article
quality logic, or the internal decision model.

It adds two durable guarantees on top of Run170/170.1:
- the three homepage picks are editorially selected for broad member utility,
  with the score-based ranker retained only as a fallback;
- the three featured records keep plain Japanese, concrete next actions, and
  customer-facing risk/use-case copy after every automated Notion sync.

ZERO Gemini/model requests.
"""
from __future__ import annotations

import json
import sys
from typing import Any

import member_human_language_ux as base
import member_presentation_sync as mps
import member_ux_body_fast as body_fast
import member_ux_guard as guard


# Homepage is an editorial product surface, not a leaderboard. These picks cover
# three questions a broad non-engineer member can act on immediately:
# 1) how to build a business AI, 2) how to try internal-document AI,
# 3) how to add a safety layer before wider deployment.
EDITORIAL_HOME_SYNC_IDS = (
    "github:langgenius/dify",
    "github:mintplex-labs/anything-llm",
    "github:nvidia-nemo/guardrails",
)

# Presentation-only copy. Internal scores, evidence, classifications and source
# records remain untouched. Keeping this keyed by canonical sync ID makes the
# copy deterministic and resilient to title changes.
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

    # A clean, single-role reason should be preserved.
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
