import json
import tempfile
import unittest
from pathlib import Path

from groq_writer_v8_contract import harden_writer_fixture_v8, inspect_writer_report_v8


def report(text):
    return {"provider":"groq","model":"openai/gpt-oss-120b","provider_calls":1,"business_writes":0,
            "result":{"text":text,"prompt_tokens":100,"completion_tokens":100}}


class GroqWriterV8Tests(unittest.TestCase):
    def test_v7_style_short_no_heading_fails_all_structure_checks(self):
        article = ("簡単に言えば、能力と利用条件は別です。" * 50)
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r.json'
            p.write_text(json.dumps(report('===TITLE===\nタイトルです。\n===ARTICLE===\n'+article),ensure_ascii=False),encoding='utf-8')
            issues=inspect_writer_report_v8(str(p))['issues']
            self.assertTrue(any(x.startswith('article_too_short:') or x.startswith('v8_article_too_short:') for x in issues))
            self.assertIn('heading_count:0', issues)
            self.assertIn('v8_heading_count:0', issues)
            self.assertIn('v8_paragraph_count:1', issues)

    def test_unconfirmed_access_requirement_assertion_fails(self):
        article = ('簡単に言えば、測定と利用は別です。' * 15 + '\n\n') * 10
        article = article.replace('\n\n', '\n\n## 固有見出し\n\n', 3)
        article += '導入には別途アクセス権が必要です。私なら一次情報を確認します。'
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'r.json'
            p.write_text(json.dumps(report('===TITLE===\nタイトルです。\n===ARTICLE===\n'+article),ensure_ascii=False),encoding='utf-8')
            self.assertIn('unconfirmed_access_requirement_assertion', inspect_writer_report_v8(str(p))['issues'])

    def test_harden_sets_2800_output_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'f.json'
            p.write_text(json.dumps({'provider':'groq','stage':'article','prompt':'base','max_output_tokens':2600}),encoding='utf-8')
            harden_writer_fixture_v8(str(p)); data=harden_writer_fixture_v8(str(p))
            self.assertEqual(data['max_output_tokens'],2800)
            self.assertEqual(data['prompt'].count('V8 OUTPUT SHAPE'),1)


if __name__ == '__main__':
    unittest.main()
