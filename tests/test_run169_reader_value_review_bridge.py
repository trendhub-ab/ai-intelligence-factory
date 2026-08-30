import inspect
import unittest
from pathlib import Path

import pipeline
import reader_value_review_bridge as bridge


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "run103_reader_value"
REAL_READY_FIXTURES = (
    "glm_5_3.md",
    "cursor_spacex.md",
    "genai_sophistication.md",
)


class Run169ReaderValueReviewBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original_human_appeal = pipeline.validate_human_appeal_gate
        cls.original_retry = pipeline.should_attempt_dynamic_retry
        cls.original_build_prompt = pipeline.build_decision_prompt
        cls.original_build_retry_instruction = pipeline.build_dynamic_retry_instruction
        cls.had_installed_attr = hasattr(pipeline, bridge._INSTALLED_ATTR)
        cls.old_installed_attr = getattr(pipeline, bridge._INSTALLED_ATTR, None)
        bridge.install(pipeline)

    @classmethod
    def tearDownClass(cls):
        pipeline.validate_human_appeal_gate = cls.original_human_appeal
        pipeline.should_attempt_dynamic_retry = cls.original_retry
        pipeline.build_decision_prompt = cls.original_build_prompt
        pipeline.build_dynamic_retry_instruction = cls.original_build_retry_instruction
        if cls.had_installed_attr:
            setattr(pipeline, bridge._INSTALLED_ATTR, cls.old_installed_attr)
        elif hasattr(pipeline, bridge._INSTALLED_ATTR):
            delattr(pipeline, bridge._INSTALLED_ATTR)

    def _article(self, name):
        return (FIXTURE_DIR / name).read_text(encoding="utf-8")

    def test_three_real_run103_ready_articles_hit_material_dense_report_cluster(self):
        for name in REAL_READY_FIXTURES:
            with self.subTest(name=name):
                article = self._article(name)
                sig = pipeline._reader_experience_signals(article)
                self.assertEqual("REVIEW", sig["reader_enjoyment"])
                self.assertEqual("REVIEW", sig["narrative_pull"])
                self.assertEqual("REVIEW", sig["information_budget"])
                self.assertEqual("REVIEW", sig["reader_temperature_rhythm"])
                issues = bridge._material_reader_value_issues(pipeline, article)
                self.assertTrue(any("dense_report_cluster" in x for x in issues), issues)

    def test_real_run103_ready_articles_are_bridged_to_human_appeal_review(self):
        for name in REAL_READY_FIXTURES:
            with self.subTest(name=name):
                article = self._article(name)
                state, issues = pipeline.validate_human_appeal_gate({"note_draft": article}, [])
                self.assertNotEqual("ACCEPTABLE", state)
                self.assertTrue(any(bridge.READER_VALUE_MARKER in x for x in issues), issues)

                reason_rows = pipeline.map_gate_reasons("human_appeal", issues)
                self.assertEqual(pipeline.GATE_DISPOSITION_REVIEW, pipeline.gate_reason_disposition(reason_rows))

    def test_reader_value_only_review_never_spends_gemini_quality_retry(self):
        article = self._article("genai_sophistication.md")
        _, issues = pipeline.validate_human_appeal_gate({"note_draft": article}, [])
        reader_issues = [x for x in issues if bridge.READER_VALUE_MARKER in x]
        self.assertTrue(reader_issues)
        rows = pipeline.map_gate_reasons("human_appeal", reader_issues)

        retry, reason = pipeline.should_attempt_dynamic_retry(rows, {"sufficiency": "SUFFICIENT"}, "new")
        self.assertFalse(retry)
        self.assertEqual("reader_value_review_no_retry", reason)

    def test_existing_non_reader_review_can_still_use_original_retry_policy(self):
        reader_rows = pipeline.map_gate_reasons(
            "human_appeal",
            [bridge.READER_VALUE_MARKER + "dense_report_cluster"],
        )
        mixed_rows = reader_rows + [{
            "reason_code": "APPEAL_DECISION_VOICE_MISSING",
            "severity": pipeline.GATE_SEVERITY_REVIEW,
            "message": "decision voice missing",
            "gate": "human_appeal",
        }]
        # Access through the class so the stored plain function is not descriptor-bound to self.
        expected = type(self).original_retry(mixed_rows, {"sufficiency": "SUFFICIENT"}, "new")
        actual = pipeline.should_attempt_dynamic_retry(mixed_rows, {"sufficiency": "SUFFICIENT"}, "new")
        self.assertEqual(expected, actual)

    def test_calm_good_article_is_not_forced_into_review(self):
        article = '''AIエージェントに社内システムを触らせるとき、便利さより先に気になることがあります。「どこまで触らせる？」です。人に合鍵を渡すとき、家じゅう全部の鍵を束で渡さないのと同じです。

最小権限は、そのAIが今の仕事に必要な範囲だけアクセスできるようにする考え方です。権限を狭くすると、誤操作や侵害が起きたときの被害範囲も狭めやすくなります。ただし、権限を絞れば安全が保証されるわけではありません。ログ監視や承認フローなど別の対策も必要です。

私なら、まず機密情報を扱わない作業だけで試し、実際に必要だった権限を記録してから範囲を広げます。便利さを先に最大化するより、必要な鍵を一つずつ増やす方が現実的です。'''
        self.assertEqual([], bridge._material_reader_value_issues(pipeline, article))

    def test_bridge_adds_zero_gemini_call_sites(self):
        pipeline_src = inspect.getsource(pipeline)
        bridge_src = inspect.getsource(bridge)
        self.assertEqual(7, pipeline_src.count("_generate_via_chat("))
        self.assertEqual(1, pipeline_src.count("genai.Client("))
        self.assertNotIn("_generate_via_chat(", bridge_src)
        self.assertNotIn("genai.Client(", bridge_src)


if __name__ == "__main__":
    unittest.main()
