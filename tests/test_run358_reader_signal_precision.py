from types import SimpleNamespace

import runtime_layers


def test_compound_acronym_gloss_and_common_sf_are_not_unexplained():
    article = (
        "SFのような話ですが、CI/CD（自動ビルド環境）を使う現場では、"
        "外部コードの自動実行範囲を確認する必要があります。"
    )
    assert runtime_layers._reader_precision_unexplained_acronyms(article) == []


def test_real_rubygems_topic_fragments_are_not_repetitive_insight():
    article = """
AIエージェントの群れが大量のパッケージを投稿しました。

エージェントが目的を達成する過程で境界を越える可能性があります。

このエージェントの権限設定を監査します。

エージェント群による別の挙動も確認されています。

ドキュメント生成処理には外部サービスが関わります。

ドキュメント生成のリクエストがサーバーで実行されます。

ドキュメント生成環境の権限も点検します。
"""
    assert runtime_layers._reader_precision_repetitive_insight(article) is False


def test_genuinely_repeated_long_wording_is_still_detected():
    repeated = "同じ判断根拠を繰り返して説明しているため読者の理解が進みません"
    article = f"""
最初の説明です。{repeated}。

別の見出しの説明です。{repeated}。

結論前の説明です。{repeated}。
"""
    assert runtime_layers._reader_precision_repetitive_insight(article) is True


def test_precision_wrapper_only_demotes_reproduced_false_positives():
    def original(article):
        return {
            "unexplained_jargon": ["SF", "CI"],
            "accessibility": "REVIEW",
            "accessibility_issues": [
                "unexplained_acronyms",
                "technical_term_concentration",
                "jargon_translation_weak",
            ],
            "repetitive_insight": True,
            "reader_enjoyment": "REVIEW",
            "enjoyment_issues": ["repetitive_insight"],
            "jargon_translation": "REVIEW",
            "non_engineer_core_clarity": "REVIEW",
            "information_budget": "REVIEW",
        }

    pipeline = SimpleNamespace(_reader_experience_signals=original)
    runtime_layers.install_reader_signal_precision_contract(pipeline)

    article = (
        "SFのような話ですが、CI/CD（自動ビルド環境）を使う現場の話です。\n\n"
        "AIエージェントの権限を確認します。\n\n"
        "エージェントが外部へ接続する範囲を確認します。\n\n"
        "このエージェントの実行環境も確認します。"
    )
    signals = pipeline._reader_experience_signals(article)

    assert signals["unexplained_jargon"] == []
    assert "unexplained_acronyms" not in signals["accessibility_issues"]
    # Genuine density/translation review survives the precision correction.
    assert signals["accessibility"] == "REVIEW"
    assert "technical_term_concentration" in signals["accessibility_issues"]
    assert "jargon_translation_weak" in signals["accessibility_issues"]
    assert signals["jargon_translation"] == "REVIEW"
    assert signals["non_engineer_core_clarity"] == "REVIEW"
    assert signals["information_budget"] == "REVIEW"
    assert signals["repetitive_insight"] is False
    assert signals["reader_signal_precision_contract"] == "run358"


def test_precision_install_is_idempotent():
    calls = {"count": 0}

    def original(article):
        calls["count"] += 1
        return {"unexplained_jargon": [], "accessibility_issues": [], "repetitive_insight": False}

    pipeline = SimpleNamespace(_reader_experience_signals=original)
    runtime_layers.install_reader_signal_precision_contract(pipeline)
    wrapped = pipeline._reader_experience_signals
    runtime_layers.install_reader_signal_precision_contract(pipeline)

    assert pipeline._reader_experience_signals is wrapped
    pipeline._reader_experience_signals("plain article")
    assert calls["count"] == 1
