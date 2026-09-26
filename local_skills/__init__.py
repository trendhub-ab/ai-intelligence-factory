"""Provider-free Local Skills publication candidate.

The Stage 8 repair keeps Canonicalizer v4, adds a verified-evidence numeric
boundary, and advances the deterministic writer to v4. It remains canary-only
until a new untouched holdout validates the repaired bytes.
"""

from .compiler import (
    CANONICALIZER_BLOB_SHA,
    WRITER_BLOB_SHA,
    CANDIDATE_STATUS,
    EVIDENCE_BOUNDARY_VERSION,
    compile_snapshot,
)

__all__ = [
    "CANONICALIZER_BLOB_SHA",
    "WRITER_BLOB_SHA",
    "CANDIDATE_STATUS",
    "EVIDENCE_BOUNDARY_VERSION",
    "compile_snapshot",
]
