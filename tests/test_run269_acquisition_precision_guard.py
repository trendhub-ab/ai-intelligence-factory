from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
import unittest

import run269_acquisition_precision_guard as guard


class Run269AcquisitionPrecisionGuardTests(unittest.TestCase):
    def _copy_contract(self, root: Path) -> None:
        for relative in (
            guard.BASE_ACQUISITION,
            guard.PRECISION,
            guard.CURRENT_STATE,
            guard.LAYER,
            guard.SMOKE,
            guard.ENTRYPOINT,
            guard.LIVE_WORKFLOW,
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(guard.ROOT / relative, target)

    def test_current_repository_contract_passes(self):
        self.assertEqual([], guard.collect_errors(guard.ROOT))

    def test_guard_rejects_raw_ai_query_reintroduction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            precision = root / guard.PRECISION
            text = precision.read_text(encoding="utf-8").replace('HN_AI_QUERIES = (', 'HN_AI_QUERIES = (\n    "AI",', 1)
            precision.write_text(text, encoding="utf-8")
            self.assertIn("hn_raw_ai_query_reintroduced", guard.collect_errors(root))

    def test_guard_rejects_precision_before_source_strategy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            entrypoint = root / guard.ENTRYPOINT
            text = entrypoint.read_text(encoding="utf-8")
            source = "    install_run268_business_source_strategy(pipeline)"
            precision = "    install_run269_business_source_precision(pipeline)"
            self.assertIn(source, text)
            self.assertIn(precision, text)
            text = text.replace(source, "    __SWAP__", 1).replace(precision, source, 1).replace("    __SWAP__", precision, 1)
            entrypoint.write_text(text, encoding="utf-8")
            self.assertIn("precision_layer_must_install_after_source_strategy", guard.collect_errors(root))

    def test_guard_rejects_live_smoke_that_imports_production_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            smoke = root / guard.SMOKE
            text = smoke.read_text(encoding="utf-8").replace("import requests", "import requests\nimport pipeline", 1)
            smoke.write_text(text, encoding="utf-8")
            self.assertIn("live_smoke_forbidden_surface:import pipeline", guard.collect_errors(root))

    def test_guard_rejects_current_state_contract_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            current_state = root / guard.CURRENT_STATE
            text = current_state.read_text(encoding="utf-8").replace('"current_state_page": True', '"current_state_page": False', 1)
            current_state.write_text(text, encoding="utf-8")
            self.assertTrue(any(e.startswith("current_state_missing:") for e in guard.collect_errors(root)))

    def test_guard_rejects_model_marker_fallback_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            current_state = root / guard.CURRENT_STATE
            text = current_state.read_text(encoding="utf-8").replace("def _has_model_list_current_state", "def _removed_model_list_current_state", 1)
            current_state.write_text(text, encoding="utf-8")
            self.assertIn("current_state_missing:def _has_model_list_current_state", guard.collect_errors(root))

    def test_guard_rejects_model_secret_in_live_smoke_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            workflow = root / guard.LIVE_WORKFLOW
            workflow.write_text(workflow.read_text(encoding="utf-8") + "\n# GEMINI_API_KEY\n", encoding="utf-8")
            self.assertIn("live_workflow_forbidden_secret:GEMINI_API_KEY", guard.collect_errors(root))


if __name__ == "__main__":
    unittest.main()
