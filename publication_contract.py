"""Fail-closed provenance contract for public-note Ready manuscripts.

`Ready` is a historical workflow state, not proof that persisted bytes were produced by the
current production policy.  The publication contract therefore derives provenance from the
actual code that can affect public article text, evidence interpretation, CTA, persistence,
and eyecatch output.  No manual Run-number bump is required: changing any manifest file changes
the policy SHA automatically.

Each Ready code block also carries the SHA-256 of its own manuscript.  Consumers accept a block
only when both the current policy SHA and the body SHA match.  This prevents a current property
set or eyecatch from being paired with an older body after a regeneration/retry.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

CONTRACT_ID = "run195-auto-policy-fingerprint-v1"
LEGACY_READY_CAPTION = "AIIF_MANUSCRIPT:READY"
READY_CAPTION_PREFIX = "AIIF_MANUSCRIPT:READY|"
ROOT = Path(__file__).resolve().parent

# Keep this list deliberately limited to code that can materially change a persisted public
# article or its public eyecatch.  Operational/member-only changes must not invalidate every
# publishable article.  The repository-wide guard verifies that this manifest remains aligned
# with production_pipeline.py's installed layers.
PUBLICATION_POLICY_FILES = (
    "pipeline.py",
    "production_pipeline.py",
    "editorial_eyecatch.py",
    "decision_intelligence.py",
    "evidence_authority.py",
    "evidence_ledger.py",
    "subscription_attribution.py",
    "reader_value_review_bridge.py",
    "run208_reader_value_repair.py",
    "run172_production_reliability.py",
    "run173_operational_yield.py",
    "run174_monthly_digest_integrity.py",
    "run175_semantic_fact_precision.py",
    "run223_technical_claim_precision.py",
    "run176_scope_fidelity.py",
    "run177_paid_funnel_alignment.py",
    "run178_eyecatch_editorial_layout_optimizer.py",
    "run179_eyecatch_font_refinement.py",
    "run180_eyecatch_semantic_layout.py",
    "run181_eyecatch_visual_balance.py",
    "run182_eyecatch_conclusion_emphasis.py",
    "run183_eyecatch_emphasis_scale.py",
    "run222_note_presentation_integrity.py",
    "publication_contract.py",
    "run194_publication_contract.py",
)

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def manuscript_sha256(manuscript: str) -> str:
    return hashlib.sha256(str(manuscript or "").encode("utf-8")).hexdigest()


def policy_sha256(root: Path | None = None) -> str:
    base = root or ROOT
    digest = hashlib.sha256()
    for relative in PUBLICATION_POLICY_FILES:
        path = base / relative
        if not path.is_file():
            raise RuntimeError(f"publication policy file is missing: {relative}")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def current_ready_caption(manuscript: str, *, root: Path | None = None) -> str:
    return (
        f"{READY_CAPTION_PREFIX}contract={CONTRACT_ID}"
        f"|policy_sha256={policy_sha256(root)}"
        f"|manuscript_sha256={manuscript_sha256(manuscript)}"
    )


def _caption_fields(value: str) -> dict[str, str]:
    text = str(value or "").strip()
    if not text.startswith(READY_CAPTION_PREFIX):
        return {}
    fields: dict[str, str] = {}
    for token in text[len(READY_CAPTION_PREFIX):].split("|"):
        if "=" not in token:
            return {}
        key, val = token.split("=", 1)
        key, val = key.strip(), val.strip()
        if not key or key in fields:
            return {}
        fields[key] = val
    return fields


def is_current_ready_caption(value: str, *, root: Path | None = None) -> bool:
    """Validate policy provenance only; use is_current_ready_block for publication."""
    fields = _caption_fields(value)
    policy = fields.get("policy_sha256", "")
    manuscript = fields.get("manuscript_sha256", "")
    if fields.get("contract") != CONTRACT_ID or not _SHA_RE.fullmatch(policy) or not _SHA_RE.fullmatch(manuscript):
        return False
    try:
        return policy == policy_sha256(root)
    except RuntimeError:
        return False


def is_current_ready_block(manuscript: str, caption: str, *, root: Path | None = None) -> bool:
    fields = _caption_fields(caption)
    if not is_current_ready_caption(caption, root=root):
        return False
    return fields.get("manuscript_sha256") == manuscript_sha256(manuscript)


def is_exact_current_ready_block(
    stored_manuscript: str,
    caption: str,
    expected_manuscript: str,
    *,
    root: Path | None = None,
) -> bool:
    return (
        is_current_ready_block(stored_manuscript, caption, root=root)
        and manuscript_sha256(stored_manuscript) == manuscript_sha256(expected_manuscript)
    )


def is_ready_family_caption(value: str) -> bool:
    text = str(value or "").strip()
    return text == LEGACY_READY_CAPTION or text.startswith(READY_CAPTION_PREFIX)
