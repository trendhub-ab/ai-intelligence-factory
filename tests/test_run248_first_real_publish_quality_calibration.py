from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

import publication_contract
import run181_eyecatch_visual_balance as r181
import run248_first_real_publish_quality_calibration as r248
import runtime_layers


class Run248FirstRealPublishQualityCalibrationTests(unittest.TestCase):
    def test_llm_token_is_never_split_and_fallback_prefers_large_type(self):
        title = 'AIでAIを採点する「LLMジャッジ」の落とし穴。'
        plan, highlight = r248._fallback_plan(title)
        self.assertEqual(''.join(plan['title_lines']), title)
        self.assertTrue(any('LLM' in line for line in plan['title_lines']))
        for left, right in zip(plan['title_lines'], plan['title_lines'][1:]):
            self.assertFalse(left.endswith(('L', 'LL')) and right.startswith('L'))
        self.assertGreaterEqual(plan['title_font_size'], 68)
        self.assertEqual(highlight, '落とし穴。')

    def test_deterministic_repair_restores_orange_and_keeps_approved_background(self):
        title = 'AIでAIを採点する「LLMジャッジ」の落とし穴。'
        summary = 'AI評価の統計手法に、尺度の床・天井が作る見かけ上の効果という落とし穴がある。'
        old_scale = r181.HIGHLIGHT_FONT_SCALE
        try:
            r181.HIGHLIGHT_FONT_SCALE = 1.20
            with tempfile.TemporaryDirectory() as tmp:
                repaired_path = Path(tmp) / 'repaired.png'
                baseline_path = Path(tmp) / 'baseline.png'
                # Both renderers call the exact same approved background/illustration function.
                import editorial_eyecatch as ee
                ee.generate_note_editorial_eyecatch(title, summary, str(baseline_path), category='MODELS', date_label='2026.09')
                r248.ensure_current_eyecatch_contract(
                    title, summary, str(repaired_path), category='MODELS', date_label='2026.09'
                )
                self.assertTrue(r248._has_orange_emphasis(str(repaired_path)))
                with Image.open(baseline_path).convert('RGB') as baseline, Image.open(repaired_path).convert('RGB') as repaired:
                    # Right-side illustration/background is outside the title surface and must be byte-identical pixelwise.
                    for point in ((900, 200), (1050, 320), (1160, 520), (1000, 640), (1250, 620)):
                        self.assertEqual(baseline.getpixel(point), repaired.getpixel(point))
        finally:
            r181.HIGHLIGHT_FONT_SCALE = old_scale

    def test_supplemental_evidence_becomes_clickable_and_digest_name_is_canonical(self):
        manuscript = '''本文。\n\n### Sources / Evidence\n- **主一次情報**: [Paper](https://example.com/paper)\n\n### 補助Evidence\n- https://arxiv.org/pdf/2608.27309.pdf\n- https://replicate.com/docs/arxiv/about\n\n※免責。\n\n---\n\n### 調査と判断の時間を減らしたい方へ\n\n無料記事では重要テーマを最後まで公開しています。会員向けには、意思決定DBと月次サマリーで、追うべき情報・Evidence・Actionを継続的に整理します。\n\n[会員向け意思決定DB＋月次サマリーを見る](https://example.com/join)'''
        repaired = r248.repair_public_manuscript(manuscript)
        self.assertIn('- [https://arxiv.org/pdf/2608.27309.pdf](https://arxiv.org/pdf/2608.27309.pdf)', repaired)
        self.assertIn('- [https://replicate.com/docs/arxiv/about](https://replicate.com/docs/arxiv/about)', repaired)
        self.assertNotIn('月次サマリー', repaired)
        self.assertIn('月次ダイジェスト', repaired)
        self.assertIn('採用・様子見・見送り', repaired)

    def test_multi_axis_reader_review_cannot_silently_pass(self):
        signals = {
            'accessibility': 'REVIEW',
            'curiosity_pull': 'REVIEW',
            'reader_enjoyment': 'REVIEW',
            'narrative_pull': 'REVIEW',
            'jargon_translation': 'REVIEW',
            'non_engineer_core_clarity': 'REVIEW',
            'information_budget': 'REVIEW',
            'reader_temperature_rhythm': 'REVIEW',
        }
        issues = r248.extra_reader_value_issues(signals)
        self.assertTrue(any('multi_axis_reader_weakness' in issue for issue in issues))
        self.assertTrue(any('non_engineer_access_failure' in issue for issue in issues))

    def test_first_real_publish_japanese_corruption_is_blocked(self):
        article = (
            'LLMジャッジは、開発速度をに高める手段です。'
            '研究チームが事前に主主要評価項目として登録しました。'
            '冷静に見極める眼砲が求められています。'
        )
        failures = r248.extra_japanese_surface_failures(article)
        joined = '\n'.join(failures)
        self.assertIn('particle_collision_wo_ni', joined)
        self.assertIn('duplicated_primary_modifier', joined)
        self.assertIn('malformed_lexeme_ganpou', joined)

    def test_runtime_and_publication_contract_include_run248(self):
        self.assertIn(
            'run248_first_real_publish_quality_calibration.install',
            runtime_layers.RUNTIME_LAYER_ORDER,
        )
        self.assertIn(
            'run248_first_real_publish_quality_calibration.py',
            publication_contract.PUBLICATION_POLICY_FILES,
        )


if __name__ == '__main__':
    unittest.main()
