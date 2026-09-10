from __future__ import annotations

import unittest

import run330_note_profile_exact_update as run330


class Run331ProfileSnapshotDiffTests(unittest.TestCase):
    def test_equal_snapshots_have_no_diff(self) -> None:
        rows = [{"tag": "input", "type": "text", "name": "editNickname", "ariaLabel": "クリエイター名", "value": "AI Intelligence Factory", "checked": False, "occurrence": 0}]
        self.assertEqual(run330._snapshot_diff(rows, list(rows)), "")

    def test_changed_semantic_value_is_reported(self) -> None:
        before = [{"tag": "input", "type": "text", "name": "instagramLink", "ariaLabel": "", "value": "", "checked": False, "occurrence": 0}]
        after = [{"tag": "input", "type": "text", "name": "instagramLink", "ariaLabel": "", "value": "https://example.com", "checked": False, "occurrence": 0}]
        diff = run330._snapshot_diff(before, after)
        self.assertIn("instagramLink", diff)
        self.assertIn("https://example.com", diff)


if __name__ == "__main__":
    unittest.main()
