"""Zero-model admission guard for regeneration of an existing article identity.

Fresh candidate acquisition must not call this resolver: a new event is a new
article identity even when its Technology grouping is shared with published work.
"""
from __future__ import annotations

from typing import Callable


def automatic_regeneration_decision(
    sync_id: str,
    *,
    classifier: Callable[[str], str] | None = None,
    delivery_configured: Callable[[], bool] | None = None,
) -> tuple[bool, str]:
    """Allow only positively verified pre-publication delivery states.

    Missing delivery authority, malformed identity, unknown state and transport
    failures are not evidence that a published article is safe to regenerate.
    """
    if not isinstance(sync_id, str) or not sync_id.strip():
        return False, "missing_article_identity"
    if classifier is None or delivery_configured is None:
        try:
            import note_ready_sync
        except Exception:
            return False, "delivery_authority_unavailable"
        if classifier is None:
            classifier = note_ready_sync.classify_exact_delivery_state
        if delivery_configured is None:
            delivery_configured = lambda: bool(
                note_ready_sync.DEST_DATA_SOURCE_ID or note_ready_sync.DEST_DATABASE_ID
            )
    try:
        if not delivery_configured():
            return False, "delivery_authority_unavailable"
    except Exception:
        return False, "delivery_authority_unavailable"
    try:
        state = classifier(sync_id)
    except Exception:
        return False, "delivery_state_unavailable"
    if state in {"not_queued", "waiting"}:
        return True, state
    if not isinstance(state, str) or not state.strip():
        return False, "invalid_delivery_state"
    return False, f"delivery_state_{state}"
