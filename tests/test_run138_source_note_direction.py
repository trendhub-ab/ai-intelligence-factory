import unittest
import pipeline


class Run138SourceNoteDirectionTests(unittest.TestCase):
    def test_hackernews_source_note_points_upward(self):
        note = pipeline.SOURCE_RIGHTS_NOTE["HackerNews"]
        self.assertIn("上記の公式リンクおよび参考情報", note)
        self.assertNotIn("下記の公式リンクおよび参考情報", note)

    def test_source_rights_notes_do_not_point_downward(self):
        for source, note in pipeline.SOURCE_RIGHTS_NOTE.items():
            self.assertNotIn("下記の公式リンク", note, source)


if __name__ == "__main__":
    unittest.main()
