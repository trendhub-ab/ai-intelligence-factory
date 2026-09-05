from pathlib import Path

PIPELINE = Path('pipeline.py')
MIGRATION = Path('run241_batched_modularization_migration.py')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, found {count}')
    return text.replace(old, new, 1)


old = '    build_subscription_tracking_url as _build_subscription_tracking_url_impl, normalize_markdown_for_note as _normalize_markdown_for_note_impl,\n'
new = '    SOURCE_RIGHTS_NOTE, build_subscription_tracking_url as _build_subscription_tracking_url_impl, normalize_markdown_for_note as _normalize_markdown_for_note_impl,\n'

pipeline = PIPELINE.read_text()
if '    SOURCE_RIGHTS_NOTE, build_subscription_tracking_url as _build_subscription_tracking_url_impl' not in pipeline:
    pipeline = replace_once(pipeline, old, new, 'pipeline note import')
PIPELINE.write_text(pipeline)

migration = MIGRATION.read_text()
if '    SOURCE_RIGHTS_NOTE, build_subscription_tracking_url as _build_subscription_tracking_url_impl' not in migration:
    migration = replace_once(migration, old, new, 'migration note import')
MIGRATION.write_text(migration)

if len(pipeline.splitlines()) != 11497:
    raise RuntimeError(f'compatibility reconciliation changed pipeline line count: {len(pipeline.splitlines())}')
print('Run241 SOURCE_RIGHTS_NOTE compatibility reconciliation: PASS')
