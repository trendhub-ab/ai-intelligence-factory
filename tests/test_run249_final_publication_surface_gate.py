from __future__ import annotations

import inspect
import types
import unittest

import publication_contract
import run249_final_publication_surface_gate as r249
import runtime_layers


REAL_BAD_TITLE = 'このAIは、なぜローン審査を落としたのか？」相関頼みのXAIを打ち破る「因果的説明」の新アプローチ。'
REAL_BAD_SUMMARY = {
    'what': '従来のSHAP等の手法がデータ発生の因果構造を無視して誤った要因帰属を出す課題に対し、因果理論とパールの確率概念に基づきながら、',
    'why': '因果関係が定義された複雑なモデルや実稼働中の価格評価モデルにおいて、単なる相関にとどまらない因果的に整合した説明を可能にし、',
    'decision': '公開されているPython実装コードを活用し、因果グラフが定義できているモデルのサブセットを対象に、従来のSHAPとPCIの帰属結果を比較検証するPoCを開始する。',
}


class _Logger:
    def warning(self, *args, **kwargs):
        pass


def _builder(article, repo_name, repo_url, spdx_id, source, **kwargs):
    title = kwargs.get('title_text', '')
    summary = kwargs.get('reader_summary') or {}
    return r249._projection_from_parts(title, summary, article)


def _pipeline(summary=None, signals=None):
    return types.SimpleNamespace(
        logger=_Logger(),
        validate_human_appeal_gate=lambda parsed, peer_articles=None: ('ACCEPTABLE', []),
        build_clean_note_manuscript=_builder,
        build_reader_first_summary=lambda parsed: dict(summary or {
            'what': '因果関係を使ってAIの判断理由を説明する新しい手法が提案されました。',
            'why': '相関だけでは見誤る可能性がある説明を、因果構造に沿って検証できます。',
            'decision': 'まず限定したデータで従来手法と比較し、説明が変わる条件を確認します。',
        }),
        _reader_experience_signals=lambda article: dict(signals or {}),
    )


class Run249FinalPublicationSurfaceGateTests(unittest.TestCase):
    def test_real_ready_specimen_unbalanced_title_is_blocked(self):
        pipeline = _pipeline(summary=REAL_BAD_SUMMARY)
        r249.install(pipeline)
        state, issues = pipeline.validate_human_appeal_gate(
            {'title_text': REAL_BAD_TITLE, 'note_draft': '本文です。'}, []
        )
        self.assertEqual(state, 'WEAK')
        self.assertTrue(any('final_surface_title_unbalanced_kagi' in issue for issue in issues))

    def test_real_ready_specimen_summary_fragments_are_blocked(self):
        pipeline = _pipeline(summary=REAL_BAD_SUMMARY)
        r249.install(pipeline)
        state, issues = pipeline.validate_human_appeal_gate(
            {'title_text': '因果でAIの判断理由を説明する。', 'note_draft': '本文です。'}, []
        )
        self.assertEqual(state, 'WEAK')
        joined = '\n'.join(issues)
        self.assertIn('final_surface_summary_fragment:何が出た？', joined)
        self.assertIn('final_surface_summary_fragment:なぜ重要？', joined)
        self.assertNotIn('final_surface_summary_fragment:結論は？', joined)

    def test_multi_axis_weakness_on_final_projection_cannot_ready(self):
        signals = {
            'accessibility': 'REVIEW',
            'curiosity_pull': 'GOOD',
            'reader_enjoyment': 'REVIEW',
            'narrative_pull': 'GOOD',
            'jargon_translation': 'REVIEW',
            'non_engineer_core_clarity': 'REVIEW',
            'information_budget': 'REVIEW',
            'reader_temperature_rhythm': 'REVIEW',
        }
        pipeline = _pipeline(signals=signals)
        r249.install(pipeline)
        state, issues = pipeline.validate_human_appeal_gate(
            {'title_text': 'AIの説明を因果で見直す。', 'note_draft': '本文です。'}, []
        )
        self.assertEqual(state, 'WEAK')
        self.assertTrue(any('final_surface_multi_axis_reader_weakness' in issue for issue in issues))
        self.assertTrue(any('final_surface_non_engineer_access_failure' in issue for issue in issues))

    def test_complete_healthy_final_surface_preserves_acceptance(self):
        signals = {
            'accessibility': 'GOOD',
            'curiosity_pull': 'GOOD',
            'reader_enjoyment': 'GOOD',
            'narrative_pull': 'GOOD',
            'jargon_translation': 'GOOD',
            'non_engineer_core_clarity': 'GOOD',
            'information_budget': 'GOOD',
            'reader_temperature_rhythm': 'GOOD',
        }
        pipeline = _pipeline(signals=signals)
        r249.install(pipeline)
        state, issues = pipeline.validate_human_appeal_gate(
            {'title_text': 'AIの説明を因果で見直す。', 'note_draft': '本文です。'}, []
        )
        self.assertEqual(state, 'ACCEPTABLE')
        self.assertEqual(issues, [])

    def test_disclaimer_is_separated_from_supplemental_evidence_link(self):
        broken = (
            '### 補助Evidence\n\n'
            '- [https://replicate.com/docs/arxiv/about](https://replicate.com/docs/arxiv/about)'
            '※本記事に含まれる見解・提案は筆者個人の意見であり、特定の効果を保証するものではありません。'
        )
        repaired = r249.repair_final_public_manuscript(broken)
        self.assertIn(
            '](https://replicate.com/docs/arxiv/about)\n\n※本記事に含まれる見解・提案',
            repaired,
        )

    def test_install_is_idempotent_and_adds_no_provider_call_surface(self):
        pipeline = _pipeline()
        first = r249.install(pipeline)
        wrapped = pipeline.validate_human_appeal_gate
        second = r249.install(pipeline)
        self.assertIs(first, second)
        self.assertIs(pipeline.validate_human_appeal_gate, wrapped)
        self.assertTrue(pipeline.RUN249_ZERO_PROVIDER_CALLS)
        source = inspect.getsource(r249)
        self.assertNotIn('generateContent', source)
        self.assertNotIn('call_gemini', source)

    def test_runtime_and_publication_contract_include_run249(self):
        self.assertIn(
            'run249_final_publication_surface_gate.install',
            runtime_layers.RUNTIME_LAYER_ORDER,
        )
        self.assertIn(
            'run249_final_publication_surface_gate.py',
            publication_contract.PUBLICATION_POLICY_FILES,
        )
        idx249 = runtime_layers.RUNTIME_LAYER_ORDER.index(
            'run249_final_publication_surface_gate.install'
        )
        idx194 = runtime_layers.RUNTIME_LAYER_ORDER.index(
            'run194_publication_contract.install'
        )
        self.assertLess(idx249, idx194)


if __name__ == '__main__':
    unittest.main()
