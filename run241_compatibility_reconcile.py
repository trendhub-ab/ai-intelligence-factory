from pathlib import Path

PIPELINE = Path('pipeline.py')
MIGRATION = Path('run241_batched_modularization_migration.py')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, found {count}')
    return text.replace(old, new, 1)


pipeline_old = '    build_subscription_tracking_url as _build_subscription_tracking_url_impl, normalize_markdown_for_note as _normalize_markdown_for_note_impl,\n'
pipeline_new = '    SOURCE_RIGHTS_NOTE, build_subscription_tracking_url as _build_subscription_tracking_url_impl, normalize_markdown_for_note as _normalize_markdown_for_note_impl,\n'
# The migration owns this import inside IMPORT_BLOCK, so the source file contains a literal
# backslash+n sequence rather than an actual line break at this point.
migration_old = r'    build_subscription_tracking_url as _build_subscription_tracking_url_impl, normalize_markdown_for_note as _normalize_markdown_for_note_impl,\n'
migration_new = r'    SOURCE_RIGHTS_NOTE, build_subscription_tracking_url as _build_subscription_tracking_url_impl, normalize_markdown_for_note as _normalize_markdown_for_note_impl,\n'

pipeline = PIPELINE.read_text()
if '    SOURCE_RIGHTS_NOTE, build_subscription_tracking_url as _build_subscription_tracking_url_impl' not in pipeline:
    pipeline = replace_once(pipeline, pipeline_old, pipeline_new, 'pipeline note import')
PIPELINE.write_text(pipeline)

migration = MIGRATION.read_text()
if migration_new not in migration:
    migration = replace_once(migration, migration_old, migration_new, 'migration note import')
MIGRATION.write_text(migration)

if len(pipeline.splitlines()) != 11497:
    raise RuntimeError(f'compatibility reconciliation changed pipeline line count: {len(pipeline.splitlines())}')
print('Run241 SOURCE_RIGHTS_NOTE compatibility reconciliation: PASS')
