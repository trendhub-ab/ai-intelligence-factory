from __future__ import annotations

import hashlib
import json

import pytest

from note_delivery_strong_zero import (
    StrongZeroEvidenceError,
    parse_strong_zero_evidence_category,
    strong_zero_evidence_digest,
    validate_strong_zero_census,
)


def _strong_zero() -> dict[str, object]:
    return {
        "status": "census_complete_no_mutation",
        "authenticated": True,
        "private_note_card_count": 5,
        "exact_target_count": 0,
        "suspicious_blank_count": 0,
        "unreadable_count": 0,
        "decision": "strong_zero",
        "zero_model_calls": True,
        "mutation_count": 0,
    }


def test_validate_strong_zero_census_accepts_only_exact_safe_schema():
    census = _strong_zero()
    assert validate_strong_zero_census(census) == census


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("status", "ambiguous"),
        ("authenticated", False),
        ("private_note_card_count", 0),
        ("exact_target_count", 1),
        ("suspicious_blank_count", 1),
        ("unreadable_count", 1),
        ("decision", "ambiguous"),
        ("zero_model_calls", False),
        ("mutation_count", 1),
    ),
)
def test_validate_strong_zero_census_rejects_any_unsafe_value(field: str, value: object):
    census = _strong_zero()
    census[field] = value
    with pytest.raises(StrongZeroEvidenceError):
        validate_strong_zero_census(census)


def test_validate_strong_zero_census_rejects_missing_or_extra_keys():
    missing = _strong_zero()
    missing.pop("mutation_count")
    with pytest.raises(StrongZeroEvidenceError):
        validate_strong_zero_census(missing)

    extra = _strong_zero()
    extra["raw_title"] = "must never enter evidence schema"
    with pytest.raises(StrongZeroEvidenceError):
        validate_strong_zero_census(extra)


def test_strong_zero_evidence_digest_is_byte_compatible_with_phase_one_contract():
    census = _strong_zero()
    canonical = json.dumps(census, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert strong_zero_evidence_digest(census) == expected

    reordered = dict(reversed(tuple(census.items())))
    assert strong_zero_evidence_digest(reordered) == expected


def test_parse_strong_zero_evidence_category_accepts_exact_lowercase_sha256_only():
    digest = "a" * 64
    assert (
        parse_strong_zero_evidence_category(
            f"creation_absence_confirmed_strong_zero:{digest}"
        )
        == digest
    )


@pytest.mark.parametrize(
    "category",
    (
        "",
        "creation_absence_confirmed_strong_zero:",
        "creation_absence_confirmed_strong_zero:" + "a" * 63,
        "creation_absence_confirmed_strong_zero:" + "a" * 65,
        "creation_absence_confirmed_strong_zero:" + "A" * 64,
        "creation_absence_confirmed_strong_zero:" + "g" * 64,
        "creation_absence_confirmed_strong_zero:" + "a" * 64 + ":extra",
        "creation_absence_confirmed:" + "a" * 64,
    ),
)
def test_parse_strong_zero_evidence_category_rejects_malformed_evidence(category: str):
    with pytest.raises(StrongZeroEvidenceError):
        parse_strong_zero_evidence_category(category)
