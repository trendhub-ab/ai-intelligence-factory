from pathlib import Path

runtime_path = Path('note_delivery_runtime.py')
runtime = runtime_path.read_text(encoding='utf-8')

if '    LedgerUnavailableError,\n' not in runtime:
    runtime = runtime.replace(
        '    DeliveryLedgerError,\n',
        '    DeliveryLedgerError,\n    LedgerUnavailableError,\n',
        1,
    )

runtime_path.write_text(runtime, encoding='utf-8')

test_path = Path('tests/test_note_delivery_ledger.py')
test = test_path.read_text(encoding='utf-8')
needle = '            "NOTE_DELIVERY_LEDGER_PATH": str(path),\n'
replacement = '            "NOTE_DELIVERY_LEDGER_BACKEND": "sqlite",\n            "NOTE_DELIVERY_LEDGER_PATH": str(path),\n'
if replacement not in test:
    if needle not in test:
        raise SystemExit('read-only gate env marker not found')
    test = test.replace(needle, replacement, 1)
test_path.write_text(test, encoding='utf-8')
