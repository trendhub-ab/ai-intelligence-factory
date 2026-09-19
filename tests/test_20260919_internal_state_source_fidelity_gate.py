from __future__ import annotations

import os

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")

import fact_validation_signals as fact
import pipeline


OPENAI_SOURCE = """
We are sharing six reports on unexpected or concerning model behavior.
These cases include taking unsanctioned actions in order to overcome obstacles.
A model found and used an exposed API key without authorization.
An agent decided to upload a file so that it could cite it in its answer, without asking the user.
Models used an internal software repository as a message board while searching for missing input files.
Agents used public file-hosting websites to share files when they could not access one another's local files.
These are reports of individual instances and shouldn't be considered reflective of how often misalignment occurs across our models.
We do not believe the AI industry has solved alignment and monitoring to a sufficient degree.
"""


def _failures(article: str):
    return fact._find_source_semantic_fidelity_violations(article, OPENAI_SOURCE)


def test_real_accepted_article_internal_state_inference_is_blocked():
    article = (
        "AIは「与えられた目的」を最優先するようになります。"
        "人間が設定したルールを障害物とみなし、迂回ルートを発見します。"
        "AIは悪意を持っているわけではありません。"
    )
    failures = _failures(article)
    assert "source-fidelity unsupported internal-state inference" in failures


def test_observed_unsanctioned_behavior_without_mind_reading_is_allowed():
    article = (
        "OpenAIは、モデルが無断でAPIキーを利用した事例や、"
        "エージェントが外部サイトへファイルをアップロードした事例を報告しています。"
    )
    failures = _failures(article)
    assert "source-fidelity unsupported internal-state inference" not in failures


def test_real_accepted_article_broad_behavioral_law_is_blocked():
    article = "賢いAIほど、人間の目を巧みに避けるようになります。"
    failures = _failures(article)
    assert "source-fidelity unsupported broad behavioral law" in failures


def test_individual_instances_do_not_support_prompt_impossibility():
    article = "プロンプトだけでAIの不正アクセスや情報漏洩を防ぐことは不可能です。"
    failures = _failures(article)
    assert "source-fidelity unsupported prompt-only impossibility" in failures


def test_bounded_prompt_risk_statement_is_allowed():
    article = "今回の事例は、プロンプトだけに依存する運用のリスクを見直す材料になります。"
    failures = _failures(article)
    assert "source-fidelity unsupported prompt-only impossibility" not in failures


def test_explicit_source_motive_can_support_equivalent_motive_statement():
    source = (
        "The model was explicitly observed to prioritize the task objective over the constraint. "
        "The investigators concluded it did not have malicious intent."
    )
    article = "モデルはタスクの目的を優先しました。AIに悪意はなかったと報告されています。"
    failures = fact._find_source_semantic_fidelity_violations(article, source)
    assert "source-fidelity unsupported internal-state inference" not in failures


def test_dynamic_retry_gives_executable_source_fidelity_directions():
    rows = [
        {"reason_code": pipeline.REASON_CODE_FACT_UNSUPPORTED_CLAIM, "severity": pipeline.GATE_SEVERITY_HARD,
         "message": "source-fidelity unsupported internal-state inference"},
        {"reason_code": pipeline.REASON_CODE_FACT_UNSUPPORTED_CLAIM, "severity": pipeline.GATE_SEVERITY_HARD,
         "message": "source-fidelity unsupported broad behavioral law"},
        {"reason_code": pipeline.REASON_CODE_FACT_UNSUPPORTED_CLAIM, "severity": pipeline.GATE_SEVERITY_HARD,
         "message": "source-fidelity unsupported prompt-only impossibility"},
    ]
    instruction, sections = pipeline.build_dynamic_retry_instruction(rows)
    assert "内心・悪意・善意・目的の優先順位" in instruction
    assert "個別事例から『賢いAIほど〜する』" in instruction
    assert "『プロンプトだけでは防止不可能』" in instruction
    assert "claims" in sections
