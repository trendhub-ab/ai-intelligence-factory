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


def _normalize_exact_sync_id(value: str) -> str:
    sync_id = re.sub(r'[^0-9a-fA-F]', '', str(value or '')).lower()
    if len(sync_id) != 32:
        raise ValueError('sync_id must be exactly 32 hex characters')
    return sync_id


def _selected_name(prop: dict[str, Any] | None) -> str:
    return str((((prop or {}).get('select') or {}).get('name') or '')).strip()


def load_exact_existing_item(pipeline_module, sync_id: str) -> dict[str, Any] | None:
    """Rehydrate one Content Intelligence row by exact page id, never a recent-row scan."""
    sync_id = _normalize_exact_sync_id(sync_id)
    try:
        response = pipeline_module.requests.get(
            f'https://api.notion.com/v1/pages/{sync_id}',
            headers=pipeline_module._notion_headers(),
            timeout=10,
        )
    except Exception:
        return None
    if int(getattr(response, 'status_code', 0) or 0) != 200:
        return None

    page = response.json() or {}
    try:
        page_id = _normalize_exact_sync_id(str(page.get('id') or ''))
    except ValueError:
        return None
    if page_id != sync_id:
        return None
    props = page.get('properties') or {}

    plain = pipeline_module._notion_plain_text
    name = plain(props.get(pipeline_module.PROP_NAME, {})).strip()
    page_url = str((props.get(pipeline_module.PROP_URL, {}) or {}).get('url') or '').strip()
    if not name or not page_url:
        return None

    source = _selected_name(props.get(pipeline_module.PROP_SOURCE)) or 'HackerNews'
    summary = plain(props.get(pipeline_module.PROP_SOURCE_SUMMARY, {})).strip()
    engagement = (props.get(pipeline_module.PROP_ENGAGEMENT, {}) or {}).get('number') or 0
    screening_score = (props.get(pipeline_module.PROP_SCREENING_SCORE, {}) or {}).get('number')
    screening_reason = plain(props.get(pipeline_module.PROP_SCREENING_REASON, {})).strip()
    published = ((props.get(pipeline_module.PROP_PUBLISHED_AT, {}) or {}).get('date') or {}).get('start')
    license_text = plain(props.get(pipeline_module.PROP_LICENSE, {})).strip()

    repo = {
        'nameWithOwner': name,
        'description': summary or '既存記事のReady asset persistence recovery',
        'url': page_url,
        'stargazerCount': int(engagement or 0),
        'source': source,
        'publishedAt': published,
        'sourceContext': '',
        'sourceDetails': {'external_url': page_url},
        'licenseInfo': ({'spdxId': license_text} if source == 'GitHub' and license_text else None),
        'notion_page_id': sync_id,
    }
    return {
        'notion_page_id': sync_id,
        'screening_score': int(screening_score) if screening_score is not None else int(
            getattr(pipeline_module, 'NOTION_SAVE_THRESHOLD_SCORE', 60)
        ),
        'screening_reason': screening_reason or 'Ready asset persistence recovery',
        'repo': repo,
    }


def exact_page_is_ready(pipeline_module, sync_id: str) -> bool:
    """Prove that the exact source row is actually persisted as Ready after generation."""
    sync_id = _normalize_exact_sync_id(sync_id)
    try:
        response = pipeline_module.requests.get(
            f'https://api.notion.com/v1/pages/{sync_id}',
            headers=pipeline_module._notion_headers(),
            timeout=10,
        )
    except Exception:
        return False
    if int(getattr(response, 'status_code', 0) or 0) != 200:
        return False
    page = response.json() or {}
    try:
        if _normalize_exact_sync_id(str(page.get('id') or '')) != sync_id:
            return False
    except ValueError:
        return False
    props = page.get('properties') or {}
    return _selected_name(props.get(pipeline_module.PROP_ARTICLE_STATUS)) == str(
        pipeline_module.ARTICLE_STATUS_READY
    )


def run_exact_ready_asset_recovery(
    pipeline_module,
    sync_id: str,
    *,
    load_exact: Callable[[Any, str], dict[str, Any] | None] | None = None,
    regeneration_decision: Callable[[str], tuple[bool, str]] | None = None,
    verify_ready: Callable[[Any, str], bool] | None = None,
) -> dict[str, Any]:
    """Recover one pre-publication persistence failure through current Production only.

    The exact article identity is checked against delivery authority before any provider
    call. The candidate is loaded by direct Notion page GET, not a bounded recent-row
    scan. A truthy generated manuscript is never treated as success: the same page must
    be re-read and prove persisted Article Status=Ready before downstream delivery may run.
    """
    sync_id = _normalize_exact_sync_id(sync_id)
    decision = regeneration_decision or automatic_regeneration_decision
    allowed, reason = decision(sync_id)
    if not allowed:
        return {'status': 'blocked_terminal', 'sync_id': sync_id, 'reason': reason, 'ready': False}

    loader = load_exact or load_exact_existing_item
    item = loader(pipeline_module, sync_id)
    if not item:
        return {'status': 'exact_target_missing', 'sync_id': sync_id, 'ready': False}
    try:
        loaded_id = _normalize_exact_sync_id(str(item.get('notion_page_id') or ''))
    except ValueError:
        loaded_id = ''
    if loaded_id != sync_id:
        return {'status': 'exact_target_mismatch', 'sync_id': sync_id, 'ready': False}

    repo = dict(item.get('repo') or {})
    legal_gate = getattr(pipeline_module, 'legal_safety_gate', None)
    if callable(legal_gate):
        safe, license_status = legal_gate(repo)
        if not safe:
            return {
                'status': 'blocked_legal',
                'sync_id': sync_id,
                'reason': str(license_status or 'legal_safety_gate'),
                'ready': False,
            }

    pipeline_module.generate_intelligence_report(
        repo,
        notion_page_id=sync_id,
        screening_score=item.get('screening_score'),
        screening_reason=item.get('screening_reason', 'Ready asset persistence recovery'),
        candidate_rank=1,
        candidate_origin='ready_asset_recovery',
        persist_results=True,
    )

    verifier = verify_ready or exact_page_is_ready
    ready = bool(verifier(pipeline_module, sync_id))
    return {
        'status': 'ready_recovered' if ready else 'not_ready',
        'sync_id': sync_id,
        'ready': ready,
        'delivery_reason': reason,
    }


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
