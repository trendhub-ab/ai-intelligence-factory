from pathlib import Path

PIPELINE = Path('pipeline.py')
text = PIPELINE.read_text(encoding='utf-8')

old = 'REGEN_TEST_SOURCE = os.environ.get("REGEN_TEST_SOURCE", "").strip()\nREGEN_TEST_OUTPUT_DIR = os.environ.get("REGEN_TEST_OUTPUT_DIR", "regen_test_outputs")'
new = 'REGEN_TEST_SOURCE = os.environ.get("REGEN_TEST_SOURCE", "").strip()\nREGEN_TEST_TITLE_CONTAINS = os.environ.get("REGEN_TEST_TITLE_CONTAINS", "").strip()\nREGEN_TEST_OUTPUT_DIR = os.environ.get("REGEN_TEST_OUTPUT_DIR", "regen_test_outputs")'
if old not in text:
    raise SystemExit('Run146 env anchor not found')
text = text.replace(old, new, 1)

old = '''    if items is None:\n        logger.error("[REGEN TEST ABORTED] 回帰テスト候補の読み出し/収集に失敗しました。")'''
new = '''    if items is not None and REGEN_TEST_TITLE_CONTAINS:\n        needle = REGEN_TEST_TITLE_CONTAINS.casefold()\n        items = [item for item in items if needle in str(item.get("name") or item.get("title") or "").casefold()]\n        logger.info(\n            "[REGEN TEST TITLE FILTER] contains=%r matched=%d",\n            REGEN_TEST_TITLE_CONTAINS, len(items),\n        )\n        if not items:\n            logger.error("[REGEN TEST ABORTED] タイトル絞り込みに一致する候補がありません。")\n            return\n\n    if items is None:\n        logger.error("[REGEN TEST ABORTED] 回帰テスト候補の読み出し/収集に失敗しました。")'''
if old not in text:
    raise SystemExit('Run146 item-filter anchor not found')
text = text.replace(old, new, 1)

PIPELINE.write_text(text, encoding='utf-8')
print('Run146 regression title filter applied')
