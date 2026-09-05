from __future__ import annotations

import builtins
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def _bridge_source() -> str:
    source = (ROOT / "pipeline.py").read_text(encoding="utf-8")
    start = source.index("# Run231 Stage2B direct-import compatibility bridge")
    end = source.index('\n\nif __name__ == "__main__":', start)
    return source[start:end]


class Run234LegacyDependencyIsolationTests(unittest.TestCase):
    def test_exact_missing_legacy_module_keeps_bridge_importable_and_fails_only_on_legacy_call(self):
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "legacy_eyecatch_renderer":
                raise ModuleNotFoundError(
                    "No module named 'legacy_eyecatch_renderer'",
                    name="legacy_eyecatch_renderer",
                )
            return real_import(name, globals, locals, fromlist, level)

        live_editorial = object()
        namespace = {
            "__builtins__": builtins.__dict__,
            "generate_note_editorial_eyecatch": live_editorial,
        }
        with mock.patch("builtins.__import__", side_effect=fake_import):
            exec(compile(_bridge_source(), "pipeline-bridge", "exec"), namespace, namespace)

        self.assertIs(live_editorial, namespace["generate_note_editorial_eyecatch"])
        legacy = namespace["generate_eyecatch_image"]
        self.assertTrue(getattr(legacy, "__run231_stage2_legacy_eyecatch__", False))
        with self.assertRaisesRegex(RuntimeError, "legacy eyecatch renderer is unavailable"):
            legacy("unused")

    def test_nested_missing_dependency_is_not_swallowed(self):
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "legacy_eyecatch_renderer":
                raise ModuleNotFoundError("No module named 'PIL'", name="PIL")
            return real_import(name, globals, locals, fromlist, level)

        namespace = {"__builtins__": builtins.__dict__}
        with mock.patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaises(ModuleNotFoundError) as ctx:
                exec(compile(_bridge_source(), "pipeline-bridge", "exec"), namespace, namespace)
        self.assertEqual("PIL", ctx.exception.name)

    def test_syntax_error_from_legacy_import_is_not_swallowed(self):
        real_import = builtins.__import__

        def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
            if name == "legacy_eyecatch_renderer":
                raise SyntaxError("broken legacy renderer")
            return real_import(name, globals, locals, fromlist, level)

        namespace = {"__builtins__": builtins.__dict__}
        with mock.patch("builtins.__import__", side_effect=fake_import):
            with self.assertRaisesRegex(SyntaxError, "broken legacy renderer"):
                exec(compile(_bridge_source(), "pipeline-bridge", "exec"), namespace, namespace)


class Run234RequiredCrossDbContractTests(unittest.TestCase):
    def test_required_zero_api_job_contains_cross_db_contract_suite(self):
        workflow = (ROOT / ".github/workflows/integration-reconciliation-ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("  zero-api-regression:", workflow)
        for command in (
            "python -m unittest tests/test_cross_db_contract_guard.py",
            "python -m unittest tests/test_content_db_contract_guard.py",
            "python -m unittest tests/test_evidence_db_contract_guard.py",
            "python -m unittest tests/test_member_presentation_resolution_guard.py",
            "python -m unittest tests/test_run232_notion_integration_reconciliation.py",
        ):
            self.assertIn(command, workflow)

    def test_cross_db_sensitive_paths_cannot_bypass_required_zero_api_job(self):
        workflow = (ROOT / ".github/workflows/integration-reconciliation-ci.yml").read_text(
            encoding="utf-8"
        )
        for path in (
            "cross_db_contract_guard.py",
            "content_db_contract_guard.py",
            "evidence_db_contract_guard.py",
            "evidence_ledger.py",
            "member_presentation_sync.py",
            "member_presentation_identity.py",
            "provision_member_presentation_db.py",
            "notion_access_policy_guard.py",
            "notion_audit_views.json",
            "documentation_freshness_guard.py",
            ".github/workflows/cross-db-contract-guard.yml",
        ):
            self.assertIn(f"- '{path}'", workflow)


if __name__ == "__main__":
    unittest.main()
