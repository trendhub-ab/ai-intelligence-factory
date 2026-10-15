from __future__ import annotations

import inspect

import pytest

from v2_github_acquisition import acquire_github_candidates


EVENTS = [
    {
        "id": "release-v2",
        "repository": "openai/openai-python",
        "event_kind": "release",
        "url": "https://github.com/openai/openai-python/releases/tag/v2.0.0",
        "title": "AI SDK release v2.0.0",
        "description": "Release changes deployment APIs and production integration behavior.",
        "published_at": "2026-10-15T02:00:00+00:00",
    },
    {
        "id": "tag-v1",
        "repository": "openai/openai-python",
        "event_kind": "tag",
        "url": "https://github.com/openai/openai-python/releases/tag/v1.9.0",
        "title": "AI SDK tag v1.9.0",
        "description": "Tagged SDK update with concrete API changes.",
        "published_at": "2026-10-14T02:00:00+00:00",
    },
]


def test_github_requires_exact_repository_allowlist():
    with pytest.raises(ValueError, match="repository"):
        acquire_github_candidates(
            repository="openai/openai-python-fork",
            allowed_repositories={"openai/openai-python"},
            events=EVENTS,
        )


def test_github_normalizes_bounded_release_metadata_with_provenance():
    result = acquire_github_candidates(
        repository="openai/openai-python",
        allowed_repositories={"openai/openai-python"},
        events=EVENTS,
        max_events=1,
    )

    assert result == [
        {
            "primary_url": "https://github.com/openai/openai-python/releases/tag/v2.0.0",
            "title": "AI SDK release v2.0.0",
            "description": "Release changes deployment APIs and production integration behavior.",
            "published_at": "2026-10-15T02:00:00+00:00",
            "source_family": "github",
            "provider": "GitHub",
            "repository": "openai/openai-python",
            "event_kind": "release",
            "canonical_url": "https://github.com/openai/openai-python/releases/tag/v2.0.0",
            "upstream_id": "release-v2",
        }
    ]


def test_github_drops_nonallowlisted_ambiguous_and_unsupported_events():
    events = [
        dict(EVENTS[0], repository="openai/openai-python-fork"),
        dict(EVENTS[0], id="issue", event_kind="issue", url="https://github.com/openai/openai-python/issues/1"),
        dict(EVENTS[0], id="lookalike", url="https://github.com.evil.example/openai/openai-python/releases/tag/v2"),
        EVENTS[1],
    ]

    result = acquire_github_candidates(
        repository="openai/openai-python",
        allowed_repositories={"openai/openai-python"},
        events=events,
    )

    assert [item["upstream_id"] for item in result] == ["tag-v1"]


def test_github_accepts_only_release_tag_or_changelog_event_kinds():
    accepted = []
    for kind in ("release", "tag", "changelog"):
        event = dict(EVENTS[0], id=kind, event_kind=kind)
        result = acquire_github_candidates(
            repository="openai/openai-python",
            allowed_repositories={"openai/openai-python"},
            events=[event],
        )
        accepted.append(result[0]["event_kind"])

    assert accepted == ["release", "tag", "changelog"]


def test_github_adapter_is_deterministic_and_has_no_write_or_model_surface():
    kwargs = dict(
        repository="openai/openai-python",
        allowed_repositories={"openai/openai-python"},
        events=EVENTS,
        max_events=10,
    )
    assert acquire_github_candidates(**kwargs) == acquire_github_candidates(**kwargs)

    signature = inspect.signature(acquire_github_candidates)
    forbidden = {
        "token",
        "write",
        "mutation",
        "notion",
        "note",
        "publish",
        "ready_state",
        "delivery_ledger",
        "gemini",
        "model",
        "writer",
    }
    assert forbidden.isdisjoint(signature.parameters)
