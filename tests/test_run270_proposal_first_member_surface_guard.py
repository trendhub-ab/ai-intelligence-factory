from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
import unittest

import run270_proposal_first_member_surface_guard as guard


class MemberCompatibilityGuardTests(unittest.TestCase):
    def _copy_contract(self, root: Path) -> None:
        for relative in (guard.MODULE, guard.WRAPPER):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(guard.ROOT / relative, target)

    def test_current_repository_contract_passes(self):
        self.assertEqual([], guard.collect_errors(guard.ROOT))

    def test_guard_fails_if_run270_moves_before_run250(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            wrapper = root / guard.WRAPPER
            text = wrapper.read_text(encoding="utf-8")
            old250 = "        run250.install_body(sys.modules[__name__])"
            old270 = "        run270.install_body(sys.modules[__name__])"
            text = text.replace(old250, "        __RUN270_SWAP__", 1)
            text = text.replace(old270, old250, 1)
            text = text.replace("        __RUN270_SWAP__", old270, 1)
            wrapper.write_text(text, encoding="utf-8")
            self.assertIn("run270_compatibility_order_drifted:body_after_run250", guard.collect_errors(root))

    def test_guard_fails_if_run270_moves_after_current_run307(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            wrapper = root / guard.WRAPPER
            text = wrapper.read_text(encoding="utf-8")
            old270 = "        run270.install_body(sys.modules[__name__])"
            old307 = "        run307.install_body(sys.modules[__name__])"
            text = text.replace(old270, "        __RUN307_SWAP__", 1)
            text = text.replace(old307, old270, 1)
            text = text.replace("        __RUN307_SWAP__", old307, 1)
            wrapper.write_text(text, encoding="utf-8")
            self.assertIn("run270_compatibility_order_drifted:body_before_run307", guard.collect_errors(root))

    def test_guard_rejects_evidence_preservation_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            module = root / guard.MODULE
            text = module.read_text(encoding="utf-8")
            text = text.replace('"evidence_preserved": True', '"evidence_preserved": False', 1)
            module.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertTrue(any(e.startswith("run270_compatibility_missing:") for e in errors))

    def test_guard_rejects_model_or_notion_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            module = root / guard.MODULE
            text = module.read_text(encoding="utf-8") + "\nimport requests\nNOTION_TOKEN = 'x'\n"
            module.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertIn("run270_forbidden_surface:import requests", errors)
            self.assertIn("run270_forbidden_surface:NOTION_TOKEN", errors)

    def test_historical_copy_and_docs_are_not_executable_contracts(self):
        self.assertFalse(hasattr(guard, "PAID_CONTRACT"))
        self.assertFalse(hasattr(guard, "REFERENCE"))
        self.assertFalse(hasattr(guard, "SPEC"))
        self.assertFalse(hasattr(guard, "WORKFLOW"))


if __name__ == "__main__":
    unittest.main()
