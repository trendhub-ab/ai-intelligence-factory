import unittest

import pipeline
from local_skills.evidence_boundary import _sanitize_field


class Run152PublicationAndBoundaryPrecisionTests(unittest.TestCase):
    def test_complete_processing_step_is_not_intro_overclaim(self):
        parsed = {
            "title_text": "Rolling-WAM",
            "note_draft": (
                "# Rolling-WAM\n\n"
                "ロボットが動く際、次の瞬間に行う制御に必要な計算だけを完全に終わらせ、"
                "先の未来予測のための計算は途中の段階で引き継ぎながら進めます。"
            ),
            "action_text": "限定した検証で比較する。",
            "score": 70,
        }
        state, issues = pipeline.validate_publication_readiness_gate(
            parsed,
            source_context="abstract experimental research prototype",
            source_info={"sufficient": True},
        )
        self.assertEqual("PASS", state)
        self.assertNotIn("intro_overclaim", issues)

    def test_complete_resolution_claim_still_blocks_weak_evidence_intro(self):
        parsed = {
            "title_text": "研究プロトタイプ",
            "note_draft": "# 研究プロトタイプ\n\nこの手法で遅延問題を完全に解決する。",
            "action_text": "限定した検証で比較する。",
            "score": 70,
        }
        state, issues = pipeline.validate_publication_readiness_gate(
            parsed,
            source_context="abstract experimental research prototype",
            source_info={"sufficient": True},
        )
        self.assertEqual("REVIEW", state)
        self.assertIn("intro_overclaim", issues)

    def test_numeric_removal_drops_broken_from_to_parenthetical(self):
        value = (
            "タスク成功率をほぼ落とすことなく、推論レイテンシを大幅に削減"
            "（特定測定例で120msから25msへ）した研究成果である。"
        )
        sanitized, removed = _sanitize_field("decision_reason", value, set())
        self.assertIn("120ms", removed)
        self.assertIn("25ms", removed)
        self.assertNotIn("からへ", sanitized)
        self.assertNotIn("（特定測定例で", sanitized)
        self.assertEqual(
            "タスク成功率をほぼ落とすことなく、推論レイテンシを大幅に削減した研究成果である。",
            sanitized,
        )


if __name__ == "__main__":
    unittest.main()
