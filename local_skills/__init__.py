"""Frozen provider-free Local Skills publication candidate.

This package is intentionally not wired into Production.  It exposes the exact
frozen Stage 6 Canonicalizer v4 + Local Writer v3 through a small deterministic
compiler interface so a future untouched holdout can validate the same code.
"""

from .compiler import (
    CANONICALIZER_BLOB_SHA,
    WRITER_BLOB_SHA,
    CANDIDATE_STATUS,
    compile_snapshot,
)

__all__ = [
    "CANONICALIZER_BLOB_SHA",
    "WRITER_BLOB_SHA",
    "CANDIDATE_STATUS",
    "compile_snapshot",
]
