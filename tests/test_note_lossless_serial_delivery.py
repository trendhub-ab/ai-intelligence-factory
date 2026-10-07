from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / '.github' / 'workflows'


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding='utf-8')


def step_script(name: str, step: str) -> str:
    source = workflow(name).split('      - name: ' + step + '\n', 1)[1]
    source = source.split('\n      - name:', 1)[0].split('\n  stop-cloud-vm:', 1)[0]
    script = source.split('        run: |\n', 1)[1]
    script = re.split(r'\n(?= {0,9}\S)', script, maxsplit=1)[0]
    return textwrap.dedent(script).rstrip() + '\n'


class NoteLosslessSerialDeliveryTests(unittest.TestCase):
    def test_both_workflows_request_non_replacing_global_serial_queues(self) -> None:
        # GitHub's boundary contract: the default pending slot replaces its
        # predecessor even with cancel-in-progress=false. queue=max retains
        # up to 100 waiting runs; do not remove or target-scope the global lock.
        # https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
        for name, group in [('note-ready-sync.yml', 'note-ready-article-sync'),
                            ('note-create-draft.yml', 'note-draft-create')]:
            with self.subTest(workflow=name):
                source = workflow(name)
                block = re.search(r'(?m)^concurrency:\n((?:[ \t]+[^\n]*\n|\n)+)', source)
                self.assertIsNotNone(block, 'The entire workflow must have a single writer')
                settings = dict(line.strip().split(': ', 1) for line in block[1].splitlines()
                                if ': ' in line and not line.lstrip().startswith('#'))
                self.assertEqual(group, settings.get('group'))
                self.assertEqual('max', settings.get('queue'), 'A single pending slot loses Ready deliveries')
                self.assertEqual('false', settings.get('cancel-in-progress'))

    def run_script(self, script: str, *, selected: str = '', count: str = '1',
                   api_error: bool = False) -> tuple[subprocess.CompletedProcess, list]:
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            gh = folder / 'gh'
            gh.write_text('''#!/usr/bin/env python3
import json, os, sys
with open(os.environ['CALLS'], 'a') as f:
    f.write(json.dumps(sys.argv[1:]) + '\\n')
if sys.argv[1] == 'api':
    if os.environ['API_ERROR'] == 'true':
        sys.exit(1)
    print(os.environ['RUNNER_COUNT'])
''', encoding='utf-8')
            gh.chmod(0o755)
            sleep = folder / 'sleep'
            sleep.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
            sleep.chmod(0o755)
            env = {**os.environ, 'PATH': str(folder) + ':' + os.environ['PATH'],
                   'GH_TOKEN': 'offline-test-token', 'SELECTED_SYNC_ID': selected,
                   'GITHUB_REPOSITORY': 'example/offline', 'GITHUB_STEP_SUMMARY': str(folder / 'summary'),
                   'CALLS': str(folder / 'calls'), 'RUNNER_COUNT': count,
                   'API_ERROR': str(api_error).lower()}
            result = subprocess.run(['bash', '-c', script], env=env, capture_output=True, text=True, timeout=10)
            calls = [json.loads(line) for line in (folder / 'calls').read_text().splitlines()] if (folder / 'calls').exists() else []
            return result, calls

    def test_four_distinct_ready_targets_dispatch_four_exact_private_draft_payloads(self) -> None:
        script = step_script('note-ready-sync.yml', 'Dispatch private note draft flow only for an exact eligible Ready')
        calls = []
        for target in ['a' * 32, 'b' * 32, 'c' * 32, 'd' * 32]:
            result, recorded = self.run_script(script, selected=target)
            self.assertEqual(0, result.returncode, result.stderr)
            calls.extend(recorded)
        self.assertEqual([
            ['workflow', 'run', 'note-create-draft.yml', '--ref', 'main', '-f',
             'confirm=CREATE_NOTE_DRAFT', '-f', 'sync_id=' + target, '-f', 'prepare_only=false']
            for target in ['a' * 32, 'b' * 32, 'c' * 32, 'd' * 32]
        ], calls)

    def test_missing_exact_target_fails_without_dispatch(self) -> None:
        result, calls = self.run_script(step_script('note-ready-sync.yml', 'Dispatch private note draft flow only for an exact eligible Ready'))
        self.assertNotEqual(0, result.returncode)
        self.assertEqual([], calls)

    def test_exactly_one_online_runner_allows_delivery(self) -> None:
        result, calls = self.run_script(step_script('note-create-draft.yml', 'Wait for exactly one registered note runner to become online'))
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, len(calls))
        self.assertEqual(['api', 'repos/example/offline/actions/runners?per_page=100'], calls[0][:2])
        self.assertIn('.status == "online"', calls[0][-1])
        self.assertIn('.name == "aiif-note-cloud"', calls[0][-1])

    def test_absent_multiple_or_unreadable_runners_never_allow_delivery(self) -> None:
        script = step_script('note-create-draft.yml', 'Wait for exactly one registered note runner to become online')
        for count, error, attempts in [('0', False, 60), ('2', False, 1), ('', True, 60), ('invalid', False, 60)]:
            with self.subTest(count=count, api_error=error):
                result, calls = self.run_script(script, count=count, api_error=error)
                self.assertNotEqual(0, result.returncode)
                self.assertEqual(attempts, len(calls))


if __name__ == '__main__':
    unittest.main()
