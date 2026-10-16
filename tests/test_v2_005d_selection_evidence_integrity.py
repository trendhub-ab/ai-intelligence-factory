from __future__ import annotations

from datetime import datetime, timezone

import pytest

from v2_shadow_observation import build_deep_dive_prompt
from v2_shadow_selection import normalize_candidate, rank_candidates, score_selection_value


NOW = datetime(2026, 10, 16, 5, 0, tzinfo=timezone.utc)


def test_selection_value_requires_ai_relevance_in_title_not_description():
    candidate = {
        "title": "v3.28.0",
        "description": (
            "Agent API release adds enterprise deployment workflow integration "
            "and improves automation for users."
        ),
    }

    assert score_selection_value(candidate) == (0, [])


@pytest.mark.parametrize(
    "title",
    [
        "GPT-6 for everyone",
        "ChatGPT Work update",
        "Introducing Claude Opus 5",
        "Gemini API availability",
    ],
)
def test_selection_value_recognizes_branded_ai_titles(title):
    score, reasons = score_selection_value({"title": title, "description": ""})

    assert score > 0
    assert "ai_relevance" in reasons


def test_rank_prefers_major_official_model_announcement_over_opaque_sdk_version_release():
    official = normalize_candidate(
        {
            "url": "https://openai.com/index/gpt-6-for-everyone",
            "title": "GPT-6 for everyone",
            "description": "",
            "published_at": None,
            "source_family": "official_vendor",
        },
        provider="OfficialVendor",
        acquired_at=NOW,
    )
    github = normalize_candidate(
        {
            "url": "https://github.com/openai/openai-python/releases/tag/v3.28.0",
            "title": "v3.28.0",
            "description": (
                "Agent API release adds enterprise deployment workflow integration, "
                "automation support, and user-facing improvements with substantive detail."
            ),
            "published_at": "2026-10-16T04:00:00+00:00",
            "source_family": "github",
            "repository": "openai/openai-python",
            "event_kind": "release",
        },
        provider="GitHub",
        acquired_at=NOW,
    )

    ranked = rank_candidates([github, official], now=NOW)
    by_identity = {item["candidate_identity"]: item for item in ranked}

    assert by_identity[github["candidate_identity"]]["screening_score"] > by_identity[official["candidate_identity"]]["screening_score"]
    assert by_identity[github["candidate_identity"]]["selection_value_score"] == 0
    assert by_identity[official["candidate_identity"]]["selection_value_score"] > 0
    assert ranked[0]["candidate_identity"] == official["candidate_identity"]


def test_title_grounding_preserves_description_assisted_applied_research_value():
    candidate = {
        "title": "AI inference optimization for language models",
        "description": (
            "New benchmark results reduce deployment cost and provide a practical "
            "implementation workflow for production users."
        ),
    }

    score, reasons = score_selection_value(candidate)

    assert score >= 45
    assert "ai_relevance" in reasons
    assert "decision_value" in reasons
    assert "applied_reader_value" in reasons


def test_deep_dive_prompt_excludes_internal_selection_and_screening_metadata():
    prompt = build_deep_dive_prompt(
        {
            "candidate_identity": "https://example.com/item",
            "provider": "OfficialVendor",
            "primary_url": "https://example.com/item",
            "title": "GPT-6 API launch",
            "description": "Official source metadata describing availability.",
            "source_timestamp": "2026-10-16T04:00:00+00:00",
            "screening_score": 70,
            "screening_reasons": ["stable_identity", "official_source"],
            "selection_value_score": 45,
            "selection_value_reasons": ["ai_relevance", "decision_value", "change_novelty"],
        }
    )

    assert "screening_score" not in prompt
    assert "screening_reasons" not in prompt
    assert "selection_value_score" not in prompt
    assert "selection_value_reasons" not in prompt

    assert '"provider": "OfficialVendor"' in prompt
    assert '"primary_url": "https://example.com/item"' in prompt
    assert '"title": "GPT-6 API launch"' in prompt
    assert '"description": "Official source metadata describing availability."' in prompt
    assert '"source_timestamp": "2026-10-16T04:00:00+00:00"' in prompt
