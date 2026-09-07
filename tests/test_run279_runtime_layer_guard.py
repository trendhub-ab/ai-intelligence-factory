from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import run279_runtime_layer_guard as guard


class Run279RuntimeLayerGuardTests(unittest.TestCase):
    def _repo(self, runtime_text: str, modules=("alpha", "beta"), production_text: str = ""):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "runtime_layers.py").write_text(runtime_text, encoding="utf-8")
        (root / "production_pipeline.py").write_text(production_text, encoding="utf-8")
        for module in modules:
            (root / f"{module}.py").write_text("def install(pipeline_module):\n    return pipeline_module\n", encoding="utf-8")
        return tmp, root

    @staticmethod
    def _literal_runtime(order=("alpha.install", "beta.install"), actual=("alpha", "beta")) -> str:
        declared = ",\n    ".join(repr(item) for item in order)
        imports = "\n    ".join(f"import {name}" for name in actual)
        calls = "\n    ".join(f"{name}.install(pipeline_module)" for name in actual)
        return f'''RUNTIME_LAYER_ORDER = (\n    {declared},\n)\n\ndef install_runtime_layers(pipeline_module):\n    {imports}\n    {calls}\n    return pipeline_module\n'''

    def test_current_repository_runtime_contract_passes(self):
        self.assertEqual([], guard.audit_runtime_layers())

    def test_fake_install_text_in_production_pipeline_cannot_satisfy_guard(self):
        runtime = self._literal_runtime()
        tmp, root = self._repo(
            runtime,
            production_text="fake.install(pipeline_module)\nrun999_fake.install(pipeline_module)\n",
        )
        self.addCleanup(tmp.cleanup)
        self.assertEqual([], guard.audit_runtime_layers(root))

    def test_dynamic_runtime_order_fails_closed(self):
        runtime = '''BASE = ("alpha.install",)\nRUNTIME_LAYER_ORDER = BASE + ("beta.install",)\n\ndef install_runtime_layers(pipeline_module):\n    import alpha\n    import beta\n    alpha.install(pipeline_module)\n    beta.install(pipeline_module)\n    return pipeline_module\n'''
        tmp, root = self._repo(runtime)
        self.addCleanup(tmp.cleanup)
        failures = guard.audit_runtime_layers(root)
        self.assertIn("runtime_layer_order_not_literal_sequence", failures)

    def test_duplicate_runtime_order_fails_closed(self):
        runtime = self._literal_runtime(
            order=("alpha.install", "alpha.install"),
            actual=("alpha", "alpha"),
        )
        tmp, root = self._repo(runtime, modules=("alpha",))
        self.addCleanup(tmp.cleanup)
        self.assertIn("runtime_layer_order_duplicate:alpha.install", guard.audit_runtime_layers(root))

    def test_declared_and_actual_order_must_match(self):
        runtime = self._literal_runtime(
            order=("alpha.install", "beta.install"),
            actual=("beta", "alpha"),
        )
        tmp, root = self._repo(runtime)
        self.addCleanup(tmp.cleanup)
        failures = guard.audit_runtime_layers(root)
        self.assertTrue(any(item.startswith("runtime_layer_execution_order_mismatch:") for item in failures))

    def test_missing_runtime_module_fails_closed(self):
        runtime = self._literal_runtime()
        tmp, root = self._repo(runtime, modules=("alpha",))
        self.addCleanup(tmp.cleanup)
        self.assertIn("runtime_layer_module_missing:beta.py", guard.audit_runtime_layers(root))

    def test_alias_import_is_resolved_to_declared_module(self):
        runtime = '''RUNTIME_LAYER_ORDER = ("alpha.install",)\n\ndef install_runtime_layers(pipeline_module):\n    import alpha as runtime_alpha\n    runtime_alpha.install(pipeline_module)\n    return pipeline_module\n'''
        tmp, root = self._repo(runtime, modules=("alpha",))
        self.addCleanup(tmp.cleanup)
        self.assertEqual([], guard.audit_runtime_layers(root))

    def test_install_hidden_in_control_flow_fails_closed(self):
        runtime = '''RUNTIME_LAYER_ORDER = ("alpha.install",)\n\ndef install_runtime_layers(pipeline_module):\n    import alpha\n    if True:\n        alpha.install(pipeline_module)\n    return pipeline_module\n'''
        tmp, root = self._repo(runtime, modules=("alpha",))
        self.addCleanup(tmp.cleanup)
        failures = guard.audit_runtime_layers(root)
        self.assertIn("runtime_install_control_flow_detected", failures)
        self.assertTrue(any(item.startswith("runtime_layer_execution_order_mismatch:") for item in failures))

    def test_multiple_runtime_order_assignments_fail_closed(self):
        runtime = '''RUNTIME_LAYER_ORDER = ("alpha.install",)\nRUNTIME_LAYER_ORDER = ("beta.install",)\n\ndef install_runtime_layers(pipeline_module):\n    import alpha\n    alpha.install(pipeline_module)\n    return pipeline_module\n'''
        tmp, root = self._repo(runtime)
        self.addCleanup(tmp.cleanup)
        self.assertIn("runtime_layer_order_assignment_count:2", guard.audit_runtime_layers(root))


if __name__ == "__main__":
    unittest.main()
