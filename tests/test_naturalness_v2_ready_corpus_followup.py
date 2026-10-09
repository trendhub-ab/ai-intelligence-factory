"""Regression probes derived from real Ready manuscripts in Notion."""

import editorial_naturalness as en


def ready_like_article():
    return "\n\n".join([
        "## 最新機能の意味\n今回注目すべきは、単なる性能向上だけではありません。ここで一つの緊張感が生まれます。AIが回答者から作業環境へ変わり始めていることを示唆しています。",
        "## 本番での選び方\n今回の変化は、単に最新を追えばよいという話ではありません。ここで重要なのは、実験と本番の境界線です。基幹インフラとしての規律が求められ始めた証左と言えます。",
        "## 次の検証\n公開仕様と既存環境を比較し、レイテンシと再現性を測定します。",
    ])


def test_real_ready_style_clusters_are_detected_without_becoming_a_gate():
    signals = en.naturalness_v2_signals(ready_like_article())
    assert signals["repeated_dramatic_scaffolding"] == [1, 2]
    assert signals["repeated_abstract_closings"] == [1, 2]
    assert signals["repair_recommended"] is True

    # Advisory only: the legacy eligibility detector must not change.
    legacy = en.ai_style_composite_signals(ready_like_article(), [])
    assert legacy["high"] is False


def test_one_editorial_emphasis_is_not_enough_to_recommend_repair():
    article = (
        "## 変更点\n今回注目すべきは、単なる性能向上だけではありません。"
        "公式仕様ではレイテンシが短縮されています。\n\n"
        "## 判断\n本番環境では固定バージョンを使います。"
    )
    signals = en.naturalness_v2_signals(article)
    assert signals["repeated_dramatic_scaffolding"] == []
    assert signals["repeated_abstract_closings"] == []
    assert signals["repair_recommended"] is False


def test_retry_contract_names_the_real_ready_habits_and_preserves_substance():
    contract = en.build_naturalness_retry_contract(ready_like_article())
    assert "ドラマ化" in contract
    assert "抽象" in contract
    assert "節 1, 2" in contract
    for required in ("Fact", "Evidence", "Decision", "数値", "URL", "条件", "制約", "情報量"):
        assert required in contract
