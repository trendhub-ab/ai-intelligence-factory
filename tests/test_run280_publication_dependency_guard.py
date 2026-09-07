import tempfile
import unittest
from pathlib import Path
from unittest import mock

import run280_publication_dependency_guard as guard


class Run280PublicationDependencyGuardTests(unittest.TestCase):
    def test_current_repository_is_dependency_complete(self):
        self.assertEqual(guard.validate_repository(guard.ROOT), [])

    def _fixture(self, policy=("pipeline.py", "production_pipeline.py", "runtime_layers.py")):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / ".github/workflows").mkdir(parents=True)
        manifest = ",\n    ".join(repr(item) for item in policy)
        (root / "publication_contract.py").write_text(
            f"PUBLICATION_POLICY_FILES = (\n    {manifest},\n)\n",
            encoding="utf-8",
        )
        for name in ("pipeline.py", "production_pipeline.py", "runtime_layers.py"):
            (root / name).write_text("", encoding="utf-8")
        tracked = "\n".join(f"      - '{item}'" for item in policy)
        (root / ".github/workflows/note-ready-sync.yml").write_text(
            "on:\n  push:\n    paths:\n" + tracked + "\n",
            encoding="utf-8",
        )
        return tmp, root

    def _validate_minimal(self, root):
        with mock.patch.object(guard, "REQUIRED_PUBLICATION_DEPENDENCIES", ("runtime_layers.py",)), \
             mock.patch.object(guard, "CLASSIFICATION_SURFACES", ("pipeline.py", "production_pipeline.py", "runtime_layers.py")), \
             mock.patch.object(guard, "TRANSITIVE_MATERIAL_SURFACES", ()), \
             mock.patch.object(guard, "EXPLICIT_NON_PUBLICATION_DEPENDENCIES", {}):
            return guard.validate_repository(root)

    def test_missing_required_material_dependency_fails_closed(self):
        tmp, root = self._fixture(policy=("pipeline.py", "production_pipeline.py"))
        self.addCleanup(tmp.cleanup)
        failures = self._validate_minimal(root)
        self.assertTrue(any("runtime_layers.py" in row and "missing from policy" in row for row in failures), failures)

    def test_unclassified_new_local_import_fails_closed(self):
        tmp, root = self._fixture()
        self.addCleanup(tmp.cleanup)
        (root / "surprise_publication_helper.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "pipeline.py").write_text("import surprise_publication_helper\n", encoding="utf-8")
        failures = self._validate_minimal(root)
        self.assertTrue(any("unclassified local dependency" in row for row in failures), failures)

    def test_documented_operational_dependency_does_not_force_ready_invalidation(self):
        tmp, root = self._fixture()
        self.addCleanup(tmp.cleanup)
        (root / "telemetry_only.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "production_pipeline.py").write_text("import telemetry_only\n", encoding="utf-8")
        with mock.patch.object(guard, "REQUIRED_PUBLICATION_DEPENDENCIES", ("runtime_layers.py",)), \
             mock.patch.object(guard, "CLASSIFICATION_SURFACES", ("pipeline.py", "production_pipeline.py", "runtime_layers.py")), \
             mock.patch.object(guard, "TRANSITIVE_MATERIAL_SURFACES", ()), \
             mock.patch.object(guard, "EXPLICIT_NON_PUBLICATION_DEPENDENCIES", {"telemetry_only.py": "observational only"}):
            self.assertEqual(guard.validate_repository(root), [])

    def test_every_policy_file_must_trigger_note_ready_reconciliation(self):
        tmp, root = self._fixture()
        self.addCleanup(tmp.cleanup)
        workflow = root / ".github/workflows/note-ready-sync.yml"
        workflow.write_text(
            "on:\n  push:\n    paths:\n      - 'pipeline.py'\n      - 'production_pipeline.py'\n",
            encoding="utf-8",
        )
        failures = self._validate_minimal(root)
        self.assertTrue(any("runtime_layers.py" in row and "does not trigger" in row for row in failures), failures)

    def test_duplicate_policy_entries_fail_closed(self):
        tmp, root = self._fixture(policy=("pipeline.py", "production_pipeline.py", "runtime_layers.py", "runtime_layers.py"))
        self.addCleanup(tmp.cleanup)
        failures = self._validate_minimal(root)
        self.assertIn("PUBLICATION_POLICY_FILES contains duplicate entries", failures)


if __name__ == "__main__":
    unittest.main()
