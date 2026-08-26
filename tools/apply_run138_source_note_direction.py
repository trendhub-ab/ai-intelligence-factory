from pathlib import Path

path = Path('pipeline.py')
text = path.read_text(encoding='utf-8')
old = '本文の技術的な事実・数値は、下記の公式リンクおよび参考情報で確認できる範囲を独自に分析・要約したものです。'
new = '本文の技術的な事実・数値は、上記の公式リンクおよび参考情報で確認できる範囲を独自に分析・要約したものです。'
if old not in text:
    raise SystemExit('Run138 anchor missing: HackerNews source rights note')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')

Path('tests/test_run138_source_note_direction.py').write_text('''import unittest\nimport pipeline\n\n\nclass Run138SourceNoteDirectionTests(unittest.TestCase):\n    def test_hackernews_source_note_points_upward(self):\n        note = pipeline.SOURCE_RIGHTS_NOTE["HackerNews"]\n        self.assertIn("上記の公式リンクおよび参考情報", note)\n        self.assertNotIn("下記の公式リンクおよび参考情報", note)\n\n    def test_source_rights_notes_do_not_point_downward(self):\n        for source, note in pipeline.SOURCE_RIGHTS_NOTE.items():\n            self.assertNotIn("下記の公式リンク", note, source)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding='utf-8')
