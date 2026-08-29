import inspect
import unittest
from types import SimpleNamespace

import paid_db_launch_readiness as lr


def rec(**overrides):
    base = dict(
        name="generic/tool",
        category="DEVTOOLS",
        source_summary="Product Review from verified primary evidence",
        short_rationale="一般的なソフトウェア機能を提供する。",
        best_for="自社のAI導入・開発・運用で具体的に必要としているチーム。",
        avoid_for="特別な制約なし。",
        main_risk="通常の運用リスク。",
        adoption_status="ADOPT",
        production_readiness="HIGH",
        evidence_confidence="HIGH",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class Run155AIRelevancePrecisionTests(unittest.TestCase):
    def test_ai_native_taxonomy_recovers_multimodal_without_literal_ai_token(self):
        item = rec(
            name="THUDM/CogVideo",
            category="MULTIMODAL",
            short_rationale="テキストから動画を生成するモデル群と関連実装を提供する。",
        )
        self.assertTrue(lr.is_ai_relevant(item))

    def test_japanese_adjacent_llm_token_is_detected_for_infra(self):
        item = rec(
            name="vllm-project/vllm",
            category="INFRA",
            short_rationale="LLM推論・サービングのスループットと効率を高める推論エンジン。",
        )
        self.assertTrue(lr.is_ai_relevant(item))
        self.assertTrue(lr.is_front_shelf(item))

    def test_product_requires_substantive_ai_signal_and_dify_passes(self):
        item = rec(
            name="langgenius/dify",
            category="PRODUCT",
            short_rationale="LLMアプリ、ワークフロー、エージェントをGUIとAPIで構築・運用できるAIアプリ基盤。",
        )
        self.assertTrue(lr.is_ai_relevant(item))

    def test_ai_security_with_japanese_adjacent_llm_is_detected(self):
        item = rec(
            name="The Model's Tell",
            category="SECURITY",
            adoption_status="TEST",
            production_readiness="LOW",
            short_rationale="LeakGaugeはLLMのprefillトークン確率からコンテキスト漏洩攻撃シグナルを検知する。",
        )
        self.assertTrue(lr.is_ai_relevant(item))
        self.assertFalse(lr.is_front_shelf(item))

    def test_face_recognition_security_is_detected(self):
        item = rec(
            name="Steering the Flow",
            category="SECURITY",
            short_rationale="顔認識モデルへの高精度なモデル逆転攻撃手法を評価する。",
        )
        self.assertTrue(lr.is_ai_relevant(item))

    def test_generic_taffy_remains_non_ai_even_with_best_for_ai_boilerplate(self):
        item = rec(
            name="dioxuslabs/taffy",
            category="DEVTOOLS",
            source_summary="Rust layout library implementing Flexbox and CSS Grid for application interfaces.",
            short_rationale="Servo、Bevy、Zed等で採用されるクロスプラットフォームレイアウトライブラリ。",
            best_for="自社のAI導入・開発・運用で具体的に必要としているチーム。",
        )
        self.assertFalse(lr.is_ai_relevant(item))
        self.assertFalse(lr.is_front_shelf(item))

    def test_explicit_non_ai_statement_overrides_native_category_without_separate_signal(self):
        item = rec(
            name="generic-model-helper",
            category="MODEL",
            source_summary="AI固有の技術ではない。",
            short_rationale="一般的な設定ファイル管理用の補助ライブラリ。",
        )
        self.assertFalse(lr.is_ai_relevant(item))

    def test_best_for_boilerplate_is_not_ai_relevance_surface(self):
        item = rec(
            name="generic/product",
            category="PRODUCT",
            source_summary="General purpose application utility.",
            short_rationale="一般的な業務向けユーティリティ。",
            best_for="AI導入を進める企業。",
        )
        self.assertFalse(lr.is_ai_relevant(item))

    def test_run155_adds_no_model_call_site(self):
        source = inspect.getsource(lr)
        self.assertNotIn("generate_content", source)
        self.assertNotIn("call_gemini", source)
        self.assertNotIn("google.genai", source)
        self.assertNotIn("GEMINI_API_KEY", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
