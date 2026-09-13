import json
import tempfile
import unittest
from pathlib import Path

from groq_writer_v4_contract import (
    GroqWriterV4Error,
    harden_writer_fixture,
    validate_writer_report,
)


def writer_fixture():
    return {
        "provider": "groq",
        "model": "groq/compound-mini",
        "prompt": "BASE WRITER PROMPT",
        "max_output_tokens": 3200,
        "schema": None,
    }


def report(article: str):
    return {
        "provider": "groq",
        "model": "groq/compound-mini",
        "provider_calls": 1,
        "result": {
            "text": "===TITLE===\n100%という数字を、そのまま信じてよい？\n===ARTICLE===\n" + article,
            "prompt_tokens": 100,
            "completion_tokens": 100,
        },
    }


def bounded_filler(repeat=42):
    return (
        "一次資料に書かれた事実と、そこから想像できることは分けて読む必要があります。"
        "数字だけを切り取らず、その数字がどの評価条件で出たのかを確認することが大切です。"
    ) * repeat


class GroqWriterV4ContractTests(unittest.TestCase):
    def test_hardening_is_idempotent_and_groq_only(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "writer.json"
            path.write_text(json.dumps(writer_fixture(), ensure_ascii=False), encoding="utf-8")
            first = harden_writer_fixture(str(path))
            second = harden_writer_fixture(str(path))
            self.assertEqual(first["contract_version"], "groq_writer_v4_reader_first")
            self.assertEqual(second["prompt"].count("V4 READER-FIRST CONTRACT"), 1)
            self.assertIn("私なら", second["prompt"])
            self.assertIn("リアルタイムで評価", second["prompt"])

    def test_v3_inferred_safeguard_mechanics_are_blocked(self):
        article = (
            "100%という数字には条件があります。例えば、レーシングカーの速さと公道で乗れるかは別の話です。"
            + bounded_filler()
            + "system safety classifierが出力内容を安全基準に照らしてリアルタイムで評価します。"
            + "私なら、現時点では導入判断をせず、まず一次情報で利用条件を確認します。"
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            path.write_text(json.dumps(report(article), ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(GroqWriterV4Error, "writer_source_boundary_violation|writer_inferred_safeguard_mechanics"):
                validate_writer_report(str(path))

    def test_v3_general_availability_inference_is_blocked(self):
        article = (
            "2件のzero-dayが見つかったという事実は目を引きます。簡単に言えば、能力と利用条件は別々に読む必要があります。"
            + bounded_filler()
            + "一般的な本番環境での利用は想定されていません。"
            + "私なら、今すぐ導入判断はせず、まず一次情報で利用条件を確認します。"
        )
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            path.write_text(json.dumps(report(article), ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(GroqWriterV4Error, "writer_source_boundary_violation"):
                validate_writer_report(str(path))

    def test_reader_contract_requires_decision_voice(self):
        article = (
            "100%という数字には条件があります。例えば、レーシングカーの速さと公道で乗れるかは別の話です。"
            + bounded_filler()
            + "能力の高さだけで導入可否を決めるべきではありません。"
        )
        self.assertGreaterEqual(len(article), 1300)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            path.write_text(json.dumps(report(article), ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(GroqWriterV4Error, "writer_decision_voice_missing"):
                validate_writer_report(str(path))

    def test_reader_contract_accepts_bounded_reader_first_surface(self):
        article = (
            "100%という数字を見ると、何でもできるAIのように感じるかもしれません。"
            "でも、ここには大事な条件があります。例えば、レーシングカーが速いことと、公道を自由に走れることは別の話です。\n\n"
            "ExploitBenchは、既知の脆弱性から攻撃方法を作れるかを見る評価です。Astraはこの評価で100%を記録しました。"
            "一方、この数字を一般的な性能へ広げて読むことはできません。\n\n"
            "さらに一次資料では、2026年6〜8月に公開された高深刻度V8脆弱性20件を評価し、その過程で2件のzero-dayを発見したとされています。"
            "zero-dayとは、まだ広く知られていない脆弱性のことです。数字の派手さより、どの条件で確認されたかを見る必要があります。\n\n"
            "安全策として、アクセス制限、拒否訓練、system safety classifier、監視、misalignment detectionが挙げられています。"
            "ここで重要なのは、名称から動作を想像して補わないことです。一次資料が示す範囲だけで判断します。\n\n"
            + bounded_filler(20)
            + "\n\n能力が高いというニュースと、今すぐ自社で使えるという話は同じではありません。"
            "私なら、現時点では導入判断をせず、まず一次情報で利用条件を確認します。"
            "その確認が済むまでは、能力の高さをそのまま導入理由にはしません。"
        )
        self.assertGreaterEqual(len(article), 1300)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            path.write_text(json.dumps(report(article), ensure_ascii=False), encoding="utf-8")
            result = validate_writer_report(str(path))
            self.assertTrue(result["v4_source_boundary_validated"])
            self.assertTrue(result["v4_reader_contract_validated"])


if __name__ == "__main__":
    unittest.main()
