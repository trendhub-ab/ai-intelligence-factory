"""Zero-Gemini X output layer for AI Intelligence Factory.

This package is intentionally isolated from the article pipeline. It reads
already-produced intelligence data and turns suitable items into reviewable X
post drafts without calling external APIs or mutating production state.
"""

from .generator import build_x_post, render_markdown, save_pending_post
from .selector import select_x_candidates

__all__ = [
    "build_x_post",
    "render_markdown",
    "save_pending_post",
    "select_x_candidates",
]
