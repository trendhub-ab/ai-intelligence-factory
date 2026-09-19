"""A deterministic summary must not invent the fragment its own Gate rejects."""
from __future__ import annotations

import pytest

import note_manuscript as manuscript
import run249_final_publication_surface_gate as surface


COMPLETE_CONDITIONAL_SENTENCE = (
    "この仕組みは、確認済みの資料から判断に必要な情報を取り出し、"
    "担当者が参照先と注意点を見比べながら導入の適否を検討できるようにするものですが、"
    "利用環境によって結果が変わるため公開された事例だけを根拠に全社での採用を決めることはできません。"
)


def test_complete_writer_sentence_does_not_become_gate_blocking_fragment():
    compact = manuscript._compact_reader_summary(COMPLETE_CONDITIONAL_SENTENCE)
    assert surface._summary_fragment_issues({"why": compact}) == []
    # The negative conclusion and its condition must survive; replacing the comma
    # with a period/ellipsis would hide the Gate issue while changing the meaning.
    assert compact == COMPLETE_CONDITIONAL_SENTENCE


@pytest.mark.parametrize("separator", ["、", "，", ",", "；", ";"])
def test_summary_retains_late_condition_instead_of_cutting_at_clause(separator):
    source = ("対象となる利用環境と確認済みの資料を担当者が事前に照合する必要がありますが" * 2
              + separator + "この条件が満たされてもすべての用途に適することが確認されたわけではありません。")
    assert manuscript._compact_reader_summary(source) == source


def test_complete_first_sentence_is_selected_without_unrelated_following_sentence():
    source = COMPLETE_CONDITIONAL_SENTENCE + "次の段落では別の問題を扱います。"
    assert manuscript._compact_reader_summary(source) == COMPLETE_CONDITIONAL_SENTENCE


def test_writer_supplied_fragment_still_fails_the_unchanged_gate():
    fragment = "確認済みの条件に合わせて判断する必要がありますが、"
    compact = manuscript._compact_reader_summary(fragment)
    assert surface._summary_fragment_issues({"why": compact}) == [
        "reader_value_review:final_surface_summary_fragment:なぜ重要？"
    ]


def test_summary_and_header_retain_identical_condition():
    summary = manuscript.build_reader_first_summary(
        {"source_summary_text": "資料を確認できる仕組みです。",
         "why_important_text": COMPLETE_CONDITIONAL_SENTENCE,
         "action_text": "まず公開資料を比較します。"},
        extract_section=lambda *_: "", display_heading_aliases=lambda _: (),
        replace_public_decision_code_leaks=lambda text, _: (text, []),
    )
    header = manuscript.build_reader_first_header(
        summary, "Example", "https://example.com/source", "GitHub", None,
    )
    assert summary["why"] == COMPLETE_CONDITIONAL_SENTENCE
    assert COMPLETE_CONDITIONAL_SENTENCE in header
    assert surface._summary_fragment_issues(summary) == []


def test_final_surface_and_notion_payload_preserve_complete_summary():
    # Exercise real summary/projection/payload builders without constructing a
    # provider client or making a Notion request.
    import pipeline
    import run194_publication_contract as stamping
    import publication_contract

    parsed = {"title_text": "資料に基づいて導入条件を確認する。",
              "note_draft": "確認済みの条件を比較し、公開資料で分からない点を整理します。",
              "source_summary_text": "資料を確認できる仕組みです。",
              "why_important_text": COMPLETE_CONDITIONAL_SENTENCE,
              "action_text": "まず公開資料を比較します。"}
    issues, summary, projection = surface.final_surface_issues(
        pipeline, pipeline.build_clean_note_manuscript,
        pipeline.build_reader_first_summary, parsed,
    )
    assert issues == []
    assert COMPLETE_CONDITIONAL_SENTENCE in projection
    caption = publication_contract.current_ready_caption(projection)
    children = pipeline.build_notion_manuscript_children(projection, caption)
    children = stamping._rewrite_code_rich_text_losslessly(children, projection, 30)
    body = stamping._block_body(children[0])
    assert body == projection
    assert COMPLETE_CONDITIONAL_SENTENCE in body
    assert publication_contract.is_current_ready_block(body, caption)

def test_public_summary_preserves_plain_specific_final_over_generic_decision():
    sections = {
        "intro": "",
        "conclusion": "",
        "final": "まず社内の小規模環境で試す。",
    }
    parsed = {
        "source_summary_text": "新しい仕組みが公開された。",
        "why_important_text": "導入前の検証方法を見直す材料になる。",
        "decision_text": "TRY",
    }
    summary = manuscript.build_reader_first_summary(
        parsed,
        extract_section=lambda _draft, headings: sections.get(headings[0], ""),
        display_heading_aliases=lambda key: (key,),
        replace_public_decision_code_leaks=lambda text, _: (text, []),
    )
    assert summary["decision"] == "まず社内の小規模環境で試す。"
