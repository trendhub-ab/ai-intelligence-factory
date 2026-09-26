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

CANONICALIZER_BLOB_SHA = "414089a14c238f104b2866507ddf8521c2baf420"
WRITER_BLOB_SHA = "dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2"
CANDIDATE_STATUS = "FROZEN_CANDIDATE_AWAITING_FRESH_HOLDOUT"


def compile_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Compile one structured record without mutating the caller's object.

    Returns both surfaces required for a future shadow/fresh-holdout evaluation:
    - canonicalized_snapshot / parsed: reader-facing candidate generated locally;
    - evidence_context: derived from the untouched original record for Gate use.

    This function does not run Gates and does not persist or publish anything.
    """
    original = deepcopy(dict(snapshot))
    writer.validate_snapshot(original)

    canonicalized = publication_canonicalizer.canonicalize_snapshot(original)
    parsed = writer.to_pipeline_parsed(canonicalized)
    evidence_context = writer.source_context(original)

    return {
        "status": CANDIDATE_STATUS,
        "original_snapshot": original,
        "canonicalized_snapshot": canonicalized,
        "parsed": parsed,
        "evidence_context": evidence_context,
        "canonicalizer_version": canonicalized.get("publication_canonicalizer_version"),
        "canonicalizer_blob_sha": CANONICALIZER_BLOB_SHA,
        "writer_blob_sha": WRITER_BLOB_SHA,
    }
