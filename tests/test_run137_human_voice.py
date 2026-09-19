import canonical_article_contract as canonical
import inspect
import unittest
import pipeline


class Run137HumanVoiceTests(unittest.TestCase):
    def test_prompt_treats_reader_as_real_person_not_abstract_user(self):
        src = canonical.ensure_final_reader_check(pipeline._human_editorial_style_rules())
        self.assertIn('読者を一人の人として扱う', src)
        self.assertIn('読者の困りごと・迷い・選択', src)

    def test_prompt_avoids_ai_staging_phrase_repetition(self):
        src = canonical.ensure_final_reader_check(pipeline._human_editorial_style_rules())
        self.assertIn('ここで重要なのは', src)
        self.assertIn('つまり', src)
        self.assertIn('等を反復しない', src)
        self.assertIn('各段落が前段落の疑問・意味・判断を受け', src)

    def test_reader_question_must_have_function(self):
        src = canonical.ensure_final_reader_check(pipeline._human_editorial_style_rules())
        self.assertIn('語りかけは装飾ではなく理解の橋', src)
        self.assertIn('中身のない問い', src)
        self.assertIn('何を見ればよいか・なぜ自分に関係するか', src)

    def test_ai_style_retry_does_not_swap_to_new_catchphrase_template(self):
        rows = [{
            'reason_code': pipeline.REASON_CODE_APPEAL_AI_STYLE_COMPOSITE,
            'message': 'ai style',
            'gate': 'appeal',
            'severity': pipeline.GATE_SEVERITY_REVIEW,
        }]
        instruction, _ = pipeline.build_dynamic_retry_instruction(rows)
        self.assertIn('常套句へ置き換えるだけの修正は禁止', instruction)
        self.assertIn('呼びかけ・相づち・疑問形を連打せず', instruction)

    def test_run137_adds_no_gemini_call_site(self):
        src = inspect.getsource(pipeline)
        self.assertEqual(7, src.count('_generate_via_chat('))
        self.assertEqual(1, src.count('genai.Client('))


if __name__ == '__main__':
    unittest.main()
