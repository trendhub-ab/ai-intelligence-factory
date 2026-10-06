from pathlib import Path

path = Path("note_delivery_gcs.py")
text = path.read_text(encoding="utf-8")

import_marker = '''    revision_key,\n)\n\nGCS_LEDGER_ENVELOPE_SCHEMA_VERSION = "note-delivery-gcs-envelope-v1"\n'''
import_replacement = '''    revision_key,\n)\nfrom note_delivery_strong_zero import (\n    StrongZeroEvidenceError,\n    parse_strong_zero_evidence_category,\n)\n\nGCS_LEDGER_ENVELOPE_SCHEMA_VERSION = "note-delivery-gcs-envelope-v1"\n'''
if "from note_delivery_strong_zero import (" not in text:
    if import_marker not in text:
        raise SystemExit("strong-zero import marker not found")
    text = text.replace(import_marker, import_replacement, 1)

method_marker = '''    def _load_operation(\n        self, op_key: str\n'''
method = '''    def authorize_reconciled_retry(\n        self,\n        snapshot: DeliverySnapshot,\n        *,\n        run_correlation_id: str,\n        expected_version: int,\n    ) -> IntentDecision:\n        logical_key = logical_delivery_key(snapshot)\n        loaded = self._load_by_logical_key(logical_key)\n        if loaded is None:\n            raise InvalidStateTransition("delivery_not_found")\n        current, events, generation = loaded\n        if current.state_version != expected_version:\n            raise ConcurrentStateChange("state_version_mismatch")\n        if current.state != DeliveryState.MANUAL_RECONCILIATION_REQUIRED:\n            return IntentDecision(current, False, "manual_reconciliation_required")\n        if current.snapshot != snapshot:\n            return IntentDecision(current, False, "snapshot_mismatch")\n        if current.draft_id:\n            return IntentDecision(current, False, "stable_draft_present")\n        try:\n            evidence_digest = parse_strong_zero_evidence_category(\n                current.conflict_category or ""\n            )\n        except StrongZeroEvidenceError:\n            return IntentDecision(current, False, "strong_zero_evidence_invalid")\n\n        next_version = current.state_version + 1\n        now = _utc_now()\n        expires = (\n            datetime.now(timezone.utc) + timedelta(minutes=5)\n        ).isoformat().replace("+00:00", "Z")\n        retry_run = _normalized_text(run_correlation_id)\n        updated = replace(\n            current,\n            state=DeliveryState.CREATE_INTENT_RECORDED,\n            state_version=next_version,\n            attempt_count=current.attempt_count + 1,\n            owner_correlation_id=retry_run,\n            owner_expires_at=expires,\n            updated_at=now,\n        )\n        next_events = list(events)\n        next_events.append(\n            _event(\n                prior_state=DeliveryState.MANUAL_RECONCILIATION_REQUIRED,\n                new_state=DeliveryState.CREATE_INTENT_RECORDED,\n                category=f"strong_zero_retry_authorized:{evidence_digest}",\n                run_correlation_id=retry_run,\n                state_version=next_version,\n                created_at=now,\n            )\n        )\n        self._write(\n            current.logical_key,\n            updated,\n            next_events,\n            expected_generation=generation,\n        )\n        return IntentDecision(updated, True, "reconciled_retry_authorized")\n\n    def _load_operation(\n        self, op_key: str\n'''
if "    def authorize_reconciled_retry(" not in text:
    if method_marker not in text:
        raise SystemExit("GCS method insertion marker not found")
    text = text.replace(method_marker, method, 1)

path.write_text(text, encoding="utf-8")
