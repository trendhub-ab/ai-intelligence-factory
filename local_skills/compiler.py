"""Provider-free publication compiler candidate.

This adapter deliberately contains no network, provider, Notion, note, or
Production side effects.  Evidence validation must continue to use the original
structured record; only the reader-facing snapshot is canonicalized before the
frozen Local Writer renders it.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from . import publication_canonicalizer
from . import writer
from .evidence_boundary import EVIDENCE_BOUNDARY_VERSION, apply_evidence_boundary

CANONICALIZER_BLOB_SHA = "414089a14c238f104b2866507ddf8521c2baf420"
WRITER_BLOB_SHA = "508dd3a3be8492142bdc617996d7f1fb6f84a4da"
CANDIDATE_STATUS = "FRESH_CANARY_PASS_AWAITING_BROADER_VALIDATION"


def compile_snapshot(snapshot: Mapping[str, Any], *, evidence_context: str | None = None) -> dict[str, Any]:
    """Compile one structured record without mutating the caller's object.

    Returns both surfaces required for a future shadow/fresh-holdout evaluation:
    - canonicalized_snapshot / parsed: reader-facing candidate generated locally;
    - evidence_context: derived from the untouched original record for Gate use.

    This function does not run Gates and does not persist or publish anything.
    """
    original = deepcopy(dict(snapshot))
    writer.validate_snapshot(original)

    canonicalized = publication_canonicalizer.canonicalize_snapshot(original)
    gate_evidence_context = (
        writer.source_context(original)
        if evidence_context is None
        else str(evidence_context or "")
    )
    bounded, evidence_boundary = apply_evidence_boundary(
        canonicalized, gate_evidence_context
    )
    parsed = writer.to_pipeline_parsed(bounded)

    return {
        "status": CANDIDATE_STATUS,
        "original_snapshot": original,
        "canonicalized_snapshot": bounded,
        "parsed": parsed,
        "evidence_context": gate_evidence_context,
        "evidence_boundary": evidence_boundary,
        "evidence_boundary_version": EVIDENCE_BOUNDARY_VERSION,
        "canonicalizer_version": canonicalized.get("publication_canonicalizer_version"),
        "canonicalizer_blob_sha": CANONICALIZER_BLOB_SHA,
        "writer_blob_sha": WRITER_BLOB_SHA,
    }
