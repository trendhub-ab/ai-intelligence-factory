import run180_eyecatch_semantic_layout as semantic


def test_existing_complete_clause_is_reused():
    source = "米政府がDeepSeekの排除を指示｜行政機関の対応を解説"
    assert semantic._safe_existing_headline_clause(source) == "米政府がDeepSeekの排除を指示"


def test_no_arbitrary_truncation_without_separator():
    assert semantic._safe_existing_headline_clause(
        "米政府がDeepSeekの排除を指示し行政機関の対応が変わる"
    ) is None


def test_does_not_drop_model_identifier():
    assert semantic._safe_existing_headline_clause(
        "AI開発の転換点｜Gemini 3.6 Flashが新たに登場"
    ) is None


def test_rejects_dangling_clause():
    assert semantic._safe_existing_headline_clause(
        "DeepSeekを禁止するため｜政府が方針を発表"
    ) is None
