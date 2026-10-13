"""Provider-free bounded proof for V2-001 shadow selection.

This file intentionally lives under tests/: it is a deterministic human-inspectable
proof harness, not a Production runtime surface.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json

from v2_shadow_selection import ShadowConfig, run_shadow_selection


FIXED_NOW = datetime(2026, 10, 14, 0, 0, tzinfo=timezone.utc)


def build_fixture_report() -> dict:
    """Return a deterministic two-provider V2-001 shadow report."""

    def official_provider():
        return [
            {
                "url": "https://vendor.example.com/releases/alpha?utm_source=official",
                "title": "Alpha model release",
                "description": (
                    "Official release evidence describing availability, concrete behavior, "
                    "implementation details, and operational constraints for evaluation."
                ),
                "published_at": "2026-10-13T12:00:00+00:00",
            }
        ]

    def discovery_provider():
        return [
            {
                "url": "https://vendor.example.com/releases/alpha?ref=feed",
                "title": "Alpha model release mirror",
                "description": (
                    "Discovery duplicate pointing to the same official release with enough "
                    "context to prove URL canonicalization and deterministic deduplication."
                ),
                "published_at": "2026-10-13T12:05:00+00:00",
            },
            {
                "url": "https://research.example.com/beta",
                "title": "Beta research update",
                "description": (
                    "Independent research evidence with sufficient descriptive detail for the "
                    "cheap screening lane but lower authority than the official release."
                ),
                "published_at": "2026-10-13T11:30:00+00:00",
            },
        ]

    def deterministic_deep_dive(candidate):
        return {
            "evidence_sufficient": (
                candidate.get("candidate_identity")
                == "https://vendor.example.com/releases/alpha"
            )
        }

    return run_shadow_selection(
        providers={
            "official": official_provider,
            "discovery": discovery_provider,
        },
        deep_dive=deterministic_deep_dive,
        config=ShadowConfig(
            max_candidates_per_provider=10,
            max_deep_dive_attempts=1,
            min_screening_score=40,
        ),
        now=FIXED_NOW,
        run_id="v2-001-provider-free-proof",
        v1_reference="https://legacy.example.com/v1-selection",
    )


if __name__ == "__main__":
    print(json.dumps(build_fixture_report(), ensure_ascii=False, sort_keys=True))
