import pytest

from hybrid_gemini_writer import (
    ARTICLE_MARKER,
    TITLE_MARKER,
    HybridWriterError,
    build_gemini_writer_prompt,
    deterministic_management_data,
    parse_gemini_writer_output,
)


def _plan():
    return {
        "source_summary": "一次情報で確認できる事実。",
        "what": "何が起きたか。",
        "why_important": "実務上は判断材料が増えた。",
        "decision": "WATCH",
        "decision_reason": ["一般利用条件が一次情報では確認できない。"],
        "business_impact": 12,
        "technical_impact": 18,
        "urgency": 8,
        "market_impact": 10,
        "reliability": 12,
        "action": "一次情報で利用条件を確認する。",
        "article_value": 82,
        "article_angle": "数字の大きさと適用範囲を分けて読む。",
        "reader_bridge": "100%という数字ほど、何を測った数字かを見る。",
        "title_seed": "100%の数字をどう読むか。",
        "access_status": "NOT_CONFIRMED",
    }


def _item():
    return {
        "source": "HackerNews",
        "name": "Example",
        "url": "https://example.com/source",
        "source_context": "一次情報では特定条件の評価結果だけが確認されている。一般提供条件は記載されていない。",
    }


def test_prompt_keeps_gemini_to_final_writer_only():
    prompt = build_gemini_writer_prompt(_item(), _plan())
    assert "最終日本語Writer" in prompt
    assert "管理データを再計算・再生成してはいけません" in prompt
    assert TITLE_MARKER in prompt and ARTICLE_MARKER in prompt
    assert "GROQ DECISION PLAN" in prompt
    assert "SOURCE CONTEXT — factual ceiling" in prompt
    assert "access_status=NOT_CONFIRMED" in prompt


def test_prompt_does_not_ask_gemini_to_rescore():
    prompt = build_gemini_writer_prompt(_item(), _plan())
    for phrase in ("Decision Scoreを再計算", "採点してください", "Article Valueを採点"):
        assert phrase not in prompt


def test_management_data_is_deterministic_from_groq_plan():
    data = deterministic_management_data(_plan())
    assert data["decision"] == "WATCH"
    assert data["decision_score"]["total"] == 60
    assert data["article_value"] == 82
    assert data["access_status"] == "NOT_CONFIRMED"


def test_writer_parser_accepts_complete_natural_surface():
    paragraph = "これは一次情報の範囲を守りながら、読者が判断しやすいよう普通の言葉で説明する文章です。"
    article = (paragraph + "\n\n") * 30 + "私なら、いまは利用条件の一次情報を確認してから次を判断します。"
    title, body = parse_gemini_writer_output(
        f"{TITLE_MARKER}\n数字の大きさだけで決めてよい？\n{ARTICLE_MARKER}\n{article}"
    )
    assert title.endswith("？")
    assert body.endswith("。")


def test_writer_parser_rejects_list_and_short_or_incomplete_output():
    with pytest.raises(HybridWriterError, match="writer_list_output_forbidden"):
        parse_gemini_writer_output(
            f"{TITLE_MARKER}\nテスト。\n{ARTICLE_MARKER}\n" + ("本文です。" * 260) + "\n- 箇条書きです。"
        )
    with pytest.raises(HybridWriterError, match="writer_article_too_short"):
        parse_gemini_writer_output(
            f"{TITLE_MARKER}\nテスト。\n{ARTICLE_MARKER}\n短い本文です。"
        )
    with pytest.raises(HybridWriterError, match="writer_article_incomplete"):
        parse_gemini_writer_output(
            f"{TITLE_MARKER}\nテスト。\n{ARTICLE_MARKER}\n" + ("本文です。" * 250) + "途中"
        )
