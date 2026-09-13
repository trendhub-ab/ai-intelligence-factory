from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import run307_use_decision_product_guard as guard

ROOT = Path(__file__).resolve().parents[1]


class Run307UseDecisionProductGuardTests(unittest.TestCase):
    def _copy_contract(self, root: Path) -> None:
        for relative in (
            guard.MODULE,
            guard.WRAPPER,
            guard.WORKFLOW,
            guard.NOTE_FORMAT,
            guard.PAID_CONTRACT,
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text((ROOT / relative).read_text(encoding="utf-8"), encoding="utf-8")

    def test_current_repository_contract_passes(self):
        self.assertEqual([], guard.collect_errors(ROOT))

    def test_missing_current_member_heading_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            module = root / guard.MODULE
            module.write_text(module.read_text(encoding="utf-8").replace('"いま、使える？"', '"いま、どうする？"'), encoding="utf-8")
            self.assertTrue(any("member_surface_missing" in error for error in guard.collect_errors(root)))

    def test_client_proposal_cannot_be_promoted_back_to_primary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            module = root / guard.MODULE
            module.write_text(module.read_text(encoding="utf-8").replace('"client_proposal_primary": False', '"client_proposal_primary": True'), encoding="utf-8")
            self.assertTrue(any("member_surface_missing" in error for error in guard.collect_errors(root)))

    def test_current_surface_must_install_after_compatibility_layer(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            wrapper = root / guard.WRAPPER
            text = wrapper.read_text(encoding="utf-8")
            a = "        run270.install_body(sys.modules[__name__])"
            b = "        run307.install_body(sys.modules[__name__])"
            self.assertIn(a, text)
            self.assertIn(b, text)
            text = text.replace(a, "        __SWAP__", 1).replace(b, a, 1).replace("        __SWAP__", b, 1)
            wrapper.write_text(text, encoding="utf-8")
            self.assertIn("current_member_surface_must_install_after_compatibility:body", guard.collect_errors(root))

    def test_model_or_notion_dependency_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            module = root / guard.MODULE
            module.write_text(module.read_text(encoding="utf-8") + "\nimport requests\nNOTION_TOKEN = 'x'\n", encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertIn("member_surface_forbidden_dependency:import requests", errors)
            self.assertIn("member_surface_forbidden_dependency:NOTION_TOKEN", errors)


if __name__ == "__main__":
    unittest.main()
