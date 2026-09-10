from __future__ import annotations

import inspect
import unittest

import run330_note_profile_exact_update as run330


class Run331ProfileFormSnapshotScopeTests(unittest.TestCase):
    def test_snapshot_is_scoped_to_biography_owner_form(self) -> None:
        source = inspect.getsource(run330._form_snapshot)
        self.assertIn("bio.closest('form')", source)
        self.assertIn("root.querySelectorAll('input, textarea, select')", source)
        self.assertNotIn("document.querySelectorAll('input, textarea, select')", source)

    def test_snapshot_excludes_biography_and_nonvisible_framework_controls_but_keeps_switches(self) -> None:
        source = inspect.getsource(run330._form_snapshot)
        self.assertIn("visible(el)", source)
        self.assertIn("editBiography", source)
        self.assertIn("style.opacity !== '0'", source)
        self.assertIn("getAttribute('role')", source)
        self.assertIn("=== 'switch'", source)
        self.assertNotIn("disabled: Boolean(el.disabled)", source)
        self.assertNotIn("index,", source)

    def test_snapshot_is_semantic_and_order_independent(self) -> None:
        source = inspect.getsource(run330._form_snapshot)
        key_source = inspect.getsource(run330._snapshot_key)
        self.assertIn("occurrence", source)
        self.assertIn("rows.sort", source)
        self.assertIn("row.name", source)
        self.assertIn("row.ariaLabel", source)
        self.assertIn("el.value", source)
        self.assertIn("el.checked", source)
        self.assertIn('row.get("role")', key_source)
        self.assertIn('row.get("occurrence")', key_source)

    def test_unrelated_setting_failure_reports_concrete_diff(self) -> None:
        diff_source = inspect.getsource(run330._snapshot_diff)
        require_source = inspect.getsource(run330._require_snapshot_unchanged)
        update_source = inspect.getsource(run330.update_profile)
        self.assertIn("before_map", diff_source)
        self.assertIn("after_map", diff_source)
        self.assertIn("diff:", require_source)
        self.assertIn("_require_snapshot_unchanged", update_source)
        self.assertIn('"before save"', update_source)
        self.assertIn('"after save"', update_source)
        self.assertIn('"on fresh settings verification"', update_source)

    def test_safety_contract_is_unchanged(self) -> None:
        source = inspect.getsource(run330.update_profile)
        self.assertIn("bio.fill(run311.CURRENT_PROFILE)", source)
        self.assertIn("save.click()", source)
        self.assertIn("save_clicks += 1", source)
        self.assertIn("_verify_public_current(page)", source)
        self.assertIn('public_state == "current"', source)
        self.assertNotIn("nickname.fill", source)
        self.assertNotIn("_settings_control(page).click()", source)


if __name__ == "__main__":
    unittest.main()
