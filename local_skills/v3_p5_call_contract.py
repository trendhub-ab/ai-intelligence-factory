"""Validation-only P5 pure Writer call contract.

The selected P5 (#852, human mean 83/100) was generated without an
additional AIIF system instruction or explicit generation overrides. This
module protects that *call configuration*, separately from prompt identity.
No claim that different model/topic outputs achieve the same human score.
"""
from __future__ import annotations


class P5BaselineCallContractError(ValueError):
    """Refuse unsafe or misleading baseline call reproduction."""


def pure_p5_writer_config(
    config: dict,
    *,
    editorial_style: str,
    writer_boundary: str,
    request_origin: str,
    request_kind: str,
) -> dict:
    """Return baseline-equivalent generation configuration, proof-only.

    No system persona, forced temperature, token cap, tools, or override.
    Source-native Evidence remains in the P5 user prompt. Management output
    and Production Evidence/Fact/Publication gates are separate.
    """
    if (
        editorial_style != "v3_p5"
        or writer_boundary != "original"
        or request_origin != "article_revalidation"
        or request_kind != "deep_dive"
    ):
        raise P5BaselineCallContractError(
            "Pure P5 baseline call is restricted to original-writer article revalidation"
        )
    if config.get("tools"):
        raise P5BaselineCallContractError(
            "Pure P5 requires frozen source-native evidence; no provider search/url tools"
        )
    # Deliberately identical to the selected original Phase0
    # client.models.generate_content(model=model, contents=prompt) call.
    return {}
