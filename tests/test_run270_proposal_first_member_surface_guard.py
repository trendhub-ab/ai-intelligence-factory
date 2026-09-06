from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
import unittest

import run270_proposal_first_member_surface_guard as guard


class Run270ProposalFirstMemberSurfaceGuardTests(unittest.TestCase):
    def _copy_contract(self, root: Path) -> None:
        for relative in (
            guard.MODULE,
            guard.WRAPPER,
            guard.WORKFLOW,
            guard.FALSIFICATION,
            guard.PAID_CONTRACT,
            guard.REFERENCE,
            guard.SPEC,
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(guard.ROOT / relative, target)

    def test_current_repository_contract_passes(self):
        self.assertEqual([], guard.collect_errors(guard.ROOT))

    def test_guard_rejects_run270_before_run250(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            wrapper = root / guard.WRAPPER
            text = wrapper.read_text(encoding="utf-8")
            old250 = "        run250.install_body(sys.modules[__name__])"
            old270 = "        run270.install_body(sys.modules[__name__])"
            self.assertIn(old250, text)
            self.assertIn(old270, text)
            text = text.replace(old250, "        __RUN270_SWAP__", 1)
            text = text.replace(old270, old250, 1)
            text = text.replace("        __RUN270_SWAP__", old270, 1)
            wrapper.write_text(text, encoding="utf-8")
            self.assertIn("run270_must_install_after_run250:body", guard.collect_errors(root))

    def test_guard_rejects_client_proposal_demoted_to_secondary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            module = root / guard.MODULE
            text = module.read_text(encoding="utf-8")
            text = text.replace('"client_proposal_primary": True', '"client_proposal_primary": False', 1)
            module.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertTrue(any(e.startswith("run270_module_missing:") for e in errors))

    def test_guard_rejects_stale_work_first_paid_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            paid = root / guard.PAID_CONTRACT
            text = paid.read_text(encoding="utf-8")
            text += "\n既存表示契約は壊さず、判断・提案メモ側でProposal-Firstへ強める。\n"
            paid.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertTrue(any(e.startswith("paid_contract_stale_work_first:") for e in errors))

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


if __name__ == "__main__":
    unittest.main()
