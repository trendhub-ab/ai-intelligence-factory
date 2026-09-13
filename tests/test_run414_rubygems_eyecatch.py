import ast
from pathlib import Path

import run414_rubygems_eyecatch as run414


def test_run414_exact_target_and_model_are_pinned():
    assert run414.PAGE_ID == "3d9479ff-dca9-819a-814c-e4a0aeb3263f"
    assert run414.EXPECTED_TITLE == "OpenAI agents carried out an undisclosed attack on RubyGems"
    assert run414.MODEL == "gemini-3.5-flash"


def test_run414_has_no_gemini_38_literal():
    source = Path(run414.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    string_values = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    assert not any("gemini-3.8" in value for value in string_values)


def test_run414_does_not_modify_article_body_surface():
    source = Path(run414.__file__).read_text(encoding="utf-8")
    assert '"アイキャッチ"' in source
    assert '"記事状態"' in source
    assert "blocks/" not in source
    assert "append" not in source.lower()


def test_run414_refuses_existing_eyecatch(monkeypatch):
    class Response:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"properties": {
                "記事名": {"title": [{"plain_text": run414.EXPECTED_TITLE}]},
                "記事状態": {"select": {"name": "Ready"}},
                "アイキャッチ": {"files": [{"name": "existing.png"}]},
            }}
    monkeypatch.setenv("NOTION_API_KEY", "test-token")
    monkeypatch.setattr(run414.requests, "get", lambda *a, **k: Response())
    try:
        run414._fetch_target()
    except RuntimeError as exc:
        assert "refuses to overwrite" in str(exc)
    else:
        raise AssertionError("existing eyecatch must fail closed")


def test_run415_extracts_json_from_later_content_part():
    data = {"candidates": [{"content": {"parts": [
        {"thought": True, "text": ""},
        {"text": '{"headline":"AIエージェントとRubyGems攻撃"}'},
    ]}}]}
    assert run414._extract_headline(data) == "AIエージェントとRubyGems攻撃"


def test_run415_extracts_fenced_json_without_relaxing_schema():
    data = {"candidates": [{"content": {"parts": [
        {"text": '```json\n{"headline":"RubyGemsを狙うAIエージェント"}\n```'},
    ]}}]}
    assert run414._extract_headline(data) == "RubyGemsを狙うAIエージェント"


def test_run415_fails_when_no_headline_json_exists():
    data = {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
    try:
        run414._extract_headline(data)
    except RuntimeError as exc:
        assert "JSON parse failed" in str(exc)
    else:
        raise AssertionError("invalid Gemini output must fail closed")
