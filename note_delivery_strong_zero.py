from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


CENSUS_KEYS = frozenset(
    {
        "status",
        "authenticated",
        "private_note_card_count",
        "exact_target_count",
        "suspicious_blank_count",
        "unreadable_count",
        "decision",
        "zero_model_calls",
        "mutation_count",
    }
)
EVIDENCE_CATEGORY_PREFIX = "creation_absence_confirmed_strong_zero:"
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


class StrongZeroEvidenceError(ValueError):
    pass


def validate_strong_zero_census(census: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(census, Mapping) or set(census) != CENSUS_KEYS:
        raise StrongZeroEvidenceError("strong-zero census schema mismatch")

    safe = {key: census[key] for key in sorted(CENSUS_KEYS)}
    if safe["status"] != "census_complete_no_mutation":
        raise StrongZeroEvidenceError("census did not complete safely")
    if safe["authenticated"] is not True:
        raise StrongZeroEvidenceError("census authentication was not proven")
    if safe["decision"] != "strong_zero":
        raise StrongZeroEvidenceError("census is not strong_zero")
    if safe["zero_model_calls"] is not True or safe["mutation_count"] != 0:
        raise StrongZeroEvidenceError("census was not zero-model read-only")
    if int(safe["private_note_card_count"] or 0) <= 0:
        raise StrongZeroEvidenceError("private draft surface was not observable")
    if int(safe["exact_target_count"] or 0) != 0:
        raise StrongZeroEvidenceError("target draft is still observable")
    if int(safe["suspicious_blank_count"] or 0) != 0:
        raise StrongZeroEvidenceError("census contains suspicious blank cards")
    if int(safe["unreadable_count"] or 0) != 0:
        raise StrongZeroEvidenceError("census contains unreadable cards")
    return dict(census)


def strong_zero_evidence_digest(census: Mapping[str, Any]) -> str:
    safe = validate_strong_zero_census(census)
    payload = json.dumps(
        safe,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_strong_zero_evidence_category(category: str) -> str:
    value = str(category or "")
    if not value.startswith(EVIDENCE_CATEGORY_PREFIX):
        raise StrongZeroEvidenceError("strong-zero evidence category prefix mismatch")
    digest = value[len(EVIDENCE_CATEGORY_PREFIX) :]
    if _DIGEST_RE.fullmatch(digest) is None:
        raise StrongZeroEvidenceError("strong-zero evidence digest is invalid")
    return digest
