from __future__ import annotations

from types import SimpleNamespace

import reader_quality_precision as rqp


def _signals(**overrides):
    base = {
        "technical_terms_per_1000_chars": 48.0,
        "opening_technical_terms_per_1000_chars": 46.0,
        "plain_language_bridge_present": False,
        "jargon_dense_paragraph_count": 3,
        "implementation_identifier_count": 2,
        "analogy_hits": 0,
        "analogy_used": False,
        "unexplained_jargon": [],
        "opening_non_engineer_access": "REVIEW",
        "narrative_pull": "REVIEW",
        "reader_temperature_rhythm": "GOOD",
        "reader_enjoyment": "GOOD",
        "information_budget": "REVIEW",
        "accessibility": "REVIEW",
        "jargon_translation": "REVIEW",
        "non_engineer_core_clarity": "REVIEW",
        "accessibility_issues": [
            "technical_term_concentration",
            "plain_language_bridge_missing",
            "jargon_translation_weak",
            "opening_non_engineer_access_weak",
        ],
        "enjoyment_issues": [],
        "explicit_reader_decision_action": True,
    }
    base.update(overrides)
    return base


def _specialist_article(explain_term: bool = True) -> str:
    term = (
        "DPoP（アクセストークンを特定の鍵に結びつける認証の仕組み）"
        if explain_term
        else "DPoP"
    )
    return f"""# OAuthのトークン盗用対策が変わる

認証基盤向けに{term}への対応が公開されました。何が変わるのか。盗まれたトークンだけでは使いにくくできる点が重要です。導入判断への影響は、既存のBearer運用より盗用耐性を高められることです。

ただし、対応クライアントや鍵管理には制約があり、導入すればすべての攻撃を防げる保証はありません。OAuthやOIDCとの組み合わせも確認が必要です。

私なら、まず限定環境で検証し、既存クライアントとの互換性を確認してから導入範囲を広げます。Evidenceでは仕様上の正式名称と条件をそのまま確認します。
"""


def test_specialist_density_passes_when_core_decision_and_term_bridge_are_clear():
    article = _specialist_article(explain_term=True)
    out = rqp.correct_reader_signals(
        article,
        _signals(unexplained_jargon=["DPoP"]),
    )

    assert out["plainness_requirement"] == "LOW"
    assert out["decision_accessibility"] == "GOOD"
    assert out["unexplained_jargon"] == []
    assert out["jargon_translation"] == "GOOD"
    assert out["non_engineer_core_clarity"] == "GOOD"
    assert "technical_term_concentration" not in out["accessibility_issues"]
    assert "plain_language_bridge_missing" not in out["accessibility_issues"]


def test_hardware_vendor_and_model_labels_do_not_block_specialist_decision_access():
    article = """# 単一GPUで視覚方策を学ぶ研究

arXivでロボット学習の研究が公開されました。何が変わるのか。教師モデルなしで視覚から行動を学び、NVIDIA RTX 4080 GPU 1台で検証できる点が重要です。

ただし、実機条件には制約があり、あらゆる環境で同じ性能を保証するものではありません。

私なら、まず限定したシミュレーション環境で検証し、既存手法と比較してから導入判断を進めます。
"""
    out = rqp.correct_reader_signals(
        article,
        _signals(
            unexplained_jargon=["NVIDIA", "RTX"],
            opening_technical_terms_per_1000_chars=30.0,
            plain_language_bridge_present=True,
        ),
    )

    assert out["plainness_requirement"] == "LOW"
    assert out["unexplained_jargon"] == []
    assert out["decision_accessibility"] == "GOOD"
    assert out["jargon_translation"] == "GOOD"
    assert out["non_engineer_core_clarity"] == "GOOD"


def test_bare_hardware_like_acronym_without_model_context_still_reviews():
    article = _specialist_article(explain_term=True) + "\nRTXを採用する。"
    out = rqp.correct_reader_signals(
        article,
        _signals(unexplained_jargon=["RTX"]),
    )

    assert "RTX" in out["unexplained_jargon"]
    assert out["decision_accessibility"] == "REVIEW"


def test_unexplained_required_specialist_term_still_reviews():
    article = _specialist_article(explain_term=False)
    out = rqp.correct_reader_signals(
        article,
        _signals(unexplained_jargon=["DPoP"]),
    )

    assert out["plainness_requirement"] == "LOW"
    assert out["decision_accessibility"] == "REVIEW"
    assert "DPoP" in out["unexplained_jargon"]
    assert "unexplained_acronyms" in out["accessibility_issues"]
    assert out["jargon_translation"] == "REVIEW"


def test_general_ai_service_keeps_high_plainness_requirement():
    article = """# 新しいAIサービスが公開

新しいAIサービスが公開されました。何が変わるのか。作業を自動化できる点が重要で、導入判断に影響します。

ただし利用条件には制約があり、すべての業務を自動化できる保証はありません。

私なら、まず小さな業務で試して比較し、効果を確認してから導入します。
"""
    out = rqp.correct_reader_signals(article, _signals())

    assert out["plainness_requirement"] == "HIGH"
    assert out["decision_accessibility"] == "GOOD"
    assert out["jargon_translation"] == "REVIEW"
    assert "technical_term_concentration" in out["accessibility_issues"]
    assert "plain_language_bridge_missing" in out["accessibility_issues"]


def test_install_appends_contract_to_fresh_and_retry_prompts_without_touching_fact_gate():
    module = SimpleNamespace(
        _reader_experience_signals=lambda article: _signals(),
        validate_human_appeal_gate=lambda parsed, peer_articles=None: ("ACCEPTABLE", []),
        build_decision_prompt=lambda *args, **kwargs: "BASE PROMPT",
        build_dynamic_retry_instruction=lambda rows: ("BASE RETRY", ["reader"]),
    )

    rqp.install(module)

    prompt = module.build_decision_prompt()
    retry, sections = module.build_dynamic_retry_instruction([])
    assert "Decision Accessibility Contract" in prompt
    assert "専門性を残したまま判断可能" in prompt
    assert "Decision Accessibility Contract" in retry
    assert sections == ["reader"]
    assert module.RUN397_DECISION_ACCESSIBILITY is True
