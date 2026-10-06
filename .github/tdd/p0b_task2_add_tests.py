from pathlib import Path

path = Path("tests/test_note_delivery_gcs.py")
text = path.read_text(encoding="utf-8")
marker = "# TASK2_STRONG_ZERO_GCS_RETRY_AUTHORITY_TESTS\n"
if marker not in text:
    text += r'''

# TASK2_STRONG_ZERO_GCS_RETRY_AUTHORITY_TESTS
_GCS_STRONG_ZERO_DIGEST = "b" * 64
_GCS_STRONG_ZERO_EVIDENCE = (
    "creation_absence_confirmed_strong_zero:" + _GCS_STRONG_ZERO_DIGEST
)


def _prepare_gcs_manual_reconciliation(
    ledger: GCSDeliveryLedger,
    snapshot=None,
    *,
    evidence: str = _GCS_STRONG_ZERO_EVIDENCE,
    with_draft: bool = False,
):
    snapshot = snapshot or _snapshot()
    first = ledger.begin_or_load(snapshot, run_correlation_id="run-original")
    if with_draft:
        current = ledger.record_draft_created(
            first.record.operation_key,
            draft_id="opaque-existing-draft",
            note_host="note.com",
            expected_version=first.record.state_version,
        )
    else:
        current = ledger.record_blocked(
            first.record.operation_key,
            state=DeliveryState.CREATION_UNKNOWN,
            category="creation_result_ambiguous",
            expected_version=first.record.state_version,
        )
    manual = ledger.record_blocked(
        current.operation_key,
        state=DeliveryState.MANUAL_RECONCILIATION_REQUIRED,
        category=evidence,
        expected_version=current.state_version,
    )
    return snapshot, manual


def test_gcs_reconciled_retry_uses_observed_generation_and_preserves_history():
    client = FakeClient()
    ledger = _ledger(client)
    snapshot, manual = _prepare_gcs_manual_reconciliation(ledger)

    decision = ledger.authorize_reconciled_retry(
        snapshot,
        run_correlation_id="run-retry",
        expected_version=manual.state_version,
    )

    assert decision.creation_authorized is True
    assert decision.reason == "reconciled_retry_authorized"
    assert decision.record.state == DeliveryState.CREATE_INTENT_RECORDED
    assert decision.record.state_version == manual.state_version + 1
    assert decision.record.attempt_count == manual.attempt_count + 1
    assert decision.record.owner_correlation_id == "run-retry"
    assert decision.record.owner_expires_at
    assert decision.record.snapshot == manual.snapshot == snapshot
    assert decision.record.draft_id is None
    assert decision.record.conflict_category == _GCS_STRONG_ZERO_EVIDENCE
    assert client.bucket_obj.upload_conditions[-1] == 3
    assert all(condition is not None for condition in client.bucket_obj.upload_conditions)

    name = record_object_name(manual.logical_key)
    envelope = json.loads(client.bucket_obj.store[name][1])
    assert [event["category"] for event in envelope["events"]] == [
        "create_intent_recorded",
        "creation_result_ambiguous",
        _GCS_STRONG_ZERO_EVIDENCE,
        "strong_zero_retry_authorized:" + _GCS_STRONG_ZERO_DIGEST,
    ]
    assert envelope["events"][-1]["run_correlation_id"] == "run-retry"


def test_gcs_reconciled_retry_rejects_malformed_evidence_without_write():
    client = FakeClient()
    ledger = _ledger(client)
    snapshot, manual = _prepare_gcs_manual_reconciliation(
        ledger,
        evidence="creation_absence_confirmed_strong_zero:BAD",
    )
    before_conditions = list(client.bucket_obj.upload_conditions)

    decision = ledger.authorize_reconciled_retry(
        snapshot,
        run_correlation_id="run-retry",
        expected_version=manual.state_version,
    )

    assert decision.creation_authorized is False
    assert decision.reason == "strong_zero_evidence_invalid"
    assert decision.record.state == DeliveryState.MANUAL_RECONCILIATION_REQUIRED
    assert client.bucket_obj.upload_conditions == before_conditions


def test_gcs_reconciled_retry_rejects_snapshot_drift_without_write():
    client = FakeClient()
    ledger = _ledger(client)
    _snapshot_before, manual = _prepare_gcs_manual_reconciliation(ledger)
    drifted = _snapshot(manuscript_sha256="9" * 64)
    before_conditions = list(client.bucket_obj.upload_conditions)

    decision = ledger.authorize_reconciled_retry(
        drifted,
        run_correlation_id="run-retry",
        expected_version=manual.state_version,
    )

    assert decision.creation_authorized is False
    assert decision.reason == "snapshot_mismatch"
    assert client.bucket_obj.upload_conditions == before_conditions


def test_gcs_reconciled_retry_rejects_existing_draft_identity_without_write():
    client = FakeClient()
    ledger = _ledger(client)
    snapshot, manual = _prepare_gcs_manual_reconciliation(ledger, with_draft=True)
    assert manual.draft_id == "opaque-existing-draft"
    before_conditions = list(client.bucket_obj.upload_conditions)

    decision = ledger.authorize_reconciled_retry(
        snapshot,
        run_correlation_id="run-retry",
        expected_version=manual.state_version,
    )

    assert decision.creation_authorized is False
    assert decision.reason == "stable_draft_present"
    assert client.bucket_obj.upload_conditions == before_conditions


def test_gcs_reconciled_retry_rejects_wrong_state_without_write():
    client = FakeClient()
    ledger = _ledger(client)
    snapshot = _snapshot()
    first = ledger.begin_or_load(snapshot, run_correlation_id="run-original")
    before_conditions = list(client.bucket_obj.upload_conditions)

    decision = ledger.authorize_reconciled_retry(
        snapshot,
        run_correlation_id="run-retry",
        expected_version=first.record.state_version,
    )

    assert decision.creation_authorized is False
    assert decision.reason == "manual_reconciliation_required"
    assert client.bucket_obj.upload_conditions == before_conditions


def test_gcs_reconciled_retry_rejects_stale_state_version_without_write():
    client = FakeClient()
    ledger = _ledger(client)
    snapshot, manual = _prepare_gcs_manual_reconciliation(ledger)
    before_conditions = list(client.bucket_obj.upload_conditions)

    with pytest.raises(ConcurrentStateChange, match="state_version_mismatch"):
        ledger.authorize_reconciled_retry(
            snapshot,
            run_correlation_id="run-retry",
            expected_version=manual.state_version - 1,
        )

    assert client.bucket_obj.upload_conditions == before_conditions


def test_gcs_reconciled_retry_stale_generation_fails_without_unconditional_overwrite():
    client = FakeClient()
    ledger = _ledger(client)
    snapshot, manual = _prepare_gcs_manual_reconciliation(ledger)
    client.bucket_obj.fail_next_precondition = True

    with pytest.raises(ConcurrentStateChange, match="state_generation_mismatch"):
        ledger.authorize_reconciled_retry(
            snapshot,
            run_correlation_id="run-retry",
            expected_version=manual.state_version,
        )

    assert client.bucket_obj.upload_conditions[-1] == 3
    assert all(condition is not None for condition in client.bucket_obj.upload_conditions)
    current = ledger.get_active_by_logical_key(manual.logical_key)
    assert current is not None
    assert current.state == DeliveryState.MANUAL_RECONCILIATION_REQUIRED
    name = record_object_name(manual.logical_key)
    envelope = json.loads(client.bucket_obj.store[name][1])
    assert not any(
        event["category"].startswith("strong_zero_retry_authorized:")
        for event in envelope["events"]
    )


def test_gcs_reconciled_retry_concurrent_callers_have_exactly_one_cas_winner():
    client = FakeClient()
    preparing = _ledger(client)
    snapshot, manual = _prepare_gcs_manual_reconciliation(preparing)
    first = _ledger(client)
    second = _ledger(client)
    barrier = threading.Barrier(2)

    def synchronize_load(ledger):
        original = ledger._load_by_logical_key

        def load(logical_key):
            loaded = original(logical_key)
            if loaded is not None and loaded[0].state == DeliveryState.MANUAL_RECONCILIATION_REQUIRED:
                barrier.wait(timeout=5)
            return loaded

        ledger._load_by_logical_key = load

    synchronize_load(first)
    synchronize_load(second)
    decisions = []
    errors = []

    def worker(ledger, run_id):
        try:
            decisions.append(
                ledger.authorize_reconciled_retry(
                    snapshot,
                    run_correlation_id=run_id,
                    expected_version=manual.state_version,
                )
            )
        except Exception as exc:
            errors.append(exc)

    a = threading.Thread(target=worker, args=(first, "run-retry-a"))
    b = threading.Thread(target=worker, args=(second, "run-retry-b"))
    a.start()
    b.start()
    a.join()
    b.join()

    assert len(decisions) == 1
    assert decisions[0].creation_authorized is True
    assert len(errors) == 1
    assert isinstance(errors[0], ConcurrentStateChange)
    assert str(errors[0]) == "state_generation_mismatch"
    name = record_object_name(manual.logical_key)
    envelope = json.loads(client.bucket_obj.store[name][1])
    retry_events = [
        event
        for event in envelope["events"]
        if event["category"].startswith("strong_zero_retry_authorized:")
    ]
    assert len(retry_events) == 1
    assert all(condition is not None for condition in client.bucket_obj.upload_conditions)
'''
path.write_text(text, encoding="utf-8")
