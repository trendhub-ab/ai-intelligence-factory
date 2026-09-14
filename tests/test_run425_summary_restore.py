import unittest
from unittest.mock import patch
import run425_rubygems_summary_restore as repair


class SummaryRestoreTests(unittest.TestCase):
    def manuscript(self):
        return ("# " + repair.target.EXPECTED_NOTE_TITLE + "\n\n### 元情報\n"
                + repair.target.EXPECTED_SOURCE_TITLE + "\n\n## 詳細\n"
                + "研究チームが分析。APIキー窃取が成功したかは不明。"
                + "ネットワークの出口制限と認証分離を点検。\n")

    def test_only_summary_added_and_idempotent(self):
        old = self.manuscript()
        new = repair.restore(old)
        self.assertEqual(new.replace(repair.SUMMARY, "", 1), old)
        self.assertEqual(repair.restore(new), new)
        self.assertEqual(new.count(repair.SUMMARY), 1)

    def test_unknown_title_partial_summary_and_missing_support_rejected(self):
        for bad in (self.manuscript().replace(repair.target.EXPECTED_NOTE_TITLE, "別記事"),
                    self.manuscript() + "\n## どんな内容？\n",
                    self.manuscript().replace("認証分離", "別の説明")):
            with self.subTest(bad=bad), self.assertRaises(RuntimeError):
                repair.restore(bad)

    def test_hash_and_policy_checked_before_accepting_source(self):
        old = self.manuscript()
        fields = (repair.contract.READY_CAPTION_PREFIX
                  + "contract=" + repair.contract.CONTRACT_ID
                  + "|policy_sha256=" + repair.OLD_POLICY
                  + "|manuscript_sha256=" + repair.contract.manuscript_sha256(old))
        block = {"type": "code", "code": {
            "rich_text": repair.source.rich(old), "caption": repair.source.rich(fields)}}
        with patch.object(repair.contract, "policy_sha256", return_value="f" * 64):
            original, new = repair.accepted_source([block])
            self.assertEqual(original, old)
            self.assertEqual(new, repair.restore(old))
            block["code"]["rich_text"] = repair.source.rich(old + "改変")
            with self.assertRaises(RuntimeError):
                repair.accepted_source([block])
            block["code"]["rich_text"] = repair.source.rich(old)
            block["code"]["caption"] = repair.source.rich(fields.replace(repair.OLD_POLICY, "a" * 64))
            with self.assertRaises(RuntimeError):
                repair.accepted_source([block])


if __name__ == "__main__":
    unittest.main()
