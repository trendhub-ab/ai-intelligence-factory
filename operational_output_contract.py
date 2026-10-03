"""P0-C public receipts: discard arbitrary payloads, never redact-and-forward them."""
from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any

ENUMS = {
    'component': {'product_review', 'daily', 'regression', 'inventory_bootstrap', 'note_failure'},
    'status': {'success', 'failure', 'deferred', 'skipped', 'unknown', 'cancelled'},
    'model_class': {'upper_flash', 'unknown'},
    'error_category': {'none', 'timeout', 'provider_unavailable', 'child_failed', 'invalid_result', 'diagnostic_unavailable', 'safety_violation'},
}
COUNTS = {'allowlist_count', 'request_count', 'request_budget', 'max_reviews', 'failure_count', 'count',
          'internal_updated', 'subscriber_updated', 'subscriber_preserved', 'eligible_records'}


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
