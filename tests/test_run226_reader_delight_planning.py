import inspect
from pathlib import Path
import types
import unittest

import editorial_quality_memory
import publication_contract
import run226_reader_delight_planning as run226


ROOT = Path(__file__).resolve().parents[1]


class Run226ReaderDelightPlanningTests(unittest.TestCase):
    def test_contract_contains_editorial_blueprint_and_five_lenses(self):
        text = run226.editorial_planning_contract()
        for token in (
            run226.EDITORIAL_BLUEPRINT_MARKER,
            'Target Reader',
            'Reader Question',
            'Why Now',
            'Central Conclusion',
            'Evidence Anchor',
            'Capability Boundary',
            'Terminology Budget',
            'Reader Decision',
            'Reader Tension',
            'Discovery',
            'Concrete Consequence',
            'Explanation Bridge',
            'Editorial Point of View',
        ):
            self.assertIn(token, text)

    def test_capability_boundary_does_not_turn_missing_evidence_into_cannot(self):
        text = run226.editorial_planning_contract()
        self.assertIn('「できる」「できない」「まだ分からない」を分離', text)
        self.assertIn('「できない」は禁止・非対応・制約がSOURCE BOUNDARYで明示される場合だけ', text)
        self.assertIn('Evidenceがない場合は「未確認/まだ分からない」', text)

    def test_contract_is_evidence_bounded_and_rejects_invented_specificity(self):
        text = run226.editorial_planning_contract()
        self.assertIn('SOURCE BOUNDARY', text)
        self.assertIn('数値baseline', text)
        self.assertIn('競合roadmap', text)
        self.assertIn('多数派認識を創作しない', text)
        self.assertIn('baselineと換算後の値の双方', text)
        self.assertIn('暗算で分かりやすい例を捏造しない', text)

    def test_contract_does_not_turn_human_voice_into_numeric_template(self):
        text = run226.editorial_planning_contract()
        self.assertIn('回数ノルマを設けない', text)
        self.assertIn('固定Hook分類を均等配分しない', text)
        self.assertIn('本文の固定順序にしない', text)
        self.assertIn('style countだけを新しいHard Gateにしない', text)
        self.assertIn('比喩・問い・scene・会話調は自然に理解を助ける場合だけ任意', text)
        self.assertIn('Blueprintは新しいHard Gateではない', text)
        self.assertIn('必要な専門概念・制約・判断材料を個数合わせのために削らない', text)

    def test_deconflicts_legacy_fixed_count_writer_rules(self):
        legacy = '\n'.join(
            [
                '記事全体の温度を1〜2個の口語句で済ませず、硬い説明が2段落続いたら次の段落では、追加説明を足さず、既存文を「読者の判断／具体場面／平易な一言」のどれかへ置き換えて人間の言葉へ戻す。',
                'この無料ARTICLEで読者が本当に覚える専門概念を内部で原則2〜3個に絞る。4個目がないとDecisionを誤解する場合だけ4個まで許す。',
                'ARTICLE本文で説明する中核概念は原則2〜3個、実装識別子・規格名・コマンド名は意思決定に必要なものだけに限定し、列挙で専門性を演出しない。',
                '手順・機能・注意点の列挙はそれぞれ最大3項目まで。',
                '短文を3つ以上連打して広告コピーのように煽らない。',
            ]
        )
        out = run226.deconflict_writer_prompt(legacy)
        for forbidden in ('原則2〜3個', '4個目', '最大3項目', '2段落続いたら', '3つ以上連打'):
            self.assertNotIn(forbidden, out)
        self.assertIn('固定個数の上限で削らず', out)
        self.assertIn('段落数だけで機械的に切り替えない', out)
        self.assertIn('個数上限のために落とさない', out)

    def test_augment_preserves_base_prompt_and_existing_safety_language(self):
        base = 'BASE\nSOURCE BOUNDARY\nEvidence-to-Decision'
        augmented = run226.augment_prompt(base)
        self.assertTrue(augmented.startswith(base.rstrip()))
        self.assertIn('SOURCE BOUNDARY', augmented)
        self.assertIn('Evidence-to-Decision', augmented)
        self.assertEqual(1, augmented.count(run226.RUN226_MARKER))
        self.assertEqual(1, augmented.count(run226.EDITORIAL_BLUEPRINT_MARKER))
        self.assertEqual(1, augmented.count(editorial_quality_memory.QUALITY_MEMORY_MARKER))

    def test_augment_deconflicts_before_appending_current_contract(self):
        legacy = 'BASE\nこの無料ARTICLEで読者が本当に覚える専門概念を内部で原則2〜3個に絞る。4個目がないとDecisionを誤解する場合だけ4個まで許す。'
        augmented = run226.augment_prompt(legacy)
        self.assertNotIn('原則2〜3個', augmented)
        self.assertNotIn('4個目', augmented)
        self.assertIn('Central Conclusion / Capability Boundary / Reader Decision', augmented)
        self.assertEqual(1, augmented.count(run226.RUN226_MARKER))

    def test_augment_is_idempotent(self):
        once = run226.augment_prompt('BASE')
        twice = run226.augment_prompt(once)
        self.assertEqual(once, twice)
        self.assertEqual(1, twice.count(run226.RUN226_MARKER))
        self.assertEqual(1, twice.count(editorial_quality_memory.QUALITY_MEMORY_MARKER))

    def test_existing_run226_prompt_can_receive_missing_quality_memory_without_duplicate_blueprint(self):
        legacy = f"BASE\n\n{run226.editorial_planning_contract()}\n"
        out = run226.augment_prompt(legacy)
        self.assertEqual(1, out.count(run226.RUN226_MARKER))
        self.assertEqual(1, out.count(editorial_quality_memory.QUALITY_MEMORY_MARKER))

    def test_install_is_idempotent_without_mutating_real_pipeline(self):
        fake = types.SimpleNamespace(build_decision_prompt=lambda *a, **k: 'BASE')
        run226.install(fake)
        first = fake.build_decision_prompt()
        run226.install(fake)
        second = fake.build_decision_prompt()
        self.assertEqual(first, second)
        self.assertEqual(1, second.count(run226.RUN226_MARKER))
        self.assertEqual(1, second.count(editorial_quality_memory.QUALITY_MEMORY_MARKER))

    def test_run226_adds_no_model_or_client_call_site(self):
        src = inspect.getsource(run226)
        memory_src = inspect.getsource(editorial_quality_memory)
        self.assertNotIn('_generate_via_chat(', src)
        self.assertNotIn('genai.Client(', src)
        self.assertNotIn('_generate_via_chat(', memory_src)
        self.assertNotIn('genai.Client(', memory_src)
        pipeline_src = (ROOT / 'pipeline.py').read_text(encoding='utf-8')
        self.assertEqual(7, pipeline_src.count('_generate_via_chat('))
        self.assertEqual(1, pipeline_src.count('genai.Client('))

    def test_production_runtime_installs_run226(self):
        src = (ROOT / 'runtime_layers.py').read_text(encoding='utf-8')
        self.assertIn('import run226_reader_delight_planning', src)
        self.assertIn('run226_reader_delight_planning.install(pipeline_module)', src)

    def test_publication_fingerprint_includes_editorial_planning_dependencies(self):
        self.assertIn(
            'run226_reader_delight_planning.py',
            publication_contract.PUBLICATION_POLICY_FILES,
        )
        self.assertIn(
            'editorial_quality_memory.py',
            publication_contract.PUBLICATION_POLICY_FILES,
        )


if __name__ == '__main__':
    unittest.main()
