from types import SimpleNamespace

import groq_quality_contract_sync as sync


def test_run357_rewrites_only_system_generated_watch_phrase():
    calls = {"count": 0}

    def polish(parsed):
        calls["count"] += 1
        out = dict(parsed)
        out["note_draft"] = str(out.get("note_draft") or "").replace("WATCH", "今後の動きを注視する")
        return out, ["base"]

    p = SimpleNamespace(_apply_final_japanese_polish=polish)
    sync.install_quality_interaction_contract(p)
    out, changes = p._apply_final_japanese_polish({"note_draft": "判断はWATCHです。"})
    assert "新しい一次情報が出るまで待ち、出た時点で再評価する" in out["note_draft"]
    assert "今後の動きを注視する" not in out["note_draft"]
    assert calls["count"] == 1
    assert any("watch_quality_interaction_contract" in x for x in changes)


def test_run357_does_not_rewrite_unrelated_human_authored_monitoring_phrase():
    def polish(parsed):
        return dict(parsed), []

    p = SimpleNamespace(_apply_final_japanese_polish=polish)
    sync.install_quality_interaction_contract(p)
    original = "利用者は今後の動きを注視する必要がある。"
    out, changes = p._apply_final_japanese_polish({"note_draft": original})
    assert out["note_draft"] == original
    assert changes == []


def test_run358_compound_gloss_and_sf_are_false_positive_only():
    article = "SFのような話ですが、CI/CD（自動ビルド環境）を使います。"
    assert sync.reader_precision_unexplained_acronyms(article) == []


def test_run358_keeps_real_unexplained_acronym():
    article = "この処理ではQXZを使って結果を出します。"
    assert sync.reader_precision_unexplained_acronyms(article) == ["QXZ"]


def test_run358_topic_fragments_do_not_trigger_repetition():
    article = """
AIエージェントの群れが大量のパッケージを投稿しました。

エージェントが目的を達成する過程で境界を越える可能性があります。

このエージェントの権限設定を監査します。

エージェント群による別の挙動も確認されています。

ドキュメント生成処理には外部サービスが関わります。

ドキュメント生成のリクエストがサーバーで実行されます。

ドキュメント生成環境の権限も点検します。
"""
    assert sync.reader_precision_repetitive_insight(article) is False


def test_run358_still_detects_genuine_long_repetition():
    repeated = "同じ判断根拠を繰り返して説明しているため読者の理解が進みません"
    article = f"""
最初の説明です。{repeated}。

別の説明です。{repeated}。

結論前の説明です。{repeated}。
"""
    assert sync.reader_precision_repetitive_insight(article) is True


def test_run358_wrapper_never_erases_unrelated_density_issue():
    def signals(article):
        return {
            "unexplained_jargon": ["CI"],
            "accessibility": "REVIEW",
            "accessibility_issues": ["unexplained_acronyms", "technical_term_concentration"],
            "repetitive_insight": False,
            "enjoyment_issues": [],
        }

    p = SimpleNamespace(_reader_experience_signals=signals)
    sync.install_reader_signal_precision_contract(p)
    result = p._reader_experience_signals("CI/CD（自動ビルド環境）を使います。")
    assert result["unexplained_jargon"] == []
    assert "unexplained_acronyms" not in result["accessibility_issues"]
    assert "technical_term_concentration" in result["accessibility_issues"]
    assert result["accessibility"] == "REVIEW"


def test_run359_sync_is_instruction_only_and_forbids_extra_call():
    text = sync.GROQ_READER_EXECUTION_CONTRACT
    assert "削除・意味カテゴリへの圧縮" in text
    assert "専門語を別の専門語で説明しない" in text
    assert "追加provider callの許可ではない" in text
    assert "retry" not in text.lower()


def test_combined_installer_is_idempotent_and_provider_neutral():
    calls = {"polish": 0, "signals": 0}

    def polish(parsed):
        calls["polish"] += 1
        return dict(parsed), []

    def signals(article):
        calls["signals"] += 1
        return {"unexplained_jargon": [], "accessibility_issues": [], "repetitive_insight": False, "enjoyment_issues": []}

    p = SimpleNamespace(_apply_final_japanese_polish=polish, _reader_experience_signals=signals)
    sync.install_provider_neutral_quality_contracts(p)
    first_polish = p._apply_final_japanese_polish
    first_signals = p._reader_experience_signals
    sync.install_provider_neutral_quality_contracts(p)
    assert p._apply_final_japanese_polish is first_polish
    assert p._reader_experience_signals is first_signals
    assert p.GROQ_QUALITY_SYNC_VERSION == sync.SYNC_VERSION
    assert not hasattr(p, "should_attempt_dynamic_retry")
