import inspect
import unittest
import pipeline


class Run136ReaderValuePriorityTests(unittest.TestCase):
    def test_article_prompt_has_no_3200_soft_ceiling(self):
        src = inspect.getsource(pipeline.build_decision_prompt)
        self.assertNotIn("3,200字", src)
        self.assertNotIn("2,200〜3,000字", src)
        self.assertIn("文字数を品質目標にしない", src)

    def test_information_budget_is_not_character_count_gate(self):
        src = inspect.getsource(pipeline._reader_experience_signals)
        self.assertNotIn("article_char_count > 3200", src)
        self.assertIn("max_explanatory_run >= 4", src)
        self.assertIn("unique_implementation_identifiers", src)

    def test_hard_retry_prioritizes_local_fact_repair(self):
        rows = [{"reason_code": pipeline.REASON_CODE_PUB_INTRO_OVERCLAIM, "message": "intro_overclaim", "gate": "publication", "severity": pipeline.GATE_SEVERITY_HARD}]
        instruction, _ = pipeline.build_dynamic_retry_instruction(rows)
        self.assertIn("記事全体の短文化・全面再構成を同時に行わず", instruction)
        self.assertNotIn("1,800〜2,300字", instruction)
        self.assertNotIn("2,300字を超えて", instruction)

    def test_hard_retry_forbids_new_guarantees(self):
        rows = [{"reason_code": pipeline.REASON_CODE_FACT_UNSUPPORTED_CLAIM, "message": "unsupported claim", "gate": "fact", "severity": pipeline.GATE_SEVERITY_HARD}]
        instruction, _ = pipeline.build_dynamic_retry_instruction(rows)
        self.assertIn("安全性が担保される", instruction)
        self.assertIn("一次情報より強い保証", instruction)

    def test_reader_value_keeps_length_observable_only(self):
        article = ("## 身近な入口\n\n普通の読者にも分かる説明です。\n\n## 判断\n\n私なら小さく試します。\n") * 150
        signals = pipeline._reader_experience_signals(article)
        self.assertGreater(signals["article_char_count"], 3200)
        self.assertTrue(signals["soft_only"])


if __name__ == "__main__":
    unittest.main()
