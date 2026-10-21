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


def test_copy_cache_roundtrip_and_invalidation(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import run180_eyecatch_semantic_layout as semantic
    title = "米政府がDeepSeekの排除を指示"
    summary = "行政機関への対応を求めた。"
    article = "記事本文の確認済み要約"
    path = str(tmp_path / "image.png")
    sub = semantic.ee.editorial_subheadline(
        summary, semantic.ee.editorial_hook_from_title(title, max_chars=48)
    )
    plan = semantic._deterministic_complete_title_plan(title, summary)
    assert plan is not None
    calls = []
    monkeypatch.setattr(semantic, "_request_layout_plan",
                        lambda *args: calls.append(args) or plan)
    pipeline = SimpleNamespace(logger=None)
    semantic.install(pipeline)
    pipeline.generate_note_editorial_eyecatch(title, summary, path, article_text=article)
    assert (tmp_path / "image.png.copy.json").exists()
    pipeline.generate_note_editorial_eyecatch(title, summary, path, article_text=article)
    assert len(calls) == 1
    pipeline.generate_note_editorial_eyecatch(title, summary, path, article_text=article + "変更")
    assert len(calls) == 2


def test_copy_prompt_contains_article_excerpt_without_extra_call():
    import run180_eyecatch_semantic_layout as semantic
    prompt = semantic._layout_prompt(
        "AI規制の転換", "規制の変更が発表された", "本文から確認できる規制の対象と変更点"
    )
    assert "本文から確認できる規制の対象と変更点" in prompt
    assert "article_excerpt" in prompt
    assert "新しい事実" in prompt
