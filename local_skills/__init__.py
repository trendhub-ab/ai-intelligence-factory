"""Provider-free Local Skills publication candidate.

The integrated candidate keeps the v4.3.6 Fresh-4/4 lineage, retains later
reader-access/evidence repairs, and absorbs topic-fit rules that were previously
owned only by A+. It remains canary-only until the integrated bytes complete a
new untouched Fresh 4/4 revalidation.
"""

from .compiler import (
    BASE_FRESH_4_OF_4_CANONICALIZER_BLOB_SHA,
    BASE_FRESH_4_OF_4_WRITER_BLOB_SHA,
    CANONICALIZER_BLOB_SHA,
    WRITER_BLOB_SHA,
    INTEGRATION_VERSION,
    CANDIDATE_STATUS,
    EVIDENCE_BOUNDARY_VERSION,
    compile_snapshot,
)

__all__ = [
    "BASE_FRESH_4_OF_4_CANONICALIZER_BLOB_SHA",
    "BASE_FRESH_4_OF_4_WRITER_BLOB_SHA",
    "CANONICALIZER_BLOB_SHA",
    "WRITER_BLOB_SHA",
    "INTEGRATION_VERSION",
    "CANDIDATE_STATUS",
    "EVIDENCE_BOUNDARY_VERSION",
    "compile_snapshot",
]
