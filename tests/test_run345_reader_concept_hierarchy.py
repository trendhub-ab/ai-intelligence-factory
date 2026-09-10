import types
import unittest

import run208_reader_value_repair as run208


class Run345ReaderConceptHierarchyTests(unittest.TestCase):
    def _pipeline(self):
        p = types.SimpleNamespace()
        p.GATE_SEVERITY_HARD = "HARD"
        p.EVIDENCE_SUFFICIENT = "SUFFICIENT"
        p.should_attempt_dynamic_retry = lambda rows, evidence, origin="new": (False, "reader_value_review_no_retry")
        # Simulate the already-rich canonical prompt. Run345 must not merely add another
        # unordered style checklist; its execution hierarchy must be appended after it.
        p.build_decision_prompt = lambda *a, **k: (
            "BASE READER RULES\n"
            "専門概念を原則2〜3個に絞る。\n"
            "読者との距離が近くなる一文を自然に成立させる。"
        )
        p.build_dynamic_retry_instruction = lambda rows: ("BASE RETRY", ["ARTICLE"])
        return p

    def test_execution_hierarchy_overrides_duplicated_reader_checklists(self):
        p = self._pipeline()
        run208.install(p)
        prompt = p.build_decision_prompt()
        self.assertGreater(prompt.find("【実行優先順位】"), prompt.find("BASE READER RULES"))
        self.assertIn("1. Decision理解", prompt)
        self.assertIn("2. 制約保持", prompt)
        self.assertIn("3. Evidence保持", prompt)
        self.assertIn("4. 中核メカニズム", prompt)
        self.assertIn("5. 実装名・略語・ベンチマーク名", prompt)

    def test_concept_admission_discards_inventory_without_dropping_evidence(self):
        p = self._pipeline()
        run208.install(p)
        prompt = p.build_decision_prompt()
        self.assertIn("中核メカニズムを1つまで", prompt)
        self.assertIn("一次情報に名前があることはARTICLEへ列挙する理由にならない", prompt)
        self.assertIn("方法名、略語、ベンチマーク、内部部品が3個以上", prompt)
        self.assertIn("Evidence inventory", prompt)
        self.assertIn("Decisionを支える一次情報・重要数値・反証は残す", prompt)

    def test_reader_proximity_is_not_optimized_as_chatty_filler(self):
        p = self._pipeline()
        run208.install(p)
        prompt = p.build_decision_prompt()
        self.assertIn("Human Appealは問いかけや比喩の数ではなく", prompt)
        self.assertIn("親しみのための前置きは増やさない", prompt)
        self.assertIn("技術説明の次は新しい技術名を足さず", prompt)

    def test_repair_contract_compresses_name_lists_before_moving_them(self):
        p = self._pipeline()
        run208.install(p)
        instruction, sections = p.build_dynamic_retry_instruction([
            {"message": "reader_value_review:non_engineer_access_failure", "severity": "REVIEW"}
        ])
        self.assertEqual(["ARTICLE"], sections)
        self.assertIn("Decision理解 → 重要な制約 → Evidence → 中核メカニズム1つ → 実装名", instruction)
        self.assertIn("まず削除・カテゴリ化を検討", instruction)
        self.assertIn("「複数の既存手法」等へ圧縮", instruction)
        self.assertIn("Human Appealのための会話句・雑談・比喩は追加しない", instruction)

    def test_run345_adds_no_new_retry_authority_or_budget(self):
        p = self._pipeline()
        run208.install(p)
        unsafe_evidence = {"state": "INSUFFICIENT", "decision_scope_safe": True}
        rows = [{"message": "reader_value_review:non_engineer_access_failure", "severity": "REVIEW"}]
        self.assertEqual((False, "reader_value_review_no_retry"), p.should_attempt_dynamic_retry(rows, unsafe_evidence, "new"))
        self.assertTrue(p.RUN345_READER_CONCEPT_HIERARCHY)


if __name__ == "__main__":
    unittest.main()
