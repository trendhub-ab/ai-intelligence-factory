import inspect
import unittest
from types import SimpleNamespace

import paid_db_launch_readiness as lr
import run164_ai_relevance_calibration as calibration


def rec(**overrides):
    base = dict(
        name="generic/tool",
        category="DEVTOOLS",
        source_summary="Product Review from verified primary evidence",
        short_rationale="一般的なソフトウェア機能を提供する。",
        best_for="AI導入を進める企業。",
        avoid_for="特別な制約なし。",
        main_risk="通常の運用リスク。",
        adoption_status="ADOPT",
        production_readiness="HIGH",
        evidence_confidence="HIGH",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class Run164AIRelevanceVocabularyCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        calibration.install_on(lr)

    def assert_ai(self, **kwargs):
        self.assertTrue(lr.is_ai_relevant(rec(**kwargs)))

    def assert_non_ai(self, **kwargs):
        self.assertFalse(lr.is_ai_relevant(rec(**kwargs)))

    def test_catalog_false_negative_phrases_are_recovered(self):
        cases = (
            dict(category="DATA", short_rationale="本番Vector DBとして運用する。"),
            dict(category="INFRA", short_rationale="大規模な分散学習を支える基盤。"),
            dict(category="INFRA", short_rationale="汎用推論ランタイムとして利用する。"),
            dict(category="PRODUCT", short_rationale="IDE内のコーディングエージェント。"),
            dict(category="DEVTOOLS", name="TDD-Agent: Test-Driven Reasoning for Code Generation"),
            dict(category="SECURITY", name="Chain-of-Thought Reasoning In The Wild Is Not Always Faithful"),
            dict(category="SECURITY", name="Fragility of Self-Improving Agents under Distribution Shift"),
            dict(category="DATA", short_rationale="調査・リサーチAgentとしてEvidenceを統合する。"),
            dict(category="DEVTOOLS", short_rationale="データサイエンスプロジェクトの標準構成。"),
            dict(category="PRODUCT", name="Chatbot UI", short_rationale="chatbot UIを提供する。"),
        )
        for case in cases:
            with self.subTest(case=case):
                self.assert_ai(**case)

    def test_generic_software_precision_guards_remain_non_ai(self):
        cases = (
            dict(name="dioxuslabs/taffy", category="DEVTOOLS", short_rationale="Rust製CSSレイアウトライブラリ。"),
            dict(name="GPU Offload in Rust", category="INFRA", short_rationale="汎用GPUオフロード基盤。"),
            dict(name="TopoIntent", category="SECURITY", short_rationale="ネットワーク構成を検証するセキュリティツール。"),
            dict(name="Deployment Agent", category="DEVTOOLS", short_rationale="デプロイ処理を自動化するagent。"),
            dict(name="Generic Model Helper", category="DEVTOOLS", short_rationale="設定モデルを管理する一般ライブラリ。"),
        )
        for case in cases:
            with self.subTest(case=case):
                self.assert_non_ai(**case)

    def test_bare_ml_token_is_not_added_as_global_signal(self):
        self.assert_non_ai(name="HTML parser", category="DEVTOOLS", short_rationale="HTML文書を解析する。")
        self.assertNotIn(r"(?<![A-Za-z0-9_])ML(?![A-Za-z0-9_])", lr.AI_RELEVANCE_PATTERNS)

    def test_negative_statement_still_overrides_native_category(self):
        item = rec(
            category="MODEL",
            source_summary="AI固有の技術ではない。",
            short_rationale="一般的な設定管理用ライブラリ。",
        )
        self.assertFalse(lr.is_ai_relevant(item))

    def test_install_is_idempotent_and_zero_provider(self):
        before = tuple(lr.AI_RELEVANCE_PATTERNS)
        calibration.install_on(lr)
        after = tuple(lr.AI_RELEVANCE_PATTERNS)
        self.assertEqual(before, after)
        source = inspect.getsource(calibration)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("call_gemini", source)
        self.assertNotIn("google.genai", source)
        self.assertEqual(lr.POLICY_VERSION, "run164-paid-db-launch-relevance-precision-v4")


if __name__ == "__main__":
    unittest.main(verbosity=2)
