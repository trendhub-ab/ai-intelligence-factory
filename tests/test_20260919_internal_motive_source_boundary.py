from __future__ import annotations

import inspect

import canonical_article_contract as contract


def test_writer_contract_forbids_unsourced_internal_motive_storytelling():
    text = contract.canonical_writer_contract()
    assert "行動から内心を逆算しない" in text
    assert "内部意図・動機・判断理由を補完しない" in text
    assert "悪意がある／ない" in text
    assert "最適解として選んだ" in text
    assert "企業・研究者の発表意図も同様" in text


def test_reader_repair_drops_existing_unsupported_motive_instead_of_preserving_it():
    text = contract.canonical_reader_repair_contract()
    assert "前稿に、一次情報が明示していない内部意図・動機・判断理由" in text
    assert "その物語を保持せず" in text
    assert "理由は確認できない" in text
    assert "新しい説明を作らない" in text


def test_final_reader_check_rechecks_motive_source_boundary():
    text = contract.canonical_final_reader_check()
    assert "行動から内心・悪意・目的・判断理由を推測していない" in text
    assert "観測事実だけに戻す" in text


def test_contract_change_adds_no_provider_or_network_surface():
    source = inspect.getsource(contract)
    for forbidden in (
        "requests.get(",
        "requests.post(",
        "genai.Client(",
        "_generate_via_chat(",
        "GEMINI_API_KEY",
    ):
        assert forbidden not in source
