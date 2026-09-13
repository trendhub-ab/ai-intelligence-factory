from pathlib import Path

import note_draft_automation as base
import run417_note_body_verification as run417


class Body:
    def __init__(self, text):
        self.text = text
    def inner_text(self, timeout=5000):
        return self.text


def manuscript():
    return """# AIが勝手に他社サーバーを突破した？OpenAIエージェントが起こしたRubyGems騒動から考える権限管理の境界線

### 元情報
- 主一次情報: OpenAI agents carried out an undisclosed attack on RubyGems

もし業務の自動化を任せたAIが、指示されたデータを集めるために勝手に外部サービスへ侵入したらどう感じるでしょうか。

これは十分に長い検証用本文です。前半の事実説明を含み、途中にも判断材料を配置して、本文全体が挿入されたかを複数地点で確認できるようにします。

中盤ではRubyGemsとAIエージェントの関係を説明し、読者が何を確認すべきかを整理します。ここは中盤アンカーとして残る文章です。

最後に、一般化できない点と未確認事項を残し、導入を急がず権限管理を点検するという判断で締めます。これは後半アンカーです。
"""


def test_run417_allows_note_body_to_omit_leading_h1():
    source = run417._visible_body_source(manuscript())
    body_text = run417._normalize_visible_text(source)
    run417.verify_body_content(Body(body_text), manuscript())


def test_run417_rejects_short_partial_insertion():
    try:
        run417.verify_body_content(Body("### 元情報 主一次情報"), manuscript())
    except base.NoteDraftError as exc:
        assert "malformed draft" in str(exc)
    else:
        raise AssertionError("short partial body must fail closed")


def test_run417_rejects_body_with_only_one_distributed_anchor():
    expected = run417._normalize_visible_text(run417._visible_body_source(manuscript()))
    first = run417._anchors(expected)[0]
    fake = first + " ダミー" * 100
    try:
        run417.verify_body_content(Body(fake), manuscript())
    except base.NoteDraftError as exc:
        assert "malformed draft" in str(exc)
    else:
        raise AssertionError("one anchor must not prove a complete body")


def test_run417_normalizes_note_whitespace_and_nfkc():
    expected = run417._normalize_visible_text(run417._visible_body_source(manuscript()))
    actual = expected.replace(" ", "\u00a0")
    run417.verify_body_content(Body(actual), manuscript())


def test_run417_is_zero_model_and_no_public_release_surface():
    source = Path(run417.__file__).read_text(encoding="utf-8").lower()
    assert "gemini_api_key" not in source
    assert "generativelanguage.googleapis.com" not in source
    assert "publish" not in source
    assert "release" not in source
