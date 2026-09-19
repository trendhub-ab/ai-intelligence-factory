import inspect
from pathlib import Path
import types
import unittest

import canonical_article_contract as cac
import editorial_quality_memory
import publication_contract
import run226_reader_delight_planning as run226


ROOT = Path(__file__).resolve().parents[1]


class Run226ReaderDelightPlanningTests(unittest.TestCase):
    def test_contract_exposes_canonical_article_dimensions(self):
        text = run226.editorial_planning_contract()
        for token in (
            cac.CANONICAL_ARTICLE_CONTRACT_MARKER,
            "Reader Question",
            "Why Now",
            "Central Conclusion",
            "Discovery",
            "Capability Boundary",
            "Reader Decision",
            "Evidence Integrity",
        ):
            self.assertIn(token, text)
        self.assertEqual(run226.EDITORIAL_BLUEPRINT_MARKER, cac.CANONICAL_ARTICLE_CONTRACT_MARKER)

    def test_contract_preserves_evidence_boundary_and_human_voice_without_quotas(self):
        text = run226.editorial_planning_contract()
        self.assertIn("Evidence、重要数値、条件、反証、対象範囲を落とさない", text)
        self.assertIn("架空の経験・感情・因果・会話・多数派認識を作らない", text)
        self.assertIn("専門語の固定個数制限は設けない", text)
        self.assertIn("固定見出しや固定順序にしない", text)

    def test_deconflicts_legacy_fixed_count_writer_rules(self):
        legacy = "\n".join(
            [
                "記事全体の温度を1〜2個の口語句で済ませず、硬い説明が2段落続いたら次の段落では、追加説明を足さず、既存文を「読者の判断／具体場面／平易な一言」のどれかへ置き換えて人間の言葉へ戻す。",
                "この無料ARTICLEで読者が本当に覚える専門概念を内部で原則2〜3個に絞る。4個目がないとDecisionを誤解する場合だけ4個まで許す。",
                "ARTICLE本文で説明する中核概念は原則2〜3個、実装識別子・規格名・コマンド名は意思決定に必要なものだけに限定し、列挙で専門性を演出しない。",
                "手順・機能・注意点の列挙はそれぞれ最大3項目まで。",
                "短文を3つ以上連打して広告コピーのように煽らない。",
            ]
        )
        out = run226.deconflict_writer_prompt(legacy)
        for forbidden in ("原則2〜3個", "4個目", "最大3項目", "2段落続いたら", "3つ以上連打"):
            self.assertNotIn(forbidden, out)
        self.assertIn("固定個数で制限しない", out)
        self.assertIn("個数上限で落とさない", out)

    def test_augment_preserves_base_and_installs_each_policy_once(self):
        base = "BASE\nSOURCE BOUNDARY\nEvidence-to-Decision"
        augmented = run226.augment_prompt(base)
        self.assertTrue(augmented.startswith(base))
        self.assertEqual(1, augmented.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER))
        self.assertEqual(1, augmented.count(run226.RUN226_MARKER))
        self.assertEqual(1, augmented.count(editorial_quality_memory.QUALITY_MEMORY_MARKER))

    def test_augment_is_idempotent(self):
        once = run226.augment_prompt("BASE")
        twice = run226.augment_prompt(once)
        self.assertEqual(once, twice)
        self.assertEqual(1, twice.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER))
        self.assertEqual(1, twice.count(run226.RUN226_MARKER))
        self.assertEqual(1, twice.count(editorial_quality_memory.QUALITY_MEMORY_MARKER))

    def test_install_is_idempotent_without_mutating_real_pipeline(self):
        fake = types.SimpleNamespace(build_decision_prompt=lambda *a, **k: "BASE")
        run226.install(fake)
        first = fake.build_decision_prompt()
        run226.install(fake)
        second = fake.build_decision_prompt()
        self.assertEqual(first, second)
        self.assertEqual(1, second.count(cac.CANONICAL_ARTICLE_CONTRACT_MARKER))

    def test_run226_adds_no_model_or_client_call_site(self):
        src = inspect.getsource(run226)
        memory_src = inspect.getsource(editorial_quality_memory)
        self.assertNotIn("_generate_via_chat(", src)
        self.assertNotIn("genai.Client(", src)
        self.assertNotIn("_generate_via_chat(", memory_src)
        self.assertNotIn("genai.Client(", memory_src)
        pipeline_src = (ROOT / "pipeline.py").read_text(encoding="utf-8")
        self.assertEqual(7, pipeline_src.count("_generate_via_chat("))
        self.assertEqual(1, pipeline_src.count("genai.Client("))

    def test_production_runtime_installs_run226(self):
        src = (ROOT / "runtime_layers.py").read_text(encoding="utf-8")
        self.assertIn("import run226_reader_delight_planning", src)
        self.assertIn("run226_reader_delight_planning.install(pipeline_module)", src)

    def test_publication_fingerprint_keeps_historical_prompt_dependencies(self):
        self.assertIn("run226_reader_delight_planning.py", publication_contract.PUBLICATION_POLICY_FILES)
        self.assertIn("editorial_quality_memory.py", publication_contract.PUBLICATION_POLICY_FILES)


if __name__ == "__main__":
    unittest.main()
