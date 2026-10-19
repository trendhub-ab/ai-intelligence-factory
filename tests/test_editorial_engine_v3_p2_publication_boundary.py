from __future__ import annotations

import json

import pytest

from experiments.editorial_engine_v3_phase0.contract import validate_reader_facing_article
from experiments.editorial_engine_v3_phase0.live import _parse_editorial_bundle


@pytest.mark.parametrize("token", ["TRY", "WATCH", "PASS", "AVOID"])
@pytest.mark.parametrize("placement", ["# {token} について\n\n本文", "# タイトル\n\n{token} を選ぶ"])
def test_internal_decision_label_is_rejected(token: str, placement: str) -> None:
    with pytest.raises(ValueError, match="internal decision label"):
        validate_reader_facing_article(placement.format(token=token))


def test_normal_japanese_article_is_accepted() -> None:
    validate_reader_facing_article("# 新しいAIの使い道\n\n私は、ここが気になった。")


def test_exact_evidence_quotation_can_be_exempted() -> None:
    article = '# 研究の話\n\n論文は "PASS" と記している。'
    validate_reader_facing_article(article, source_quotes=('"PASS"',))
    with pytest.raises(ValueError, match="internal decision label"):
        validate_reader_facing_article(article)


def test_partial_or_unmatched_source_quote_cannot_exempt_verdict() -> None:
    article = "# 研究の話\n\nTRYを選ぶべきだ。"
    with pytest.raises(ValueError, match="internal decision label"):
        validate_reader_facing_article(article, source_quotes=("研究には TRY と書かれていた",))


def test_bundle_parser_fails_closed_when_final_leaks_label() -> None:
    payload = {
        "Writer Reaction": "反応",
        "Editorial Discovery": "発見",
        "Cognitive Shift": "変化",
        "Persona Article Generation": "# タイトル\n\n私はここが気になる。",
        "Fact-Safe Review": "# タイトル\n\nTRY",
    }
    with pytest.raises(RuntimeError, match="internal decision label"):
        _parse_editorial_bundle(json.dumps(payload, ensure_ascii=False))


def test_bundle_accepts_repaired_draft_label() -> None:
    payload = {
        "Writer Reaction": "反応",
        "Editorial Discovery": "発見",
        "Cognitive Shift": "変化",
        "Persona Article Generation": "# タイトル\n\nTRY と書かれた下書き。",
        "Fact-Safe Review": "# タイトル\n\n私はここが気になった。",
    }
    article, stages = _parse_editorial_bundle(json.dumps(payload, ensure_ascii=False))
    assert article == payload["Fact-Safe Review"]
    assert stages["Persona Article Generation"] == payload["Persona Article Generation"]
