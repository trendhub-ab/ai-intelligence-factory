import inspect
import types
import unittest
from pathlib import Path

import pipeline
import publication_contract
import runtime_layers
import run226_reader_delight_planning as run226


class Run226ReaderDelightPlanningTests(unittest.TestCase):
    def test_contract_contains_five_editorial_lenses(self):
        text = run226.editorial_planning_contract()
        for token in (
            'Reader Tension',
            'Discovery',
            'Concrete Consequence',
            'Explanation Bridge',
            'Editorial Point of View',
        ):
            self.assertIn(token, text)

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

    def test_augment_preserves_base_prompt_and_existing_safety_language(self):
        base = pipeline.build_decision_prompt(
            'x', 'https://example.com', 1, 'desc', source_context='primary evidence'
        )
        augmented = run226.augment_prompt(base)
        self.assertTrue(augmented.startswith(base.rstrip()))
        self.assertIn('SOURCE BOUNDARY', augmented)
        self.assertIn('Evidence-to-Decision', augmented)
        self.assertEqual(1, augmented.count(run226.RUN226_MARKER))

    def test_augment_is_idempotent(self):
        once = run226.augment_prompt('BASE')
        twice = run226.augment_prompt(once)
        self.assertEqual(once, twice)
        self.assertEqual(1, twice.count(run226.RUN226_MARKER))

    def test_install_is_idempotent_without_mutating_real_pipeline(self):
        fake = types.SimpleNamespace(build_decision_prompt=lambda *a, **k: 'BASE')
        run226.install(fake)
        first = fake.build_decision_prompt()
        run226.install(fake)
        second = fake.build_decision_prompt()
        self.assertEqual(first, second)
        self.assertEqual(1, second.count(run226.RUN226_MARKER))

    def test_run226_adds_no_model_or_client_call_site(self):
        src = inspect.getsource(run226)
        self.assertNotIn('_generate_via_chat(', src)
        self.assertNotIn('genai.Client(', src)
        pipeline_src = inspect.getsource(pipeline)
        self.assertEqual(7, pipeline_src.count('_generate_via_chat('))
        self.assertEqual(1, pipeline_src.count('genai.Client('))

    def test_production_runtime_installs_run226(self):
        src = inspect.getsource(runtime_layers)
        self.assertIn('import run226_reader_delight_planning', src)
        self.assertIn('run226_reader_delight_planning.install(pipeline_module)', src)

    def test_publication_fingerprint_includes_run226(self):
        self.assertIn(
            'run226_reader_delight_planning.py',
            publication_contract.PUBLICATION_POLICY_FILES,
        )

    def test_canonical_spec_documents_run226(self):
        root = Path(__file__).resolve().parents[1]
        spec = (root / 'AI_Intelligence_Factory_最終仕様書.md').read_text(encoding='utf-8')
        self.assertIn('Run226', spec)
        self.assertIn('run226_reader_delight_planning.py', spec)
        self.assertIn('Reader Tension', spec)
        self.assertIn('回数ノルマ', spec)


if __name__ == '__main__':
    unittest.main()
