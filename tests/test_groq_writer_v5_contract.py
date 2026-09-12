import json
import tempfile
import unittest
from pathlib import Path

from groq_writer_v5_contract import (
    GroqWriterV5Error,
    harden_writer_fixture,
    validate_writer_report,
)


def writer_fixture():
    return {
        "provider": "groq", "model": "groq/compound-mini",
        "prompt": "BASE WRITER PROMPT", "max_output_tokens": 3200,
        "reasoning_effort": "medium", "schema": None,
    }


def report(article: str):
    return {
        "provider": "groq", "model": "groq/compound-mini", "provider_calls": 1,
        "result": {
            "text": "===TITLE===\n100%という数字を、そのまま信じてよい？\n===ARTICLE===\n" + article,
            "prompt_tokens": 100, "completion_tokens": 100,
        },
    }


def safe_paragraph(seed: str):
    return seed + "一次資料に書かれた事実と、そこから想像できることは分けて読む必要があります。数字だけを切り取らず、その数字がどの評価条件で出たのかを確認することが大切です。"


def valid_article():
    return "\n\n".join([
        "100%という数字を見ると、何でもできるAIのように感じるかもしれません。ですが、この100%は既知脆弱性からexploitを開発するExploitBenchで記録された値です。たとえば、レーシングカーが速いことと、公道を自由に走れることは別の話です。",
        "## 100%は、どの物差しで測った数字なのか",
        safe_paragraph("OpenAIのPreparedness Frameworkという評価枠組みでは、AstraがCritical cybersecurity capability threshold（重大なサイバー能力の基準）に到達した最初のモデルと説明されています。"),
        safe_paragraph("この結果はdefault production configurationではなくDaybreak Blue access条件を反映します。"),
        "## 2件のzero-dayが示したもの",
        safe_paragraph("一次資料では、2026年6〜8月に公開された高深刻度V8脆弱性20件を社内評価し、その途中で2件のzero-day脆弱性を発見したとされています。"),
        safe_paragraph("2件はexploit chainの一部として利用されたと記されています。具体的な攻撃方法を足さず、ここでは一次資料が示した範囲だけを見ます。"),
        "## 強い能力と、使える条件は別に見る",
        safe_paragraph("公開時には、高度なサイバー能力へのアクセス制限、拒否訓練、system safety classifier、監視、misalignment detectionなど複数の安全策を適用すると説明されています。名称だけから動作を推測するべきではありません。"),
        safe_paragraph("能力の高さが確認されたことと、自社で今すぐ利用できることは同じ意味ではありません。この一次資料から一般利用条件までは確認できません。"),
        "私なら、今すぐ導入判断はせず、まず一次情報で利用条件を確認します。能力の強さではなく、確認できた条件までを判断材料にします。",
    ])


class GroqWriterV5ContractTests(unittest.TestCase):
    def test_hardening_adds_v5_once(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "fixture.json"
            path.write_text(json.dumps(writer_fixture(), ensure_ascii=False), encoding="utf-8")
            first = harden_writer_fixture(str(path))
            second = harden_writer_fixture(str(path))
            self.assertEqual(first["contract_version"], "groq_writer_v5_reader_length_precision")
            self.assertEqual(second["prompt"].count("V5 READER-LENGTH + EVIDENCE PRECISION CONTRACT"), 1)
            self.assertIn("1400字未満のまま返答してはいけない", second["prompt"])

    def test_v4_short_article_still_blocks(self):
        article = "\n\n".join([
            "100%という数字には条件があります。例えば、速い車でも公道で走れる条件は別です。",
            "## 条件を見る",
            "ExploitBenchの100%は評価条件の中で読む必要があります。",
            "## 次に見るもの",
            "私なら、まず一次情報で利用条件を確認します。",
        ])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            path.write_text(json.dumps(report(article), ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(GroqWriterV5Error, "writer_reader_article_too_short"):
                validate_writer_report(str(path))

    def test_v4_unsupported_interpretations_block_even_if_padded(self):
        bad_phrases = [
            "安全策が多数導入されていることは安心材料です。",
            "利用可能になるまでのハードルが存在します。",
            "アクセス条件や運用方法は公開されていません。",
            "Preparedness Frameworkはサイバー防御力を評価する枠組みです。",
        ]
        for bad in bad_phrases:
            article = valid_article() + "\n\n" + bad
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / "report.json"
                path.write_text(json.dumps(report(article), ensure_ascii=False), encoding="utf-8")
                with self.assertRaisesRegex(GroqWriterV5Error, "writer_source_boundary_violation|writer_inferred_or_mistranslated_claim"):
                    validate_writer_report(str(path))

    def test_bold_only_headings_block(self):
        article = valid_article().replace("## 100%は、どの物差しで測った数字なのか", "**100%は、どの物差しで測った数字なのか**")
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            path.write_text(json.dumps(report(article), ensure_ascii=False), encoding="utf-8")
            with self.assertRaisesRegex(GroqWriterV5Error, "writer_heading_contract_invalid|writer_bold_heading_forbidden"):
                validate_writer_report(str(path))

    def test_valid_reader_first_article_passes(self):
        article = valid_article()
        self.assertGreaterEqual(len(article), 1300)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "report.json"
            path.write_text(json.dumps(report(article), ensure_ascii=False), encoding="utf-8")
            result = validate_writer_report(str(path))
            self.assertTrue(result["v5_source_boundary_validated"])
            self.assertTrue(result["v5_reader_contract_validated"])
            self.assertGreaterEqual(result["v5_article_chars"], 1300)
            self.assertEqual(result["v5_headings"], 3)
            self.assertGreaterEqual(result["v5_paragraphs"], 7)


if __name__ == "__main__":
    unittest.main()
