"""Run183: scale the validated orange conclusion emphasis by 20%.

This is a zero-provider-call policy layer. Run180 still owns the single Gemini layout
request, Run182 validates/selects the exact highlight substring, and Run181 measures the
mixed-size line geometry. Run183 only sets the approved art-direction scale.
"""
from __future__ import annotations

from typing import Any

import run181_eyecatch_visual_balance as r181


HIGHLIGHT_FONT_SCALE = 1.20
HIGHLIGHT_MAX_FONT = 96


def install(pipeline_module: Any) -> Any:
    if getattr(pipeline_module, "_RUN183_EYECATCH_EMPHASIS_SCALE_INSTALLED", False):
        return pipeline_module

    r181.HIGHLIGHT_FONT_SCALE = HIGHLIGHT_FONT_SCALE
    r181.HIGHLIGHT_MAX_FONT = HIGHLIGHT_MAX_FONT

    pipeline_module._RUN183_EYECATCH_EMPHASIS_SCALE_INSTALLED = True
    pipeline_module.RUN183_EYECATCH_HIGHLIGHT_FONT_SCALE = HIGHLIGHT_FONT_SCALE
    pipeline_module.RUN183_EYECATCH_HIGHLIGHT_MAX_FONT = HIGHLIGHT_MAX_FONT
    return pipeline_module
