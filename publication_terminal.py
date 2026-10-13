"""Fail-closed publication terminal authority for automatic regeneration lanes.

This module is intentionally zero-provider. It answers only whether an existing article
identity is proven to remain pre-publication. Automatic regeneration is allowed only when
its durable note-delivery state is explicitly ``not_queued`` or ``waiting``.
"""
from __future__ import annotations

from collections.abc import Callable

_PREPUBLICATION_STATES = frozenset({"not_queued", "waiting"})
_KNOWN_BLOCKED_STATES = frozenset({"already_delivered", "human_blocked"})


def automatic_regeneration_decision(
    sync_id: str,
    *,
    classifier: Callable[[str], str] | None = None,
    delivery_configured: Callable[[], bool] | None = None,
) -> tuple[bool, str]:
    """Return whether automatic regeneration is allowed for one existing article.

    Missing delivery authority, unreadable/ambiguous delivery state, and every state other
    than the two explicit pre-publication states fail closed. The default classifier is the
    exact durable note-delivery classifier and is imported lazily so lightweight/offline
    surfaces do not acquire note synchronization dependencies unless they use this guard.
    """
    if classifier is None or delivery_configured is None:
        try:
            import note_ready_sync as ready_sync
        except Exception:
            return False, "delivery_authority_unavailable"
        if classifier is None:
            classifier = ready_sync.classify_exact_delivery_state
        if delivery_configured is None:
            delivery_configured = lambda: bool(
                ready_sync.DEST_DATA_SOURCE_ID or ready_sync.DEST_DATABASE_ID
            )

    try:
        configured = bool(delivery_configured())
    except Exception:
        return False, "delivery_authority_unavailable"
    if not configured:
        return False, "delivery_authority_unavailable"

    try:
        state = str(classifier(str(sync_id or "")) or "").strip()
    except Exception:
        return False, "delivery_state_unavailable"

    if state in _PREPUBLICATION_STATES:
        return True, state
    if state in _KNOWN_BLOCKED_STATES:
        return False, state
    return False, "delivery_state_invalid"
