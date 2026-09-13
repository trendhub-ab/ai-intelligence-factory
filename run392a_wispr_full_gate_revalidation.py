"""Run392A: temporary adapter precision for current ### Sources / Evidence boundary.

This does not change any gate. It only reconstructs the same pre-presentation phase
that Production validates before the final source section is attached.
"""
from __future__ import annotations

import re
import run392_wispr_full_gate_revalidation as run392

_original = run392.reconstruct_pre_presentation_draft


def _production_phase_draft(manuscript: str) -> str:
    draft = _original(manuscript)
    draft = re.sub(r"(?ms)^#{2,3} Sources / Evidence\s*\n.*\Z", "", draft, count=1)
    return re.sub(r"\n{3,}", "\n\n", draft).strip()


run392.reconstruct_pre_presentation_draft = _production_phase_draft

if __name__ == "__main__":
    raise SystemExit(run392.main())
