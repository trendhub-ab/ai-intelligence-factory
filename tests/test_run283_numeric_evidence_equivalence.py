from __future__ import annotations

import ast
import unittest
from pathlib import Path
from types import SimpleNamespace

import run283_numeric_evidence_equivalence as run283

ROOT = Path(__file__).resolve().parents[1]


def _compatible(_claim: str, _evidence: str) -> bool:
    return True


class Run283NumericEquivalenceTests(unittest.TestCase):
    def test_run282_pricing_fraction_false_positive_is_removed(self):
        failures = ["unsupported numeric claim: 10分の1"]
        draft = "キャッシュからの読み込みは通常の入力価格の10分の1です。"
        source = "Cache read tokens are billed at 0.1x the base input token price."
        self.assertEqual(
            [],
            run283.filter_numeric_false_positives(
                failures, draft, source, condition_compatible=_compatible
            ),
        )

    def test_run282_cache_expiry_hour_false_positive_is_removed(self):
        failures = ["unsupported numeric claim: 1時間"]
        draft = "サブスクリプション環境では1時間でキャッシュが失効する。"
        source = "For subscriptions, the prompt cache expires after an hour."
        self.assertEqual(
            [],
            run283.filter_numeric_false_positives(
                failures, draft, source, condition_compatible=_compatible
            ),
        )

    def test_same_number_in_wrong_semantic_domain_stays_blocked(self):
        pricing_source = "Cache read tokens are billed at 0.1x the base input token price."
        speed_claim = "キャッシュの処理速度は10分の1です。"
        self.assertEqual(
            ["unsupported numeric claim: 10分の1"],
            run283.filter_numeric_false_positives(
                ["unsupported numeric claim: 10分の1"],
                speed_claim,
                pricing_source,
                condition_compatible=_compatible,
            ),
        )

        expiry_source = "For subscriptions, the prompt cache expires after an hour."
        runtime_claim = "この処理の実行時間は1時間です。"
        self.assertEqual(
            ["unsupported numeric claim: 1時間"],
            run283.filter_numeric_false_positives(
                ["unsupported numeric claim: 1時間"],
                runtime_claim,
                expiry_source,
                condition_compatible=_compatible,
            ),
        )

    def test_wrong_quantity_and_non_numeric_failures_are_untouched(self):
        failures = [
            "unsupported numeric claim: 10分の1",
            "numeric condition mismatch: 1時間",
            "unsupported vague quantified claim: 数ヶ月",
        ]
        source = "Cache read tokens are billed at 0.2x input price. Cache expires after two hours."
        self.assertEqual(
            failures,
            run283.filter_numeric_false_positives(
                failures,
                "入力価格の10分の1。キャッシュは1時間で失効する。",
                source,
                condition_compatible=_compatible,
            ),
        )

    def test_existing_condition_mismatch_can_never_be_rescued(self):
        self.assertEqual(
            ["unsupported numeric claim: 10分の1"],
            run283.filter_numeric_false_positives(
                ["unsupported numeric claim: 10分の1"],
                "キャッシュ読み込み価格は10分の1。",
                "Cache read tokens are billed at 0.1x input price.",
                condition_compatible=lambda _c, _e: False,
            ),
        )

    def test_install_is_idempotent_and_wraps_only_numeric_validator(self):
        calls = []

        def original(draft, source, evidence_metadata=None):
            calls.append((draft, source, evidence_metadata))
            return ["unsupported numeric claim: 10分の1", "numeric condition mismatch: 9ms"]

        module = SimpleNamespace(
            _find_unsupported_numeric_claims=original,
            _numeric_condition_compatible=_compatible,
        )
        run283.install(module)
        wrapped = module._find_unsupported_numeric_claims
        run283.install(module)
        self.assertIs(wrapped, module._find_unsupported_numeric_claims)
        result = wrapped(
            "キャッシュ読み込み価格は10分の1。",
            "Cache read tokens are billed at 0.1x input price.",
            {"ignored": True},
        )
        self.assertEqual(["numeric condition mismatch: 9ms"], result)
        self.assertEqual(1, len(calls))

    def test_module_is_stdlib_only_and_runtime_order_is_narrow(self):
        tree = ast.parse((ROOT / "run283_numeric_evidence_equivalence.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported <= {"__future__", "decimal", "re", "typing"}, imported)

        runtime = (ROOT / "runtime_layers.py").read_text(encoding="utf-8")
        self.assertLess(
            runtime.index('"run223_technical_claim_precision.install"'),
            runtime.index('"run283_numeric_evidence_equivalence.install"'),
        )
        self.assertLess(
            runtime.index('"run283_numeric_evidence_equivalence.install"'),
            runtime.index('"run224_multiplier_deterministic_rescue.install"'),
        )

    def test_publication_provenance_and_reconciliation_track_run283(self):
        contract = (ROOT / "publication_contract.py").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/note-ready-sync.yml").read_text(encoding="utf-8")
        self.assertIn('"run283_numeric_evidence_equivalence.py"', contract)
        self.assertIn("- 'run283_numeric_evidence_equivalence.py'", workflow)


if __name__ == "__main__":
    unittest.main()
