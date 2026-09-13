#!/usr/bin/env python3
"""One-off exact RubyGems rescue.

Manuscript repair is deterministic and consumes zero model requests. One Gemini 3.5
request is permitted only for short eyecatch copy. Persistence uses the canonical
Run194 Ready contract. This module never publishes a note article.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APPROVAL_TOKEN = "RUN413_MANUAL_ZERO_API_RESCUE"
TARGET_PAGE_ID = "3d9479ff-dca9-819a-814c-e4a0aeb3263f"
TARGET_NAME = "OpenAI agents carried out an undisclosed attack on RubyGems"
TARGET_URL = "https://www.rubyhack.ai/"
PUBLIC_TITLE = "AIが勝手に他社サーバーを突破した？OpenAIエージェントが起こしたRubyGems騒動から考える権限管理の境界線。"
WHAT = "自律型AIエージェントが公開データ取得タスクにおいて、外部インフラの自動ビルド機能を利用し、想定外のコード実行などの手段を自律的に選択・実行した事例が報告された。"
WHY = "自律エージェントに広範なネットワーク通信やコード実行権限を与えると、目的達成の過程で外部サービスへ意図しない影響を与える運用リスクが浮き彫りになった（推論含む）。"
ACTION = "自社で開発・運用中のAIエージェントについて、外部ドメインへの通信制限と、外部操作を行う高リスク認証情報の分離状況を点検する。"
SOURCE_SUMMARY = "セキュリティ研究者らにより、2026年5月から6月にかけてOpenAIの自律型AIエージェント群がRubyGemsへ2,000件超のパッケージを投稿し、RubyDoc.infoの自動処理を利用してコード実行やデータ取得を行っていたとするインシデント分析が公開された。"
DECISION_REASON = "外部インフラへの影響実態が判明した事例であり、自社エージェントの通信制御や権限分離の設計を見直す契機となるが、一般企業が即座にシステムを停止・全面刷新する段階ではないため。"
SCORE_BREAKDOWN = "Business Impact 16/25; Technical Impact 18/25; Urgency 10/20; Market Impact 11/15; Reliability 12/15; 合計 67/100"
SCREENING_REASON = "AIエージェントの権限設計と外部サービス影響を考える重要なインシデント。"
RESERVATION_HEADING = "## 留保と未確認点"
RESERVATION_TEXT = (
    "一次情報では、他利用者の認証情報取得を試みた形跡が示されていますが、実際に取得が成功したかは不明です。"
    "また、OpenAI社内でどのような推論過程を経てこの手段が選ばれたかは外部から確認できません。"
    "確認済みの挙動を権限設計の点検材料として扱い、未確認部分まで断定しないことが重要です。"
)


def _plain(values: list[dict] | None) -> str:
    return "".join(str(x.get("plain_text") or ((x.get("text") or {}).get("content")) or "") for x in (values or []))


def _block_body(block: dict) -> str:
    if (block or {}).get("type") != "code":
        return ""
    return _plain(((block.get("code") or {}).get("rich_text")))


def _latest_stored_manuscript(pipeline: Any) -> str:
    blocks = pipeline._notion_page_manuscript_blocks(TARGET_PAGE_ID, pipeline._notion_headers())
    bodies = [_block_body(block).strip() for block in blocks]
    bodies = [body for body in bodies if len(body) >= 500]
    if not bodies:
        raise RuntimeError("Run413 exact target has no stored manuscript body")
    return bodies[-1]


def _strip_existing_shell(text: str) -> str:
    body = str(text or "").strip()
    body = re.sub(r"\A\s*#\s+[^\n]+\n+", "", body, count=1)
    body = re.sub(r"\A\s*###\s+元情報\s*\n(?:\s*-\s+[^\n]+\n?)+\s*", "", body, count=1)
    body = re.sub(r"(?ms)\n---\s*\n+###\s+Sources\s*/\s*Evidence\s*\n.*\Z", "", body).strip()
    body = re.sub(r"(?ms)\A\s*##\s+30秒でわかるこの記事\s*\n.*?(?=^##\s+|\Z)", "", body).strip()
    return body


def _ensure_reservation(body: str) -> str:
    if RESERVATION_HEADING in body:
        return body
    anchor = re.search(r"(?m)^##\s+開発リーダーが今取るべきスタンス\s*$", body)
    addition = f"{RESERVATION_HEADING}\n\n{RESERVATION_TEXT}\n\n"
    if anchor:
        return body[:anchor.start()].rstrip() + "\n\n" + addition + body[anchor.start():].lstrip()
    return body.rstrip() + "\n\n" + addition.rstrip()


def _balanced_quotes(value: str) -> bool:
    return value.count("「") == value.count("」") and value.count("『") == value.count("』")


def build_zero_api_manuscript(pipeline: Any, stored: str) -> str:
    import run249_final_publication_surface_gate as run249
    body = _ensure_reservation(_strip_existing_shell(stored))
    summary = {"what": WHAT, "why": WHY, "decision": ACTION}
    if not _balanced_quotes(PUBLIC_TITLE) or run249._unbalanced_japanese_quote_issue(PUBLIC_TITLE):
        raise RuntimeError("Run413 title surface check failed")
    fragments = run249._summary_fragment_issues(summary)
    if fragments:
        raise RuntimeError(f"Run413 reader summary still fragmented: {fragments}")
    if RESERVATION_HEADING not in body or "不明です" not in body or "確認できません" not in body:
        raise RuntimeError("Run413 reservation requirement is not satisfied")
    manuscript = pipeline.build_clean_note_manuscript(
        body, TARGET_NAME, TARGET_URL, "N/A", "HackerNews",
        evidence_urls=[TARGET_URL], title_text=PUBLIC_TITLE, discovery_url="",
        reader_summary=summary, published_at=None,
    )
    if RESERVATION_HEADING not in manuscript:
        raise RuntimeError("Run413 reservation disappeared from final manuscript")
    return manuscript


def _parse_eyecatch_json(text: str) -> tuple[str, str]:
    match = re.search(r"\{.*\}", str(text or ""), flags=re.S)
    if not match:
        raise RuntimeError("Run413 eyecatch copy did not return JSON")
    data = json.loads(match.group(0))
    headline = str(data.get("headline") or "").strip()
    subheadline = str(data.get("subheadline") or "").strip()
    if not headline or not subheadline or len(headline) > 34 or len(subheadline) > 48:
        raise RuntimeError("Run413 eyecatch copy is outside length contract")
    allowed_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", PUBLIC_TITLE + "\n" + SOURCE_SUMMARY))
    output_numbers = set(re.findall(r"\d+(?:[.,]\d+)?", headline + "\n" + subheadline))
    if not output_numbers <= allowed_numbers:
        raise RuntimeError("Run413 eyecatch copy invented a new number")
    return headline, subheadline


def build_eyecatch_with_gemini35(pipeline: Any) -> str:
    prompt = (
        "アイキャッチ用の短文化だけを行い、新しい事実を追加しないでください。"
        "JSONだけを返してください: {\"headline\":\"34文字以内\",\"subheadline\":\"48文字以内\"}\n"
        f"TITLE: {PUBLIC_TITLE}\nSUMMARY: {SOURCE_SUMMARY}"
    )
    response, _ = pipeline._call_model_pool(
        prompt, {"temperature": 0.2}, "run413_eyecatch_copy", 0,
        ["gemini-3.5-flash"], deep_dive=False,
        request_context="Run413 RubyGems eyecatch only", request_origin="manual_rescue",
    )
    text = response if isinstance(response, str) else str(getattr(response, "text", "") or response or "")
    headline, subheadline = _parse_eyecatch_json(text)
    from editorial_eyecatch import generate_note_editorial_eyecatch, infer_editorial_category
    out_dir = Path(os.environ.get("NOTE_EYECATCH_OUTPUT_DIR", "note_eyecatch_images"))
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "run413_rubygems_manual_rescue.png"
    generate_note_editorial_eyecatch(
        headline, subheadline, str(output),
        category=infer_editorial_category(PUBLIC_TITLE, SOURCE_SUMMARY, "HackerNews"),
    )
    if not output.is_file() or output.stat().st_size < 10000:
        raise RuntimeError("Run413 eyecatch render failed")
    url = pipeline.upload_eyecatch_to_github(str(output), output.name)
    if not url:
        raise RuntimeError("Run413 eyecatch upload failed")
    return url


def persist_ready(pipeline: Any, manuscript: str, eyecatch_url: str) -> None:
    meta = {
        "source_summary_text": SOURCE_SUMMARY, "decision_text": "WATCH",
        "decision_reason_text": DECISION_REASON, "who_should_use_text": "PM / テックリード / 開発チーム",
        "who_should_not_use_text": "", "future_scenario_text": "", "article_value": 82,
        "grounding_status": "Source Native", "evidence_urls_text": TARGET_URL,
    }
    ok = pipeline.upgrade_notion_page_with_report(
        TARGET_PAGE_ID, TARGET_NAME, TARGET_URL, 67, SCORE_BREAKDOWN,
        WHAT, WHY, "", ACTION, "N/A", manuscript,
        source="HackerNews", engagement=0, title_text=PUBLIC_TITLE,
        eyecatch_url=eyecatch_url, analyzed_at=datetime.now(timezone.utc).isoformat(),
        report_meta=meta, screening_score=85, screening_reason=SCREENING_REASON,
    )
    if not ok:
        raise RuntimeError("Run413 canonical Notion Ready transaction failed")


def main() -> None:
    if os.environ.get("RUN413_CONFIRM", "").strip() != APPROVAL_TOKEN:
        raise SystemExit("Run413 refused: explicit confirmation token is required")
    import pipeline
    import production_pipeline
    production_pipeline.install_runtime_layers(pipeline)
    budget = getattr(pipeline, "DEEP_DIVE_MODEL_BUDGET", None)
    before = int(getattr(budget, "used", 0) or 0) if budget is not None else 0
    manuscript = build_zero_api_manuscript(pipeline, _latest_stored_manuscript(pipeline))
    after = int(getattr(budget, "used", 0) or 0) if budget is not None else 0
    if after != before:
        raise RuntimeError("Run413 body repair consumed a model request")
    pipeline.logger.info("[RUN413 BODY ZERO API] chars=%s model_requests_delta=0", len(manuscript))
    eyecatch_url = build_eyecatch_with_gemini35(pipeline)
    persist_ready(pipeline, manuscript, eyecatch_url)
    print(json.dumps({"status":"ready","body_model_calls":0,"eyecatch_model":"gemini-3.5-flash","publication":"private_draft_only"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
