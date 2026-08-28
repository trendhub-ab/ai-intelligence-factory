import inspect
import unittest
import pipeline


class Run145RealArticleClosureTests(unittest.TestCase):
    def test_absolute_sandbox_host_safety_is_hard_detected(self):
        text = 'サンドボックス内なら、AIがどんな操作を行ってもPCには影響が及びません。'
        failures = pipeline._find_hype_claims(text, '', {})
        self.assertTrue(any('unsupported absolute isolation' in x for x in failures), failures)

    def test_containment_guarantee_is_hard_detected(self):
        text = '問題が起きても、被害範囲をこのコンテナだけに抑え込める仕組みです。'
        failures = pipeline._find_hype_claims(text, '', {})
        self.assertTrue(any('unsupported containment guarantee' in x for x in failures), failures)

    def test_limited_security_wording_is_not_false_positive(self):
        text = '権限を狭くすると、誤操作や侵害が起きたときの被害範囲も狭めやすくなります。ただし安全が保証されるわけではありません。'
        failures = pipeline._find_hype_claims(text, '', {})
        self.assertFalse(any('unsupported absolute isolation' in x or 'unsupported containment guarantee' in x for x in failures), failures)

    def test_malformed_ordinal_year_is_repaired_without_touching_version(self):
        article = '### 変化\n\n2.2026年以降の方針を見る。\n\nSDK v2.2026 は別の文字列です。'
        repaired, changes = pipeline._repair_malformed_reader_numbering(article)
        self.assertIn('2. 2026年以降', repaired)
        self.assertIn('SDK v2.2026', repaired)
        self.assertTrue(changes)

    def test_prompt_closes_real_article_defects(self):
        prompt = pipeline._human_editorial_style_rules()
        self.assertIn('Roadmap、protocol、SDK、仕様変更', prompt)
        self.assertIn('何をしてもPCへ影響しない', prompt)

    def test_no_new_gemini_call_site(self):
        src = inspect.getsource(pipeline)
        self.assertEqual(7, src.count('_generate_via_chat('))
        self.assertEqual(1, src.count('genai.Client('))


if __name__ == '__main__':
    unittest.main()
