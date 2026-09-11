from __future__ import annotations

import ast
from pathlib import Path
import unittest

import run348_adversarial_editorial_lab as lab


ROOT = Path(__file__).resolve().parents[1]


class Run348AdversarialEditorialLabTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = lab.build_corpus(10_000)
        cls.report = lab.evaluate(cls.cases)

    def test_corpus_is_large_deterministic_and_covers_four_failure_families(self):
        self.assertEqual(10_000, len(self.cases))
        self.assertEqual(set(lab.FAMILIES), {case.family for case in self.cases})
        self.assertEqual(lab.corpus_digest(self.cases), lab.corpus_digest(lab.build_corpus(10_000)))
        for family in lab.FAMILIES:
            labels = {case.expected for case in self.cases if case.family == family}
            self.assertIn(lab.OK, labels)
            self.assertIn(lab.FAIL, labels)

    def test_lab_has_zero_api_import_surface(self):
        tree = ast.parse((ROOT / "run348_adversarial_editorial_lab.py").read_text(encoding="utf-8"))
        forbidden = {"requests", "httpx", "google", "google_genai", "notion_client", "pipeline"}
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        self.assertFalse(imported & forbidden, imported & forbidden)
        self.assertEqual(
            {"gemini_calls": 0, "notion_reads": 0, "notion_writes": 0, "network_calls": 0, "pipeline_imported": False},
            self.report["safety_contract"],
        )

    def test_fact_scope_overclaims_are_not_accepted(self):
        targeted = [
            case for case in self.cases
            if case.family == "fact" and case.expected == lab.FAIL
            and set(case.tags) & {"max_to_average", "universalized", "preview_to_ga", "conditional_free_to_free", "partial_to_total_retirement"}
        ]
        self.assertGreater(len(targeted), 100)
        accepted = [case.case_id for case in targeted if lab.detect(case) == lab.OK]
        self.assertEqual([], accepted[:10])

    def test_one_or_two_natural_glue_phrases_do_not_fail_human_appeal(self):
        controls = [case for case in self.cases if case.family == "human_appeal" and "single_glue_control" in case.tags]
        self.assertGreater(len(controls), 20)
        failures = [case.case_id for case in controls if lab.detect(case) == lab.FAIL]
        self.assertEqual([], failures[:10])

    def test_formulaic_composites_are_detected(self):
        cases = [case for case in self.cases if case.family == "human_appeal" and "formulaic_composite" in case.tags]
        self.assertGreater(len(cases), 20)
        missed = [case.case_id for case in cases if lab.detect(case) != lab.FAIL]
        self.assertEqual([], missed[:10])

    def test_score_narrative_clear_mismatches_fail(self):
        cases = [case for case in self.cases if case.family == "score_narrative" and case.expected == lab.FAIL]
        self.assertGreater(len(cases), 100)
        missed = [case.case_id for case in cases if lab.detect(case) != lab.FAIL]
        self.assertEqual([], missed[:10])

    def test_report_exposes_false_positive_and_false_negative_rates_per_family(self):
        self.assertEqual(10_000, self.report["total_cases"])
        for family in lab.FAMILIES:
            row = self.report["families"][family]
            self.assertIn("false_positive_rate", row)
            self.assertIn("false_negative_rate", row)
            self.assertGreater(row["known_good"], 0)
            self.assertGreater(row["known_bad"], 0)


if __name__ == "__main__":
    unittest.main()
