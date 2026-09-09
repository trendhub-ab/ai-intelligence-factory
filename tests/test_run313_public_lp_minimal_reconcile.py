from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import run313_public_lp_minimal_reconcile as run313

ROOT = Path(__file__).resolve().parents[1]


class Run313PublicLpMinimalReconcileTests(unittest.TestCase):
    def test_exact_audited_state_is_hard_bound(self) -> None:
        self.assertEqual(run313.run310.TARGET_NOTE_ID, "ned673e381ef8")
        self.assertEqual(
            run313.EXPECTED_BODY_SHA256,
            "3e3569378f388634c02d107d11672dd05958bbee4c4b4a6c9a2368af415f4b5c",
        )
        self.assertEqual(
            run313.CONFIRM_TOKEN,
            "RECONCILE_PUBLIC_LP_NED673E381EF8_SHA3E356937",
        )

    def test_scope_is_exactly_two_text_corrections(self) -> None:
        self.assertEqual(run313.LEGACY_PREFIX_START, "そんな人のために作りました。")
        self.assertIn("これは知っておいた", run313.LEGACY_PREFIX_END)
        self.assertEqual(run313.MOBILE_OLD, "PC・スマートフォン対応")
        self.assertEqual(
            run313.MOBILE_NEW,
            "PCでの利用を推奨（スマートフォン向け簡易ビューあり）",
        )
        self.assertIn("このAI、使える！", run313.CANONICAL_BODY_START)

    def test_reconciler_never_full_body_pastes(self) -> None:
        source = inspect.getsource(run313.reconcile)
        for forbidden in (
            "_paste_manuscript(",
            "_set_title(",
            "replace_content",
            "innerHTML =",
            "fill(",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("_select_unique_text_span", source)
        self.assertIn("_select_exact_text", source)
        self.assertIn('page.keyboard.press("Backspace")', source)
        self.assertIn("page.keyboard.insert_text(MOBILE_NEW)", source)

    def test_text_range_selector_maps_exact_unique_strings_to_dom_range_without_mutation(self) -> None:
        source = inspect.getsource(run313._select_unique_text_span)
        self.assertIn("document.createTreeWalker", source)
        self.assertIn("NodeFilter.SHOW_TEXT", source)
        self.assertIn("joined.indexOf(startNeedle)", source)
        self.assertIn("document.createRange", source)
        self.assertIn("selection.addRange(range)", source)
        for forbidden in ("removeChild", "innerHTML =", "textContent =", ".click()", ".fill("):
            self.assertNotIn(forbidden, source)

    def test_body_drift_fails_closed_except_verified_idempotent_state(self) -> None:
        source = inspect.getsource(run313.reconcile)
        self.assertIn("_sha256(original_text) != EXPECTED_BODY_SHA256", source)
        self.assertIn('"already_reconciled"', source)
        self.assertIn("refuses body drift", source)
        self.assertIn("_verify_public(page)", source)

    def test_membership_cta_and_product_markers_are_preserved(self) -> None:
        source = inspect.getsource(run313._validate_reconciled_editor)
        self.assertIn('a[href*="note.com/trendhub_biz/membership"]', source)
        self.assertIn("REQUIRED_MARKERS", source)
        self.assertIn("MOBILE_NEW", source)
        public_source = inspect.getsource(run313._verify_public)
        self.assertIn("LEGACY_PREFIX_START", public_source)
        self.assertIn("MOBILE_OLD", public_source)
        self.assertIn("membership", public_source)

    def test_workflow_is_exact_manual_and_zero_model(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "note-public-lp-reconcile.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("RECONCILE_PUBLIC_LP_NED673E381EF8_SHA3E356937", workflow)
        self.assertIn("run313_public_lp_minimal_reconcile.py", workflow)
        self.assertNotIn("schedule:", workflow)
        self.assertNotIn("push:", workflow)
        self.assertIn("zero Gemini calls", workflow)


if __name__ == "__main__":
    unittest.main()
