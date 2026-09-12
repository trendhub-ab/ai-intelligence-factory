"""Self-contained writer recovery snapshots; no provider or business I/O.

Hashes detect changed saved material, not factual truth or authentic provenance.
Restore additionally recomputes the Fact binding and Writer prompt from the durable
input + Fact-Locked Plan, so a self-consistent but internally mismatched snapshot cannot
resume. Legacy pending rows require their original fixture and cannot use standalone restore.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


class WriterPackageError(RuntimeError):
    pass


def package_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def snapshot_fixture(fixture: dict) -> dict:
    # JSON round trip prevents the caller mutating a retained nested object.
    value = json.loads(json.dumps(fixture, ensure_ascii=False, allow_nan=False))
    if value.get('business_writes') != 0 or value.get('persist_results') is not False:
        raise WriterPackageError('writer_package_not_read_only')
    return {'version': 1, 'fixture': value, 'sha256': package_hash(value)}


def validate_snapshot(snapshot: dict) -> dict:
    if not isinstance(snapshot, dict) or snapshot.get('version') != 1:
        raise WriterPackageError('writer_package_version_invalid')
    fixture = snapshot.get('fixture')
    if not isinstance(fixture, dict) or snapshot.get('sha256') != package_hash(fixture):
        raise WriterPackageError('writer_package_hash_mismatch')
    snapshot_fixture(fixture)
    return fixture


def _validate_handoff_binding(fixture: dict) -> tuple[dict, dict]:
    """Recompute immutable Evidence + prompt binding from durable package material."""
    from hybrid_gemini_writer import build_gemini_writer_prompt
    from hybrid_groq_plan import validate_hybrid_plan_text

    package = fixture.get('decision_package')
    if not isinstance(package, dict) or package.get('version') != 1:
        raise WriterPackageError('writer_decision_package_missing')
    item, report = package.get('input'), package.get('plan_report')
    if not isinstance(item, dict) or not isinstance(report, dict):
        raise WriterPackageError('writer_handoff_material_missing')
    candidate_id = str(fixture.get('candidate_id') or '')
    if not candidate_id or item.get('candidate_id') != candidate_id:
        raise WriterPackageError('writer_package_input_mismatch')
    if report.get('candidate_id', candidate_id) != candidate_id:
        raise WriterPackageError('writer_package_plan_candidate_mismatch')
    if report.get('mode') != 'hybrid_groq_judgment_fact_locked':
        raise WriterPackageError('writer_package_fact_locked_plan_required')
    if report.get('status') != 'PLAN_VALIDATED' or report.get('semantic_plan_validated') is not True:
        raise WriterPackageError('writer_package_plan_rejected')

    source_context = str(item.get('source_context') or '').strip()
    if not source_context:
        raise WriterPackageError('writer_package_source_context_missing')
    evidence_hash = hashlib.sha256(source_context.encode('utf-8')).hexdigest()
    if report.get('fact_envelope_sha256') != evidence_hash:
        raise WriterPackageError('writer_package_fact_hash_mismatch')

    raw_plan = report.get('composed_plan')
    if not isinstance(raw_plan, dict):
        raise WriterPackageError('writer_package_composed_plan_missing')
    try:
        plan = validate_hybrid_plan_text(json.dumps(raw_plan, ensure_ascii=False))
    except Exception:
        raise WriterPackageError('writer_package_composed_plan_invalid') from None
    expected_prompt = build_gemini_writer_prompt(item, plan)
    if fixture.get('writer_prompt') != expected_prompt:
        raise WriterPackageError('writer_package_prompt_mismatch')
    return item, report


def restore_pending_package(record: dict, output_dir: str) -> dict[str, str]:
    """Restore only fixed filenames in a caller-owned directory; never call models.

    Eligibility (cooldown, TTL, attempts) is checked by the existing runtime immediately
    before sending. Restoring material alone does not grant permission to publish.
    """
    from hybrid_writer_deferred import validate_pending_writer_record, _stable_payload_hash
    from hybrid_groq_plan import load_hybrid_plan_report
    from groq_article_parity import load_input
    validate_pending_writer_record(record, allow_not_ready=True)
    fixture = validate_snapshot(record.get('writer_snapshot'))
    if fixture.get('candidate_id') != record.get('candidate_id'):
        raise WriterPackageError('writer_package_candidate_mismatch')
    if _stable_payload_hash(fixture) != record.get('payload_hash'):
        raise WriterPackageError('writer_package_payload_mismatch')
    item, plan_report = _validate_handoff_binding(fixture)

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    paths = {key: str(directory / name) for key, name in (
        ('fixture', 'writer-fixture.json'), ('input', 'writer-input.json'),
        ('plan_report', 'writer-plan-report.json'))}
    # Refuse overwrites so an unrelated run's material cannot be replaced.
    if any(Path(path).exists() for path in paths.values()):
        raise WriterPackageError('writer_package_restore_target_exists')
    for key, value in [('input', item), ('plan_report', plan_report)]:
        with Path(paths[key]).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
    load_input(paths['input'])
    # Recovery must use the same canonical Fact-Locked contract as the normal Writer handoff.
    load_hybrid_plan_report(paths['plan_report'])
    with Path(paths['fixture']).open('x', encoding='utf-8') as stream:
        json.dump(fixture, stream, ensure_ascii=False, indent=2)
    return paths
