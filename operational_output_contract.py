"""Operational safety contracts for public receipts and existing-article admission."""
from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any, Callable

ENUMS = {
    'component': {'product_review', 'daily', 'regression', 'inventory_bootstrap', 'note_failure'},
    'status': {'success', 'failure', 'deferred', 'skipped', 'unknown', 'cancelled'},
    'model_class': {'upper_flash', 'unknown'},
    'error_category': {'none', 'timeout', 'provider_unavailable', 'child_failed', 'invalid_result', 'diagnostic_unavailable', 'safety_violation'},
}
COUNTS = {'allowlist_count', 'request_count', 'request_budget', 'max_reviews', 'failure_count', 'count',
          'internal_updated', 'subscriber_updated', 'subscriber_preserved', 'eligible_records'}


def automatic_regeneration_decision(
    sync_id: str,
    *,
    classifier: Callable[[str], str] | None = None,
    delivery_configured: Callable[[], bool] | None = None,
) -> tuple[bool, str]:
    """Allow automatic regeneration only for positively verified pre-publication state.

    This is intentionally fail-closed. Missing delivery authority, unreadable/ambiguous
    state, and delivery/human-blocked states are not evidence that an existing article is
    safe to regenerate. Fresh candidate acquisition must not use this contract.
    """
    if not isinstance(sync_id, str) or not sync_id.strip():
        return False, 'missing_article_identity'

    if classifier is None or delivery_configured is None:
        try:
            import note_ready_sync
        except Exception:
            return False, 'delivery_authority_unavailable'
        if classifier is None:
            classifier = note_ready_sync.classify_exact_delivery_state
        if delivery_configured is None:
            delivery_configured = lambda: bool(
                note_ready_sync.DEST_DATA_SOURCE_ID or note_ready_sync.DEST_DATABASE_ID
            )

    try:
        if not delivery_configured():
            return False, 'delivery_authority_unavailable'
    except Exception:
        return False, 'delivery_authority_unavailable'

    try:
        state = classifier(sync_id)
    except Exception:
        return False, 'delivery_state_unavailable'

    if state in {'not_queued', 'waiting'}:
        return True, state
    if not isinstance(state, str) or not state.strip():
        return False, 'invalid_delivery_state'
    return False, f'delivery_state_{state}'


def safe_operational_projection(data: dict[str, Any]) -> dict[str, Any]:
    """Only exact scalar types and fixed enums cross the public boundary."""
    out: dict[str, Any] = {}
    for key, allowed in ENUMS.items():
        value = data.get(key)
        if type(value) is str and value in allowed:
            out[key] = value
    for key in COUNTS:
        value = data.get(key)
        if type(value) is int and 0 <= value <= 1_000_000_000:
            out[key] = value
    value = data.get('run_id')
    if type(value) is str and re.fullmatch(r'[0-9]{1,20}', value):
        out['run_id'] = value
    # Unknown is honest when the child dies before its aggregate budget summary.
    if data.get('request_count') is None:
        out['request_count'] = None
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--component', choices=sorted(ENUMS['component']), required=True)
    parser.add_argument('--status', choices=sorted(ENUMS['status']), default='unknown')
    args = parser.parse_args()
    print(json.dumps(safe_operational_projection({
        'component': args.component, 'status': args.status,
        'run_id': os.environ.get('GITHUB_RUN_ID'),
        'error_category': 'none' if args.status == 'success' else 'diagnostic_unavailable',
    }), sort_keys=True))
