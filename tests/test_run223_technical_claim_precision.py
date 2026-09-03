from __future__ import annotations

import unittest

import run223_technical_claim_precision as run223


class Run223TechnicalClaimPrecisionTests(unittest.TestCase):
    def test_operation_specific_maintain_order_collapse_is_rejected(self):
        source = '''
        group_by(..., maintain_order=True)
        df.join(other, on="id", maintain_order="left")
        '''
        bad = '''
        joinやgroup_byで順序が必要なら `maintain_order=True` を追加してください。
        '''
        good = '''
        group_byなら `maintain_order=True`、左側の行順を維持したいjoinなら
        `maintain_order="left"` を指定します。
        '''
        self.assertTrue(run223.operation_parameter_failures(bad, source))
        self.assertEqual(run223.operation_parameter_failures(good, source), [])

    def test_blanket_conversion_prohibition_is_rejected_but_scoped_wording_passes(self):
        bad = "Polars 2.0ではこうした曖昧な型変換を禁止し、不整合なら止めます。"
        good = "Polars 2.0では、一部の暗黙的な型変換をより厳格にし、情報が失われる可能性のある変換ではエラーになります。"
        self.assertTrue(run223.broad_conversion_failures(bad))
        self.assertEqual(run223.broad_conversion_failures(good), [])

    def test_expected_multiplier_requires_modality_and_variability(self):
        source = "In aggregate we expect the streaming engine to be easily 5x faster across workloads."
        bad = "ストリーミングエンジンで全体として5倍高速化します。"
        good = (
            "Polarsチームは、ストリーミングエンジンについて全体として5倍程度の高速化を期待しています。"
            "ただし、実際の改善幅は処理内容や実行環境によって変わります。"
        )
        self.assertTrue(run223.multiplier_scope_failures(bad, source))
        self.assertEqual(run223.multiplier_scope_failures(good, source), [])

    def test_primary_source_date_uses_only_explicit_source_metadata(self):
        article = "- **公開・更新**: 2026-09-03"
        explicit = {"primary_source_published_date": "2026-09-02"}
        self.assertTrue(run223.source_date_failures(article, explicit, {}, {}))
        correct = "- **公開・更新**: 2026-09-02"
        self.assertEqual(run223.source_date_failures(correct, explicit, {}, {}), [])

        # Generic operational dates must never be treated as the first-party publication date.
        operational_only = {"analysis_date": "2026-09-03", "collected_at": "2026-09-03T16:00:00Z", "date": "2026-09-03"}
        self.assertEqual(run223.source_date_failures(article, operational_only, {}, {}), [])

    def test_ambiguous_explicit_primary_dates_fail_open_to_prompt_not_guess(self):
        metadata = {
            "primary_source_published_date": "2026-09-02",
            "nested": {"source_published_date": "2026-09-01"},
        }
        article = "公開・更新: 2026-09-03"
        self.assertEqual(run223.source_date_failures(article, metadata, {}, {}), [])

    def test_obvious_japanese_particle_typo_is_blocked(self):
        bad = "ストリーミング処理によるな処理速度を手に入れます。"
        self.assertTrue(run223.malformed_japanese_failures(bad))
        good = "ストリーミング処理による高速化の恩恵を検証します。"
        self.assertEqual(run223.malformed_japanese_failures(good), [])

    def test_polars_audit_fixed_excerpt_passes_all_run223_guards(self):
        source = '''
        By Ritchie Vink on Wed, 2 Sept 2026.
        In aggregate we expect the streaming engine to be easily 5x faster.
        group_by(..., maintain_order=True)
        join(..., maintain_order="left")
        '''
        article = '''
        # Polars 2.0の静かな進化

        - **公開・更新**: 2026-09-02

        Polarsチームはストリーミングエンジンについて全体として5倍程度の高速化を期待していると説明しています。
        ただし、実際の改善幅は処理内容や実行環境によって変わります。

        group_byなら `maintain_order=True`、左側の行順を維持したいjoinなら `maintain_order="left"` を使えます。

        Polars 2.0では、一部の暗黙的な型変換をより厳格にし、情報が失われる可能性のある変換などではエラーを出す方向です。
        '''
        parsed = {"note_draft": article}
        failures = run223.technical_claim_failures(
            parsed,
            source,
            evidence_metadata={"primary_source_published_date": "2026-09-02"},
        )
        self.assertEqual(failures, [])

    def test_install_adds_prompt_and_blocks_extra_failure_without_changing_base_failure(self):
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
        run223.install(pipe)
        prompt = pipe.build_decision_prompt()
        self.assertIn("技術Claim精度 / Run223", prompt)
        parsed = {"note_draft": "ストリーミング処理によるな処理速度です。"}
        ok, failures = pipe.validate_fact_gate(parsed, "x")
        self.assertFalse(ok)
        self.assertTrue(any("malformed_japanese_particle:" in row for row in failures))


if __name__ == "__main__":
    unittest.main()
