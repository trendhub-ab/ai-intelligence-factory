import hashlib
import importlib.util
import unittest
from pathlib import Path

import member_customer_surface_contract as member_contract


ROOT = Path(__file__).resolve().parents[1]
GUARD_PATH = ROOT / "specification_freshness_guard.py"
SPEC_PATH = ROOT / "AI_Intelligence_Factory_最終仕様書.md"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "repository-falsification.yml"


def _guard_module():
    if not GUARD_PATH.is_file():
        return None
    spec = importlib.util.spec_from_file_location("specification_freshness_guard_under_test", GUARD_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


class SpecificationFreshnessGuardTests(unittest.TestCase):
    def test_guard_classifies_executable_workflow_and_asset_surfaces(self):
        guard = _guard_module()
        self.assertIsNotNone(guard, "specification_freshness_guard.py must exist")

        self.assertTrue(guard.is_production_surface("pipeline.py"))
        self.assertTrue(guard.is_production_surface("local_skills/a_plus.py"))
        self.assertTrue(guard.is_production_surface(".github/workflows/daily-one-shot.yml"))
        self.assertTrue(guard.is_production_surface("assets/eyecatch/v2/.background_master_parts/part01.b64"))
        self.assertFalse(guard.is_production_surface("tests/test_pipeline.py"))
        self.assertFalse(guard.is_production_surface("docs/audits/example.md"))
        self.assertFalse(guard.is_production_surface("AI_Intelligence_Factory_最終仕様書.md"))

    def test_v3_phase0_dispatchable_code_is_included_in_production_fingerprint(self):
        guard = _guard_module()
        for name in ("cases.py", "prompts.py", "proof.py", "runner.py", "contract.py", "live.py"):
            with self.subTest(name=name):
                self.assertTrue(
                    guard.is_production_surface(f"experiments/editorial_engine_v3_phase0/{name}")
                )
        self.assertTrue(guard.is_production_surface("experiments/other_experiment/runner.py"))
        production = {"pipeline.py": b"live code"}
        experiment_changed = dict(production)
        experiment_changed["experiments/editorial_engine_v3_phase0/prompts.py"] = b"C writer changed"
        self.assertNotEqual(
            guard.fingerprint_entries(production),
            guard.fingerprint_entries(experiment_changed),
        )

    def test_v3_experiment_commit_advances_production_review_date(self):
        guard = _guard_module()
        history = (
            "__AIIF_COMMIT__2026-10-19\n"
            "experiments/editorial_engine_v3_phase0/prompts.py\n"
            "__AIIF_COMMIT__2026-10-18\n"
            "pipeline.py\n"
        )
        from unittest.mock import patch
        with patch.object(guard, "_git", return_value=history):
            self.assertEqual("2026-10-19", guard.latest_production_commit_date())

    def test_fingerprint_is_deterministic_and_ignores_documentation_only_changes(self):
        guard = _guard_module()
        self.assertIsNotNone(guard, "specification_freshness_guard.py must exist")

        base = {
            "pipeline.py": b"print('v1')\n",
            "tests/test_pipeline.py": b"assert True\n",
            "docs/audits/example.md": b"old docs\n",
        }
        docs_changed = dict(base)
        docs_changed["tests/test_pipeline.py"] = b"assert 1 == 1\n"
        docs_changed["docs/audits/example.md"] = b"new docs\n"
        production_changed = dict(base)
        production_changed["pipeline.py"] = b"print('v2')\n"

        first = guard.fingerprint_entries(base)
        second = guard.fingerprint_entries(dict(reversed(list(base.items()))))
        self.assertEqual(first, second)
        self.assertEqual(first, guard.fingerprint_entries(docs_changed))
        self.assertNotEqual(first, guard.fingerprint_entries(production_changed))
        self.assertEqual(64, len(first))
        int(first, 16)

    def test_metadata_audit_fails_closed_on_stale_fingerprint_or_review_date(self):
        guard = _guard_module()
        self.assertIsNotNone(guard, "specification_freshness_guard.py must exist")

        expected = hashlib.sha256(b"production").hexdigest()
        stale = hashlib.sha256(b"stale").hexdigest()
        text = (
            "仕様最終変更日: **2026-10-13**  \n"
            "Production最終照合日: **2026-10-12**  \n"
            f"Production Contract Fingerprint: **`{stale}`**  \n"
            "実装監査基準SHA: **`774211333c9103d7bed92d46fa6d2824ec521953`**  \n"
        )
        failures = guard.audit_metadata(
            text,
            expected_fingerprint=expected,
            latest_production_date="2026-10-13",
        )
        self.assertIn("production_contract_fingerprint_mismatch", failures)
        self.assertIn("production_review_date_stale", failures)

        current = text.replace("2026-10-12", "2026-10-13").replace(stale, expected)
        self.assertEqual(
            [],
            guard.audit_metadata(
                current,
                expected_fingerprint=expected,
                latest_production_date="2026-10-13",
            ),
        )

    def test_repository_falsification_workflow_executes_specification_guard(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("python specification_freshness_guard.py", workflow)
        self.assertIn("python -m unittest tests.test_specification_freshness_guard -v", workflow)
        self.assertIn("fetch-depth: 0", workflow)

    def test_canonical_spec_exposes_machine_checked_freshness_metadata(self):
        text = SPEC_PATH.read_text(encoding="utf-8")
        self.assertIn("仕様最終変更日:", text)
        self.assertIn("Production最終照合日:", text)
        self.assertIn("Production Contract Fingerprint:", text)
        self.assertIn("実装監査基準SHA:", text)

    def test_specification_guard_is_explicitly_non_member_infrastructure(self):
        self.assertIn("specification_freshness_guard.py", member_contract.NON_MEMBER_MODULES)


if __name__ == "__main__":
    unittest.main(verbosity=2)
