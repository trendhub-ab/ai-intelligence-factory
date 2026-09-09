from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import run307_use_decision_product_guard as guard


ROOT = Path(__file__).resolve().parents[1]


class Run307UseDecisionProductGuardTests(unittest.TestCase):
    def test_current_repository_contract_is_documented(self):
        self.assertEqual([], guard.collect_errors(ROOT))

    def test_missing_current_member_heading_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in (
                guard.MODULE,
                guard.WRAPPER,
                guard.WORKFLOW,
                guard.FALSIFICATION,
                guard.NOTE_FORMAT,
                guard.PAID_CONTRACT,
                guard.REFERENCE,
                guard.SPEC,
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                text = (ROOT / relative).read_text(encoding="utf-8")
                if relative == guard.MODULE:
                    text = text.replace('"いま、使える？"', '"いま、どうする？"')
                target.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
        self.assertTrue(any("run307_module_missing" in error for error in errors))

    def test_client_proposal_cannot_be_promoted_back_to_primary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for relative in (
                guard.MODULE,
                guard.WRAPPER,
                guard.WORKFLOW,
                guard.FALSIFICATION,
                guard.NOTE_FORMAT,
                guard.PAID_CONTRACT,
                guard.REFERENCE,
                guard.SPEC,
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                text = (ROOT / relative).read_text(encoding="utf-8")
                if relative == guard.MODULE:
                    text = text.replace('"client_proposal_primary": False', '"client_proposal_primary": True')
                target.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
        self.assertTrue(any("run307_module_missing" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
