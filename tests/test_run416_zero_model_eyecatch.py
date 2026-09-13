from pathlib import Path

import run416_rubygems_zero_model_eyecatch as run416


def test_run416_headline_is_source_faithful_and_bounded():
    assert run416.HEADLINE == "AIエージェントがRubyGemsを攻撃"
    assert 8 <= len(run416.HEADLINE) <= 30
    assert "成功" not in run416.HEADLINE


def test_run416_has_no_model_api_surface():
    source = Path(run416.__file__).read_text(encoding="utf-8")
    assert "GEMINI_API_KEY" not in source
    assert "generativelanguage.googleapis.com" not in source
    assert "_gemini_headline" not in source


def test_run416_reuses_exact_guarded_bridge():
    source = Path(run416.__file__).read_text(encoding="utf-8")
    assert "bridge._fetch_target()" in source
    assert "bridge._render(HEADLINE)" in source
    assert "bridge._upload_to_notion(path)" in source
