import json
import tempfile
import unittest
from pathlib import Path

from groq_writer_v7_contract import (
    GroqWriterV7Error,
    harden_writer_fixture_v7,
    inspect_writer_report,
    validate_writer_report_v7,
)


def report(text: str) -> dict:
    return {
        "provider": "groq",
        "model": "openai/gpt-oss-120b",
        "provider_calls": 1,
        "business_writes": 0,
        "result": {"text": text, "prompt_tokens": 100, "completion_tokens": 100},
    }


class GroqWriterV7ContractTests(unittest.TestCase):
    def test_aggregates_multiple_v6_style_failures(self):
        article = (
            "100%という数字は目を引きます。簡単に言えば、能力と利用条件は別の話です。\n\n"
            "Daybreak Blueアクセスがどのように取得できるか確認します。\n\n"
            "この結果は高度に制御された環境であることを裏付けます。\n\n"
            "私なら、今すぐ導入判断はせず、一次情報を確認します。"
        )
        text = "===TITLE===\n句点のないタイトル\n===ARTICLE===\n" + article
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            path.write_text(json.dumps(report(text), ensure_ascii=False), encoding="utf-8")
            inspected = inspect_writer_report(str(path))
            self.assertTrue(any(x.startswith("article_too_short:") for x in inspected["issues"]))
            self.assertIn("heading_count:0", inspected["issues"])
            self.assertIn("title_punctuation", inspected["issues"])
            self.assertIn("daybreak_access_assumption", inspected["issues"])
            self.assertIn("controlled_environment_inference", inspected["issues"])
            with self.assertRaisesRegex(GroqWriterV7Error, "writer_v7_contract"):
                validate_writer_report_v7(str(path))

    def test_harden_adds_v7_contract_once(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fixture.json"
            path.write_text(json.dumps({
                "provider": "groq", "stage": "article", "prompt": "base",
            }), encoding="utf-8")
            first = harden_writer_fixture_v7(str(path))
            second = harden_writer_fixture_v7(str(path))
            self.assertEqual(second["prompt"].count("V7 COMPLETE READER + SOURCE BOUNDARY CONTRACT"), 1)
            self.assertEqual(first["contract_version_v7"], "groq_writer_v7_aggregate_reader_boundary")

    def test_valid_shape_passes(self):
        paras = [
            "100%という数字は強烈です。しかし対象はExploitBenchで、簡単に言えば測定結果と利用条件は別の話です。" + "条件を丁寧に読む必要があります。" * 5,
            "OpenAIのPreparedness Frameworkという評価枠組みでは、Astraが重大なサイバー能力の基準に到達したとされています。" + "ここで重要なのは数字の対象を広げないことです。" * 4,
            "2026年6月から8月の評価では高深刻度のV8脆弱性20件が扱われ、2件のzero-dayも記録されています。" + "一次資料が示す範囲だけを読み取ります。" * 4,
            "安全策についてはアクセス制限、拒否訓練、system safety classifier、監視、misalignment detectionという名称が示されています。" + "名称から具体的な動作を推測してはいけません。" * 4,
            "能力が高いことと、誰がどの条件で利用できるかは別問題です。" + "この一次資料から利用条件は確認できません。" * 5,
            "読者側で変わるのは、性能の数字だけで導入判断をしないことです。" + "測定条件と提供条件を分けて確認します。" * 5,
            "私なら、今すぐ導入判断はせず、まず一次情報で利用条件を確認します。" + "確認できるまでPoCや申請を前提にしません。" * 5,
            "そのうえで、自社に関係する条件が一次情報で確認できた時点で改めて判断します。" + "今は注視が妥当です。" * 5,
        ]
        article = paras[0] + "\n\n## 100%をそのまま読まない\n\n" + paras[1] + "\n\n" + paras[2] + "\n\n## 数字の外側にある安全策\n\n" + paras[3] + "\n\n" + paras[4] + "\n\n## 導入判断より先に確認すること\n\n" + "\n\n".join(paras[5:])
        self.assertGreaterEqual(len(article), 1500)
        self.assertLessEqual(len(article), 2100)
        text = "===TITLE===\n100%という数字を、そのまま信じてよい？\n===ARTICLE===\n" + article
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            path.write_text(json.dumps(report(text), ensure_ascii=False), encoding="utf-8")
            inspected = inspect_writer_report(str(path))
            self.assertEqual(inspected["issues"], [])
            validated = validate_writer_report_v7(str(path))
            self.assertTrue(validated["v7_source_boundary_validated"])
            self.assertTrue(validated["v7_reader_contract_validated"])


if __name__ == "__main__":
    unittest.main()
