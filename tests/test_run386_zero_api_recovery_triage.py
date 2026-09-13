from pathlib import Path

import run386_zero_api_recovery_triage as r386


def test_run367_audit_has_exactly_38_rows():
    rows = r386.parse_audit(Path("docs/RUN367_READONLY_AUDIT.md"))
    assert len(rows) == 38


def test_all_gate_failed_rows_are_current_reader_repair_reason_subset():
    rows = r386.parse_audit(Path("docs/RUN367_READONLY_AUDIT.md"))
    failed = [row for row in rows if row.classification == "gate_failed"]
    assert len(failed) == 32
    for row in failed:
        labels = r386.reader_labels(row.reason)
        assert labels
        assert labels <= r386.REPAIRABLE_READER_LABELS
        assert r386.classify(row).bucket == "reader_repair_candidate"


def test_non_reader_rows_remain_fail_closed_until_full_gate_proof():
    rows = r386.parse_audit(Path("docs/RUN367_READONLY_AUDIT.md"))
    triaged = r386.triage(rows)
    counts = r386.summarize(triaged)
    assert counts.get("reader_repair_candidate") == 32
    assert counts.get("full_gate_proof_required") == 1
    assert counts.get("manual_or_fact_repair_required", 0) == 0
    assert counts.get("unclassified", 0) == 0
    assert counts.get("official_source_migrated_full_gate_revalidation", 0) + counts.get("source_reground_required", 0) == 5


def test_unsupported_rows_never_become_reader_repair_candidates():
    rows = r386.parse_audit(Path("docs/RUN367_READONLY_AUDIT.md"))
    for row in rows:
        if row.classification == "unsupported":
            assert r386.classify(row).bucket in {
                "official_source_migrated_full_gate_revalidation",
                "source_reground_required",
            }
