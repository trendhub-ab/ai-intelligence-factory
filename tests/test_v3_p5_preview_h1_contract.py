"""Provider-free regression for Preview responses that omit Fact-Safe Review H1.

The previous live Gemini 3 Flash Preview response contained valid stage JSON, but
the Fact-Safe Review stage did not start with '# <title>'. Never accept a summary
or synthesize a missing H1 to force a structural PASS.
"""
from __future__ import annotations

import json

import pytest

from experiments.editorial_engine_v3_phase0.cases import READY_CASES
from experiments.editorial_engine_v3_phase0.contract import EDITORIAL_STAGES
from experiments.editorial_engine_v3_phase0.live import _parse_editorial_bundle
from experiments.editorial_engine_v3_phase0.prompts import (
    FACT_SAFE_FULL_MANUSCRIPT_CONTRACT,
    build_editorial_bundle_prompt,
    build_editorial_stage_prompts,
    build_persona_only_prompt,
)


def test_preview_full_manuscript_contract_is_present_in_both_c_review_paths() -> None:
    case = READY_CASES[0].case
    stages = build_editorial_stage_prompts(case)
    bundle = build_editorial_bundle_prompt(case)
    b_baseline = build_persona_only_prompt(case)
    assert FACT_SAFE_FULL_MANUSCRIPT_CONTRACT in stages["Fact-Safe Review"]
    assert FACT_SAFE_FULL_MANUSCRIPT_CONTRACT in bundle
    for phrase in (
        "監査コメント",
        "『# 記事タイトル』",
        "記事の全文",
        "変更点",
        "Persona Article Generation",
        "JSON",
        "Evidence / Facts / Sources",
    ):
        assert phrase in FACT_SAFE_FULL_MANUSCRIPT_CONTRACT
    assert FACT_SAFE_FULL_MANUSCRIPT_CONTRACT not in b_baseline
    assert FACT_SAFE_FULL_MANUSCRIPT_CONTRACT not in stages["Persona Article Generation"]
    assert '"Fact-Safe Review": "必ずMarkdown H1' in bundle


def _stages() -> dict[str, str]:
    fields = {key: f"test-{key}" for key in EDITORIAL_STAGES}
    fields["Persona Article Generation"] = "# 実験的な記事\n\nこれは根拠に沿う本文です。"
    fields["Fact-Safe Review"] = fields["Persona Article Generation"]
    return fields


def test_valid_full_manuscript_is_accepted_unchanged() -> None:
    values = _stages()
    final, parsed = _parse_editorial_bundle(json.dumps(values, ensure_ascii=False))
    assert final == values["Persona Article Generation"]
    assert parsed["Fact-Safe Review"] == values["Fact-Safe Review"]


@pytest.mark.parametrize(
    "not_article",
    (
        "Fact監査完了。修正不要です。",
        "OK。内容は正確です。",
        "本文はそのままで問題ありません。",
        "## 見出しだけ\n\nこれは本文です。",
    ),
)
def test_preview_invalid_review_must_fail_closed_not_autorepair(not_article: str) -> None:
    values = _stages()
    values["Fact-Safe Review"] = not_article
    with pytest.raises(RuntimeError, match="Fact-Safe Review.*missing Markdown H1"):
        _parse_editorial_bundle(json.dumps(values, ensure_ascii=False))
