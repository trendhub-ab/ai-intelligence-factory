from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
import unittest

import run269_acquisition_precision_guard as guard


class Run269AcquisitionPrecisionGuardTests(unittest.TestCase):
    def _copy_contract(self, root: Path) -> None:
        required = (
            guard.BASE_ACQUISITION,
            guard.PRECISION,
            guard.CURRENT_STATE,
            guard.LAYER,
            guard.SMOKE,
            guard.ENTRYPOINT,
            guard.LIVE_WORKFLOW,
            guard.FALSIFICATION_WORKFLOW,
            guard.SPEC,
            guard.REFERENCE,
        )
        for relative in required:
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
            text = precision.read_text(encoding="utf-8")
            text = text.replace('HN_AI_QUERIES = (', 'HN_AI_QUERIES = (\n    "AI",', 1)
            precision.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertIn("hn_raw_ai_query_reintroduced", errors)

    def test_guard_rejects_run269_before_run268(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            entrypoint = root / guard.ENTRYPOINT
            text = entrypoint.read_text(encoding="utf-8")
            run268 = "    install_run268_business_source_strategy(pipeline)"
            run269 = "    install_run269_business_source_precision(pipeline)"
            self.assertIn(run268, text)
            self.assertIn(run269, text)
            text = text.replace(run268, "    __RUN269_SWAP_A__", 1)
            text = text.replace(run269, run268, 1)
            text = text.replace("    __RUN269_SWAP_A__", run269, 1)
            entrypoint.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertIn("run269_must_install_after_run268", errors)

    def test_guard_rejects_live_smoke_that_imports_production_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            smoke = root / guard.SMOKE
            text = smoke.read_text(encoding="utf-8")
            text = text.replace("import requests", "import requests\nimport pipeline", 1)
            smoke.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertIn("live_smoke_forbidden_surface:import pipeline", errors)

    def test_guard_rejects_bytedance_current_state_contract_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            current_state = root / guard.CURRENT_STATE
            text = current_state.read_text(encoding="utf-8")
            text = text.replace('"current_state_page": True', '"current_state_page": False', 1)
            current_state.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertTrue(any(e.startswith("current_state_missing:") for e in errors))

    def test_guard_rejects_model_marker_fallback_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            current_state = root / guard.CURRENT_STATE
            text = current_state.read_text(encoding="utf-8")
            text = text.replace("def _has_model_list_current_state", "def _removed_model_list_current_state", 1)
            current_state.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertIn("current_state_missing:def _has_model_list_current_state", errors)


if __name__ == "__main__":
    unittest.main()
