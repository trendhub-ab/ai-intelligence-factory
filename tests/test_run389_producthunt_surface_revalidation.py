import inspect

import run389_producthunt_surface_revalidation as r389


def _code(body: str, language: str = "markdown") -> dict:
    return {
        "type": "code",
        "code": {
            "language": language,
            "rich_text": [{"plain_text": body}],
            "caption": [],
        },
    }


def test_exact_five_migrated_targets_are_pinned_with_supported_sources():
    assert len(r389.TARGETS) == 5
    assert len({t.page_id for t in r389.TARGETS}) == 5
    assert {t.source for t in r389.TARGETS} == {"GitHub", "OfficialVendor"}


def test_latest_substantial_markdown_body_wins_without_mutation():
    old = "## この記事の結論\n" + "古い本文。" * 120
    new = "## この記事の結論\n" + "新しい本文。" * 120
    body, _caption, count = r389.select_latest_markdown_manuscript([
        _code(old),
        _code("print('not article')", "python"),
        _code(new),
    ])
    assert body == new
    assert count == 2


def test_missing_or_tiny_markdown_body_fails_closed():
    try:
        r389.select_latest_markdown_manuscript([_code("## short\nsmall")])
    except RuntimeError as exc:
        assert "no substantial markdown manuscript" in str(exc)
    else:
        raise AssertionError("tiny manuscript must fail closed")


def test_surface_clean_can_never_become_ready_without_body_reground_proof():
    class Pipeline:
        @staticmethod
        def _reader_experience_signals(_body):
            return {
                "reader_enjoyment": "GOOD", "narrative_pull": "GOOD",
                "information_budget": "GOOD", "reader_temperature_rhythm": "GOOD",
                "accessibility": "GOOD", "jargon_translation": "GOOD",
                "non_engineer_core_clarity": "GOOD",
                "repetitive_insight": False,
            }

    manuscript = (
        "## 30秒でわかるこの記事\n\n**何が出た？**\n短い説明です。\n\n"
        "**なぜ重要？**\n判断材料になります。\n\n**結論は？**\n限定環境で試します。\n\n"
        "## この記事の結論\n" + "平易な本文です。" * 120
    )
    result = r389.evaluate_surface("問題のないタイトル", manuscript, Pipeline())
    assert result["ready_eligible"] is False
    assert result["full_fact_evidence_gate_proven"] is False
    assert result["state"] in {"SURFACE_REVIEW", "SURFACE_CLEAN_BODY_REGROUND_PROOF_REQUIRED"}


def test_missing_reader_first_header_is_surface_review():
    class Pipeline:
        @staticmethod
        def _reader_experience_signals(_body):
            return {
                "reader_enjoyment": "GOOD", "narrative_pull": "GOOD",
                "information_budget": "GOOD", "reader_temperature_rhythm": "GOOD",
                "accessibility": "GOOD", "jargon_translation": "GOOD",
                "non_engineer_core_clarity": "GOOD",
                "repetitive_insight": False,
            }

    manuscript = "## この記事の結論\n" + "本文です。" * 150
    result = r389.evaluate_surface("タイトル", manuscript, Pipeline())
    assert result["state"] == "SURFACE_REVIEW"
    assert "presentation_contract_missing:reader_first_30sec_header" in result["issues"]


def test_core_has_no_model_or_write_path():
    source = inspect.getsource(r389)
    forbidden = (
        "call_gemini", "generate_content", "client.models", "requests.patch",
        "requests.post", "notion-update", "note_ready_sync.py", "publish_note",
    )
    assert all(token not in source for token in forbidden)
