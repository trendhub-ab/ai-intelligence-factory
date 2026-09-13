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
    monkeypatch.setattr(run414.requests, "get", lambda *a, **k: Response())
    try:
        run414._fetch_target()
    except RuntimeError as exc:
        assert "refuses to overwrite" in str(exc)
    else:
        raise AssertionError("existing eyecatch must fail closed")
