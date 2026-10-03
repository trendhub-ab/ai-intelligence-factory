"""Production boundary tests; all service calls replaced before entrypoint execution."""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
import re
import textwrap
import daily_portfolio_review as dpr

ROOT = Path(__file__).resolve().parents[1]
SENTINELS = [f'P0C_{kind}_SENSITIVE' for kind in ('PAID_ID', 'CANONICAL_ID', 'MANUSCRIPT', 'EVIDENCE', 'CUSTOMER', 'SECRET')]
RAW = '\n'.join(SENTINELS)
DIRECTORIES = ('review_candidates', 'quality_failures', 'gate_history', 'article_audit', 'regression_cases_pending', 'regen_test_outputs')


def configure_main(monkeypatch):
    monkeypatch.setattr(dpr.decision_intelligence, 'ENABLE_DECISION_INTELLIGENCE_DB', True)
    monkeypatch.setattr(dpr.context_first_enrichment, 'preflight_context_first_schema', lambda: None)
    monkeypatch.setattr(dpr.decision_intelligence, 'query_technology_records', lambda **kw: [])
    monkeypatch.setattr(dpr, 'plan_daily_review_allowlist', lambda *a, **kw: list(SENTINELS))
    monkeypatch.setattr(dpr.context_first_enrichment, 'enrich_context_first', lambda *a: {'internal_updated': 2, 'detail': RAW})


@pytest.mark.parametrize('case', ['success', 'timeout', 'provider_failure', 'child_exception', 'malformed_result'])
def test_child_public_sinks_contain_no_sensitive_payload(case, monkeypatch, capsys, tmp_path):
    configure_main(monkeypatch)
    summary = tmp_path / 'summary'
    summary.write_text('')
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))
    monkeypatch.setenv('GITHUB_RUN_ID', '12345')
    output = '[PRODUCT REVIEW] observed\nProduct Review Gemini Requests Used: 2/3 (review=2)\n' + RAW
    proc = SimpleNamespace(returncode=0, stdout=output, stderr=RAW)
    effects = {'timeout': subprocess.TimeoutExpired('child', 1, output=output.encode(), stderr=RAW.encode()),
               'provider_failure': SimpleNamespace(returncode=1, stdout=output, stderr='503 provider unavailable\n' + RAW),
               'child_exception': OSError(RAW), 'malformed_result': SimpleNamespace(returncode=0, stdout=RAW, stderr=RAW)}
    effect = effects.get(case, proc)
    def run(*args, **kwargs):
        assert kwargs['capture_output'] is True
        assert kwargs['env']['INVENTORY_BOOTSTRAP_ENTITY_IDS'] == ','.join(SENTINELS)
        if isinstance(effect, Exception):
            raise effect
        return effect
    monkeypatch.setattr(dpr.subprocess, 'run', run)
    try:
        code = dpr.main()
    except Exception as exc:
        # Even callers rendering the exception must never expose raw details.
        print(str(exc))
        code = 1
    captured = capsys.readouterr()
    public = captured.out + captured.err + summary.read_text()
    assert not any(s in public for s in SENTINELS)
    receipt = json.loads(captured.out.strip().splitlines()[-1])
    assert receipt['component'] == 'product_review'
    assert receipt['request_budget'] == dpr.DEFAULT_REQUEST_BUDGET
    assert receipt['allowlist_count'] == len(SENTINELS)
    assert 'request_count' in receipt and 'model_class' in receipt
    assert receipt['status'] in {'success', 'failure', 'deferred'}
    assert 'error_category' in receipt
    assert code == (0 if case in {'success', 'timeout'} else 1)


def test_main_does_not_publish_arbitrary_result_or_dependency_output(monkeypatch, capsys):
    configure_main(monkeypatch)
    monkeypatch.setattr(dpr, '_run_product_only', lambda *a: {'skipped': False, 'ordered_allowlist': SENTINELS, 'detail': RAW, 'request_budget': 3})
    def enrich(*a):
        print('::error::' + RAW)
        return {'detail': RAW, 'internal_updated': 2}
    monkeypatch.setattr(dpr.context_first_enrichment, 'enrich_context_first', enrich)
    assert dpr.main() == 0
    captured = capsys.readouterr()
    assert not any(s in captured.out + captured.err for s in SENTINELS)
    assert 'ordered_allowlist' not in captured.out


def workflow_steps(workflow):
    # Match actual step blocks; unlike a substring assertion this examines upload
    # path selections, including multiline globs. No new CI parser dependency.
    return re.split(r"(?m)^      - ", workflow.read_text())[1:]


def upload_paths(workflow):
    paths = []
    for step in workflow_steps(workflow):
        if not re.search(r"uses: actions/upload-artifact@", step):
            continue
        match = re.search(r"(?m)^          path: (.*)$", step)
        assert match, "Every upload must have an explicit path"
        value = match.group(1)
        if value in {"|", ">"}:
            value = "\n".join(re.findall(r"(?m)^            (.+)$", step[match.end():]))
        paths.append(value)
    return paths


@pytest.mark.parametrize('workflow', ['daily-one-shot.yml', 'daily.yml', 'regression-test.yml'])
def test_raw_fixture_directories_are_not_selected_by_artifact_upload(workflow, tmp_path):
    for directory in DIRECTORIES:
        folder = tmp_path / directory
        folder.mkdir()
        (folder / 'sensitive.txt').write_text(RAW)
    selected = []
    for pattern in upload_paths(ROOT / '.github/workflows' / workflow):
        for line in pattern.splitlines():
            if not line.strip() or line.startswith('!'):
                continue
            for match in tmp_path.glob(line.strip().rstrip('/')):
                selected.extend(match.rglob('*') if match.is_dir() else [match])
    assert not any(p.is_file() and any(s in p.read_text() for s in SENTINELS) for p in selected)


def test_failure_screenshot_has_no_artifact_route():
    workflow = ROOT / '.github/workflows/note-failure-snapshot.yml'
    assert not upload_paths(workflow)
    text = workflow.read_text()
    assert 'failure_count' in text and 'GITHUB_RUN_ID' in text
    assert 'diagnostic_unavailable' in text


def test_projection_rejects_sensitive_values_in_safe_named_fields():
    # Delayed import makes missing contract an assertion RED, not a collection error.
    import importlib.util
    assert importlib.util.find_spec('operational_output_contract') is not None
    from operational_output_contract import safe_operational_projection
    data = {key: RAW for key in ('status', 'run_id', 'component', 'request_count', 'request_budget', 'model_class', 'error_category', 'correlation_id')}
    data.update(ordered_allowlist=SENTINELS, arbitrary={'detail': RAW})
    projected = safe_operational_projection(data)
    assert not any(s in json.dumps(projected) for s in SENTINELS)
    assert 'ordered_allowlist' not in projected


def test_bootstrap_apply_public_json_does_not_include_ordered_allowlist(monkeypatch, capsys, tmp_path):
    import inventory_bootstrap as ib
    monkeypatch.setenv('NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID', 'synthetic')
    monkeypatch.setattr(ib, 'NotionClient', lambda *a: SimpleNamespace(query_data_source=lambda *a: []))
    monkeypatch.setattr(ib, 'subscriber_visible_count', lambda *a: 0)
    readiness = dict(sellable_count=0, inventory_ready=False, launch_ready=False, launch_blockers=[])
    monkeypatch.setattr(ib, 'evaluate_readiness', lambda *a, **kw: readiness)
    monkeypatch.setattr(ib, 'plan_candidates', lambda *a, **kw: [SimpleNamespace(canonical_entity_id=SENTINELS[0])])
    monkeypatch.setattr(ib, 'ARTIFACT_DIR', tmp_path)
    monkeypatch.setattr(ib.subprocess, 'run', lambda *a, **kw: SimpleNamespace(returncode=0, stdout='[PRODUCT REVIEW] observed', stderr=''))
    args = SimpleNamespace(confirm=ib.CONFIRM_TEXT, pipeline=str(ROOT/'production_pipeline.py'), target=2, min_sellable=1, max_reviews=1, product_request_budget=3, timeout=2)
    data = ib.run_apply(args)
    assert data['ordered_allowlist'] == [SENTINELS[0]]
    captured = capsys.readouterr()
    assert SENTINELS[0] not in captured.out + captured.err
    for path in tmp_path.glob('*.json'):
        assert SENTINELS[0] not in path.read_text()


def test_child_cannot_bypass_capture_via_actions_environment(monkeypatch):
    for key in ('GITHUB_STEP_SUMMARY', 'GITHUB_OUTPUT', 'GITHUB_ENV'):
        monkeypatch.setenv(key, '/synthetic/public-sink')
    def run(*a, **kw):
        assert not any(key in kw['env'] for key in ('GITHUB_STEP_SUMMARY', 'GITHUB_OUTPUT', 'GITHUB_ENV'))
        return SimpleNamespace(returncode=0, stdout='[PRODUCT REVIEW] observed', stderr='')
    monkeypatch.setattr(dpr.subprocess, 'run', run)
    dpr._run_product_only(['synthetic'], 1, 3)


def test_child_malformed_shape_raises_only_safe_category(monkeypatch):
    monkeypatch.setattr(dpr.subprocess, 'run', lambda *a, **kw: {'detail': RAW})
    with pytest.raises(RuntimeError, match='^invalid_result$'):
        dpr._run_product_only(SENTINELS, 1, 3)


def test_zero_budget_observability_is_exact(monkeypatch, capsys):
    configure_main(monkeypatch)
    monkeypatch.setattr(dpr, 'DEFAULT_REQUEST_BUDGET', 0)
    monkeypatch.setattr(dpr.subprocess, 'run', lambda *a, **kw: pytest.fail('must not spawn'))
    assert dpr.main() == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['request_count'] == 0
    assert receipt['status'] == 'skipped'


def test_bootstrap_raw_child_capture_is_not_uploaded():
    assert not upload_paths(ROOT / '.github/workflows/inventory-bootstrap.yml')


def test_snapshot_fixture_is_discarded_without_public_bytes(monkeypatch, tmp_path):
    workflow = ROOT / '.github/workflows/note-failure-snapshot.yml'
    text = workflow.read_text().split('  collect-snapshot:', 1)[1].split('  stop-cloud-vm:', 1)[0]
    assert not upload_paths(workflow)
    script = textwrap.dedent(text.split('        run: |\n', 1)[1])
    source = tmp_path / '.runtime/note_draft/failure.png'
    source.parent.mkdir(parents=True)
    # A real PNG with sensitive text metadata and image pixels.
    from PIL import Image, PngImagePlugin
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('manuscript', RAW)
    Image.new('RGB', (20, 20)).save(source, pnginfo=metadata)
    import os
    env = dict(os.environ, GITHUB_WORKSPACE=str(tmp_path), RUNNER_TEMP=str(tmp_path), GITHUB_RUN_ID='123')
    proc = subprocess.run(['bash', '-c', script], env=env, capture_output=True, text=True)
    assert proc.returncode == 0
    assert not source.exists()
    receipt = json.loads(proc.stdout)
    assert receipt['failure_count'] == 1 and receipt['run_id'] == '123'
    assert not any(s in proc.stdout + proc.stderr for s in SENTINELS)


def test_bootstrap_exception_is_safe(monkeypatch, capsys):
    import inventory_bootstrap as ib
    monkeypatch.setattr(ib, 'build_parser', lambda: SimpleNamespace(parse_args=lambda: SimpleNamespace(command='apply')))
    monkeypatch.setattr(ib, 'run_apply', mock.Mock(side_effect=RuntimeError(RAW)))
    assert ib.main() == 2
    captured = capsys.readouterr()
    assert not any(s in captured.out + captured.err for s in SENTINELS)
    assert 'diagnostic_unavailable' in captured.out + captured.err


def test_cancelled_workflow_emits_safe_receipt():
    import sys
    proc = subprocess.run([sys.executable, str(ROOT/'operational_output_contract.py'), '--component', 'daily', '--status', 'cancelled'], capture_output=True, text=True)
    assert proc.returncode == 0
    assert json.loads(proc.stdout)['status'] == 'cancelled'


def test_real_child_capture_blocks_annotation_and_summary_bypass(monkeypatch, capsys, tmp_path):
    """Execute a local synthetic child, never production or an external API."""
    configure_main(monkeypatch)
    monkeypatch.chdir(tmp_path)
    summary = tmp_path / 'summary.txt'
    output = tmp_path / 'github-output.txt'
    summary.write_text('')
    output.write_text('')
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(summary))
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    script = (
        'import os,sys,pathlib\n'
        f'raw={RAW!r}\n'
        'print("[PRODUCT REVIEW] observed")\n'
        'print("Product Review Gemini Requests Used: 2/3 (review=2)")\n'
        'print("::error::"+raw)\n'
        'print(raw,file=sys.stderr)\n'
        'for key in ("GITHUB_STEP_SUMMARY","GITHUB_OUTPUT"):\n'
        '    if os.environ.get(key): pathlib.Path(os.environ[key]).write_text(raw)\n'
    )
    (tmp_path/'production_pipeline.py').write_text(script)
    assert dpr.main() == 0
    captured = capsys.readouterr()
    assert not any(s in captured.out + captured.err + summary.read_text() + output.read_text() for s in SENTINELS)
    assert '::error::' not in captured.out + captured.err
    receipt = json.loads(captured.out)
    assert receipt['request_count'] == 2 and receipt['request_budget'] == 3
    assert receipt['allowlist_count'] == len(SENTINELS)


def test_no_other_workflow_upload_selects_failure_screenshot():
    for workflow in (ROOT/'.github/workflows').glob('*.yml'):
        for path in upload_paths(workflow):
            assert 'failure.png' not in path
            assert 'note-failure' not in path
            assert '.runtime/note_draft' not in path
            assert path.strip() not in {'.', './', '**', '**/*', '${{ runner.temp }}', '/tmp/'}


@pytest.mark.parametrize('phase', ['preflight', 'query', 'enrich'])
def test_parent_exception_never_prints_payload(phase, monkeypatch, capsys):
    configure_main(monkeypatch)
    failure = mock.Mock(side_effect=RuntimeError(RAW))
    monkeypatch.setattr(dpr, '_run_product_only', lambda *a: {'skipped': False})
    if phase == 'preflight':
        monkeypatch.setattr(dpr.context_first_enrichment, 'preflight_context_first_schema', failure)
    elif phase == 'query':
        monkeypatch.setattr(dpr.decision_intelligence, 'query_technology_records', failure)
    else:
        monkeypatch.setattr(dpr.context_first_enrichment, 'enrich_context_first', failure)
    assert dpr.main() == 1
    captured = capsys.readouterr()
    assert not any(s in captured.out + captured.err for s in SENTINELS)
    assert json.loads(captured.out)['error_category'] == 'diagnostic_unavailable'
