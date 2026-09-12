"""Self-contained writer recovery snapshots; no provider or business I/O.

Hashes detect changed saved material, not factual truth or authentic provenance.
Legacy pending rows require their original fixture and cannot use standalone restore.
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


def restore_pending_package(record: dict, output_dir: str) -> dict[str, str]:
    """Restore only fixed filenames in a caller-owned directory; never call models.

    Eligibility (cooldown, TTL, attempts) is checked by the existing runtime immediately
    before sending. Restoring material alone does not grant permission to publish.
    """
    from hybrid_writer_deferred import validate_pending_writer_record, _stable_payload_hash
    from groq_two_pass_article import load_plan_report
    from groq_article_parity import load_input
    validate_pending_writer_record(record, allow_not_ready=True)
    fixture = validate_snapshot(record.get('writer_snapshot'))
    if fixture.get('candidate_id') != record.get('candidate_id'):
        raise WriterPackageError('writer_package_candidate_mismatch')
    if _stable_payload_hash(fixture) != record.get('payload_hash'):
        raise WriterPackageError('writer_package_payload_mismatch')
    package = fixture.get('decision_package')
    if not isinstance(package, dict) or package.get('version') != 1:
        raise WriterPackageError('writer_decision_package_missing')
    item, plan_report = package.get('input'), package.get('plan_report')
    if not isinstance(item, dict) or item.get('candidate_id') != record['candidate_id']:
        raise WriterPackageError('writer_package_input_mismatch')
    if not isinstance(plan_report, dict):
        raise WriterPackageError('writer_package_plan_missing')
    if plan_report.get('candidate_id', record['candidate_id']) != record['candidate_id']:
        raise WriterPackageError('writer_package_plan_candidate_mismatch')
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
    load_plan_report(paths['plan_report'])
    with Path(paths['fixture']).open('x', encoding='utf-8') as stream:
        json.dump(fixture, stream, ensure_ascii=False, indent=2)
    return paths
