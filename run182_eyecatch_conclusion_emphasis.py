"""Run182: emphasize the strongest title conclusion in restrained editorial orange.

Run180 already spends the single Gemini 3.5 layout request.  Run182 does not add a
provider call; it simply consumes the validated ``highlight_text`` returned in that same
schema response and asks Run181's deterministic PIL renderer to color only that exact
substring #F28C28.  Invalid or missing emphasis remains navy rather than causing a retry.
"""
from __future__ import annotations

from typing import Any

import run178_eyecatch_editorial_layout_optimizer as r178
import run181_eyecatch_visual_balance as r181


HIGHLIGHT_ORANGE = r181.HIGHLIGHT_ORANGE


def install(pipeline_module: Any) -> Any:
    if getattr(pipeline_module, "_RUN182_EYECATCH_CONCLUSION_EMPHASIS_INSTALLED", False):
        return pipeline_module

    def emphasized_renderer(
        title: str,
        summary: str,
        output_path: str,
        validated: dict[str, Any],
        category: str | None = None,
        date_label: str | None = None,
    ) -> str:
        raw_highlight = validated.get("highlight_text")
        highlight = raw_highlight if isinstance(raw_highlight, str) and raw_highlight else None
        return r181._render_balanced_plan(
            title,
            summary,
            output_path,
            validated,
            category=category,
            date_label=date_label,
            highlight_text=highlight,
        )

    r178._render_with_validated_plan = emphasized_renderer
    pipeline_module._RUN182_EYECATCH_CONCLUSION_EMPHASIS_INSTALLED = True
    pipeline_module.RUN182_EYECATCH_HIGHLIGHT_RGB = HIGHLIGHT_ORANGE
    pipeline_module.RUN182_EYECATCH_HIGHLIGHT_HEX = "#F28C28"
    return pipeline_module
