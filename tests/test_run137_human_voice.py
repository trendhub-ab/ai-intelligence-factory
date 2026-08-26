import inspect
import unittest
import pipeline


class Run137HumanVoiceTests(unittest.TestCase):
    def test_prompt_treats_reader_as_real_person_not_abstract_user(self):
        src = inspect.getsource(pipeline.build_decision_prompt)
        self.assertIn('読者を抽象的な「ユーザー」として扱わず', src)
        self.assertIn('実際にスマホやPCを触り', src)

    def test_prompt_avoids_ai_staging_phrase_repetition(self):
        src = inspect.getsource(pipeline.build_decision_prompt)
        self.assertIn('ここで重要なのは', src)
        self.assertIn('ポイントは', src)
        self.assertIn('常套句', src)
        self.assertIn('前の段落で生まれた疑問・意外性・判断', src)

    def test_reader_question_must_have_function(self):
        src = inspect.getsource(pipeline.build_decision_prompt)
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
