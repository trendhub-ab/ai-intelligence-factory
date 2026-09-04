from __future__ import annotations

import unittest

import run227_japanese_surface_integrity as run227


class Run227JapaneseSurfaceIntegrityTests(unittest.TestCase):
    def test_run24_predicate_missing_escape_is_blocked(self):
        article = "この推論を確かめるために比較しました。\n\n結果はでした。\n\n次に詳細を見ます。"
        failures = run227.japanese_surface_failures(article)
        self.assertTrue(any("predicate_missing" in row for row in failures))

    def test_run24_particle_collision_escape_is_blocked(self):
        article = "精度を半分に落とせば、AIモデルの計算はに速くなる――理論上はそう見えます。"
        failures = run227.japanese_surface_failures(article)
        self.assertTrue(any("particle_collision_ha_ni" in row for row in failures))

    def test_run24_adapt_apply_transitivity_escape_is_blocked(self):
        article = "分散学習でFP4を過度に適応すると学習が失敗するため、慎重な検証が必要です。"
        failures = run227.japanese_surface_failures(article)
        self.assertTrue(any("transitivity_adapt_vs_apply" in row for row in failures))

    def test_valid_neighboring_japanese_passes(self):
        samples = (
            "結果は明確でした。",
            "結論は次の通りです。",
            "AIモデルの計算はさらに速くなる可能性があります。",
            "Aは日本語で説明します。",
            "この結果には注意が必要です。",
            "モデルが新しい環境に適応するまで時間が必要です。",
            "方式を環境に適応させる必要があります。",
            "FP4を適用すると精度条件が変わります。",
        )
        for article in samples:
            with self.subTest(article=article):
                self.assertEqual(run227.japanese_surface_failures(article), [])

    def test_code_is_not_scanned(self):
        article = (
            "本文は自然です。\n\n```text\n結果はでした。\n計算はに速くなる\nFP4を適応する\n```\n\n"
            "`結果はでした。`という文字列をテストします。"
        )
        self.assertEqual(run227.japanese_surface_failures(article), [])

    def test_install_is_idempotent_and_blocks_before_ready(self):
        class DummyLogger:
            def warning(self, *args, **kwargs):
                pass

        class DummyPipeline:
            logger = DummyLogger()

            @staticmethod
            def build_decision_prompt(*args, **kwargs):
                return "BASE"

            @staticmethod
            def validate_fact_gate(
                parsed,
                repo_name,
                source_context="",
                source="",
                evidence_metadata=None,
                source_info=None,
                freshness=None,
                output_truncated=False,
            ):
                return True, []

            @staticmethod
            def build_dynamic_retry_instruction(reason_rows):
                return "RETRY", []

        pipe = DummyPipeline()
        run227.install(pipe)
        first_prompt = pipe.build_decision_prompt()
        run227.install(pipe)
        second_prompt = pipe.build_decision_prompt()
        self.assertEqual(first_prompt, second_prompt)
        self.assertEqual(second_prompt.count("日本語Surface Integrity / Run227"), 1)

        parsed = {"note_draft": "結果はでした。"}
        ok, failures = pipe.validate_fact_gate(parsed, "x")
        self.assertFalse(ok)
        self.assertTrue(any("malformed_japanese_surface:" in row for row in failures))

        retry, _ = pipe.build_dynamic_retry_instruction(
            [{"message": "malformed_japanese_surface:predicate_missing: obvious broken Japanese remains"}]
        )
        self.assertIn("局所修正", retry)
        self.assertIn("新しい数値・人物・因果", retry)


if __name__ == "__main__":
    unittest.main()
