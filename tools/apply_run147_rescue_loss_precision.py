from pathlib import Path

PIPELINE = Path('pipeline.py')
text = PIPELINE.read_text(encoding='utf-8')

old = '"loss_exceeded": bool(important_numeric_removed or removed_sentences >= 3),'
new = '"loss_exceeded": bool(removed_sentences >= 3 or (important_numeric_removed and removed_sentences != 1)),'

if old not in text:
    raise SystemExit('Run147 rescue-loss anchor not found')
if text.count(old) != 1:
    raise SystemExit(f'Run147 expected exactly one rescue-loss anchor, found {text.count(old)}')

text = text.replace(old, new, 1)
PIPELINE.write_text(text, encoding='utf-8')
print('Run147 rescue-loss precision applied')
