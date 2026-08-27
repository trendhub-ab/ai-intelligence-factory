"""Zero-Gemini X output layer for AI Intelligence Factory."""

from .freeform import ANGLES, build_free_chip_post, choose_angle, extract_core_conclusion
from .generator import X_VARIANTS, build_x_post, build_x_variants, render_markdown, save_pending_post
from .persona import CHIP_PERSONA, validate_chip_text
from .runner import (
    find_latest_screening_snapshot,
    generate_batch,
    generate_from_latest_observed_history,
    load_latest_observed_history,
    load_records,
)
from .selector import select_x_candidates

__all__ = [
    "ANGLES",
    "X_VARIANTS",
    "CHIP_PERSONA",
    "validate_chip_text",
    "build_free_chip_post",
    "choose_angle",
    "extract_core_conclusion",
    "build_x_post",
    "build_x_variants",
    "render_markdown",
    "save_pending_post",
    "select_x_candidates",
    "load_records",
    "find_latest_screening_snapshot",
    "load_latest_observed_history",
    "generate_batch",
    "generate_from_latest_observed_history",
]
