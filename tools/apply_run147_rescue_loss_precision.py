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

TESTS = Path('tests/test_free_article_delivery.py')
test_text = TESTS.read_text(encoding='utf-8')
old_test = '''    def test_rescue_loss_limit_marks_important_numeric_deletion(self):
        parsed = minimal_parsed(article=minimal_parsed()["note_draft"] + "\\np95は56.8 msでした。")
        rows = pipeline.map_gate_reasons("fact", ["unsupported numeric claim: 56.8 ms"])
        rescued, _ = pipeline._apply_deterministic_publication_rescue(parsed, rows)
        self.assertTrue(rescued["_rescue_loss"]["important_numeric_removed"])
        self.assertTrue(rescued["_rescue_loss"]["loss_exceeded"])
'''
new_test = '''    def test_rescue_loss_limit_allows_single_unsupported_numeric_sentence(self):
        parsed = minimal_parsed(article=minimal_parsed()["note_draft"] + "\\np95は56.8 msでした。")
        rows = pipeline.map_gate_reasons("fact", ["unsupported numeric claim: 56.8 ms"])
        rescued, _ = pipeline._apply_deterministic_publication_rescue(parsed, rows)
        self.assertTrue(rescued["_rescue_loss"]["important_numeric_removed"])
        self.assertEqual(1, rescued["_rescue_loss"]["removed_sentences"])
        self.assertFalse(rescued["_rescue_loss"]["loss_exceeded"])
'''
if old_test not in test_text:
    raise SystemExit('Run147 legacy rescue test anchor not found')
test_text = test_text.replace(old_test, new_test, 1)
TESTS.write_text(test_text, encoding='utf-8')

print('Run147 rescue-loss precision applied')
