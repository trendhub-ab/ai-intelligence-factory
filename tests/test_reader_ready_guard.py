import unittest

import gate_reasoning as gr
import reader_value_review_bridge as bridge


class DummyPipeline:
    GATE_SEVERITY_HARD = "HARD_BLOCK"
    GATE_SEVERITY_REVIEW = "REVIEW"
    REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH = "PUB_SCORE_NARRATIVE_MISMATCH"
    REASON_CODE_APPEAL_DECISION_VOICE_LOSS = "APPEAL_DECISION_VOICE_LOSS"

    def __init__(self, signals=None, human_state="ACCEPTABLE", human_issues=None):
        self.signals = signals or {}
        self.human_state = human_state
        self.human_issues = list(human_issues or [])
        self.retry_calls = 0

    def _reader_experience_signals(self, article):
        return dict(self.signals)

    def validate_human_appeal_gate(self, parsed, peer_articles=None):
        return self.human_state, list(self.human_issues)

    def should_attempt_dynamic_retry(self, rows, evidence_result, candidate_origin="new"):
        self.retry_calls += 1
        return True, "original_retry_policy"

    def build_decision_prompt(self, *args, **kwargs):
        return "PROMPT"

    def build_dynamic_retry_instruction(self, rows):
        return "RETRY", []


class ReaderReadyGuardTests(unittest.TestCase):
    def test_0300_real_shape_is_blocking_reader_access(self):
        signals = {
            "accessibility": "REVIEW",
            "curiosity_pull": "REVIEW",
            "reader_enjoyment": "REVIEW",
            "narrative_pull": "GOOD",
            "jargon_translation": "GOOD",
            "non_engineer_core_clarity": "GOOD",
            "information_budget": "REVIEW",
            "reader_temperature_rhythm": "GOOD",
            "opening_non_engineer_access": "REVIEW",
            "plain_language_bridge": "REVIEW",
        }
        p = DummyPipeline(signals=signals)
        issues = bridge._material_reader_value_issues(p, "article")
        access_issue = next(x for x in issues if "non_engineer_access_failure" in x)
        code = gr.reason_code(access_issue, "human_appeal")
        severity = gr.classify_gate_reason_severity("human_appeal", access_issue, code)
        self.assertEqual(code, gr.REASON_CODE_READER_NON_ENGINEER_ACCESS)
        self.assertEqual(severity, gr.GATE_SEVERITY_REVIEW)

    def test_specialist_article_with_real_reader_bridges_is_not_blocked(self):
        signals = {
            "accessibility": "GOOD",
            "reader_enjoyment": "GOOD",
            "narrative_pull": "GOOD",
            "information_budget": "GOOD",
            "reader_temperature_rhythm": "GOOD",
            "opening_non_engineer_access": "GOOD",
            "plain_language_bridge": "GOOD",
        }
        p = DummyPipeline(signals=signals)
        self.assertEqual(bridge._material_reader_value_issues(p, "technical article"), [])

    def test_human_appeal_weak_can_never_be_ready_without_review_reason(self):
        p = DummyPipeline(human_state="WEAK", human_issues=["headline_flattened"])
        bridge.install(p)
        state, issues = p.validate_human_appeal_gate({"note_draft": "article"})
        weak_issue = "reader_value_review:human_appeal_weak"
        self.assertEqual(state, "WEAK")
        self.assertIn(weak_issue, issues)
        code = gr.reason_code(weak_issue, "human_appeal")
        self.assertEqual(
            gr.classify_gate_reason_severity("human_appeal", weak_issue, code),
            gr.GATE_SEVERITY_REVIEW,
        )

    def test_reader_review_delegates_to_existing_bounded_retry_policy(self):
        p = DummyPipeline()
        bridge.install(p)
        rows = [{
            "message": "reader_value_review:non_engineer_access_failure (...) ",
            "severity": "REVIEW",
            "gate": "human_appeal",
        }]
        self.assertEqual(
            p.should_attempt_dynamic_retry(rows, {}, "new"),
            (True, "original_retry_policy"),
        )
        self.assertEqual(p.retry_calls, 1)

    def test_reader_soft_only_stays_zero_spend(self):
        p = DummyPipeline()
        bridge.install(p)
        rows = [{
            "message": "reader_value_review:dense_report_cluster (...)",
            "severity": "SOFT_QUALITY",
            "gate": "human_appeal",
        }]
        self.assertEqual(
            p.should_attempt_dynamic_retry(rows, {}, "new"),
            (False, "reader_value_review_no_retry"),
        )
        self.assertEqual(p.retry_calls, 0)


if __name__ == "__main__":
    unittest.main()
