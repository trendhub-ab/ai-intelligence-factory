import json
from pathlib import Path
import unittest

from technology_comment_shadow import (
    TechnologyCommentShadowError,
    build_shadow_prompt,
    compare_shadow_to_baseline,
    parse_shadow_output,
    score_values,
)


FIXTURE = Path("tests/fixtures/technology_comment_shadow_live.json")


class TechnologyCommentShadowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.baseline = self.fixture["baseline"]

    def test_prompt_is_shadow_only_and_evidence_bounded(self):
        prompt = build_shadow_prompt(self.fixture)
        self.assertIn("本番DBへ書き込む権限はありません", prompt)
        self.assertIn("EVIDENCE — sole factual surface", prompt)
        self.assertIn("4キー以外は禁止", prompt)

    def test_parse_rejects_extra_key(self):
        payload = dict(self.baseline)
        payload["extra"] = "forbidden"
        with self.assertRaisesRegex(TechnologyCommentShadowError, "shadow_shape_invalid"):
            parse_shadow_output(json.dumps(payload, ensure_ascii=False))

    def test_forbidden_claim_penalizes_evidence_alignment(self):
        bad = dict(self.baseline)
        bad["short_rationale"] = "公開情報によりコスト削減と本番で安定した運用が確認されているため採用する。"
        scores, _ = score_values(bad, self.fixture)
        self.assertLess(scores.evidence_alignment, 80)

    def test_tie_is_never_promoted(self):
        result = compare_shadow_to_baseline(self.baseline, self.baseline, self.fixture)
        self.assertFalse(result["deterministic_gate_passed"])
        self.assertFalse(result["promotion_candidate"])
        self.assertEqual("baseline_wins", result["tie_policy"])
        self.assertFalse(result["automatic_promotion_allowed"])
        self.assertFalse(result["persist_allowed"])
        self.assertEqual(0, result["business_writes"])

    def test_candidate_with_worse_axis_cannot_pass(self):
        challenger = dict(self.baseline)
        challenger["best_for"] = "重要です。"
        result = compare_shadow_to_baseline(self.baseline, challenger, self.fixture)
        self.assertFalse(result["deterministic_gate_passed"])
        self.assertTrue(result["worse_axes"] or any(result["challenger_style_violations"].values()))

    def test_comparison_never_authorizes_automatic_promotion(self):
        challenger = {
            "main_risk": "実験段階のバッチ実行は安定版まで仕様変更の可能性があり、公開テストだけでは本番信頼性を判断できない。",
            "best_for": "バッチで反復リクエストをまとめ、公開テスト条件に近い環境でレイテンシ差を検証する用途。",
            "avoid_for": "仕様固定や本番信頼性が必要な運用と、公開テスト外へレイテンシ結果を一般化する用途。",
            "short_rationale": "バッチ条件下ではレイテンシ改善が示されたが、実験機能で本番信頼性は未確認のため、まず限定検証し本番採用は保留する。",
        }
        result = compare_shadow_to_baseline(self.baseline, challenger, self.fixture)
        self.assertFalse(result["automatic_promotion_allowed"])
        self.assertTrue(result["human_or_independent_semantic_review_required"])


if __name__ == "__main__":
    unittest.main()
