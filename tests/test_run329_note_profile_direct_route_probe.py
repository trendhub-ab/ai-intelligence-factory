from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "run329_note_profile_direct_route_probe.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/note-profile-settings-probe.yml").read_text(encoding="utf-8")


class Run329NoteProfileDirectRouteProbeTests(unittest.TestCase):
    def test_exact_audited_route_is_required(self):
        self.assertIn('PROFILE_SETTINGS_URL = "https://note.com/settings/profile"', SCRIPT)
        self.assertIn("run311._settings_control(page)", SCRIPT)
        self.assertIn('control.get_attribute("href")', SCRIPT)
        self.assertIn("if href != PROFILE_SETTINGS_URL", SCRIPT)
        self.assertIn("page.goto(PROFILE_SETTINGS_URL", SCRIPT)

    def test_public_legacy_profile_remains_exact_precondition(self):
        self.assertIn("run311.PUBLIC_PROFILE_URL", SCRIPT)
        self.assertIn("run311.LEGACY_PROFILE", SCRIPT)
        self.assertIn("run311.CURRENT_PROFILE", SCRIPT)
        self.assertIn('"Product Hunt"', SCRIPT)

    def test_probe_has_zero_click_zero_save_zero_fill_contract(self):
        self.assertNotIn(".click()", SCRIPT)
        self.assertNotIn(".fill(", SCRIPT)
        self.assertNotIn("keyboard.insert_text", SCRIPT)
        self.assertNotIn("_set_profile_field", SCRIPT)
        self.assertNotIn("_save_control", SCRIPT)
        for marker in (
            '"settings_control_clicked": False',
            '"save_control_clicked": False',
            '"field_filled": False',
            '"public_mutation": False',
            '"settings_mutation": False',
            '"clicks_performed": 0',
            '"zero_gemini_calls": True',
            '"notion_writes": 0',
        ):
            self.assertIn(marker, SCRIPT)

    def test_probe_reuses_broad_surface_inventory_and_screenshot(self):
        self.assertIn("run328._surface(page)", SCRIPT)
        self.assertIn("pre_surface", SCRIPT)
        self.assertIn("surface_t1", SCRIPT)
        self.assertIn("surface_t3", SCRIPT)
        self.assertIn("page.screenshot", SCRIPT)

    def test_existing_workflow_is_reused_exactly_and_zero_model(self):
        token = "PROBE_NOTE_PROFILE_DIRECT_ROUTE_TRENDHUB_BIZ_READONLY"
        command = "/aiif note profile probe"
        self.assertIn(token, SCRIPT)
        self.assertIn(token, WORKFLOW)
        self.assertIn(command, WORKFLOW)
        self.assertIn("workflow_dispatch:", WORKFLOW)
        self.assertIn("issue_comment:", WORKFLOW)
        self.assertIn("github.event.issue.number == 71", WORKFLOW)
        self.assertIn("run329_note_profile_direct_route_probe.py", WORKFLOW)
        self.assertIn("tests.test_run328_note_profile_settings_probe", WORKFLOW)
        self.assertIn("tests.test_run329_note_profile_direct_route_probe", WORKFLOW)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertNotIn("push:", WORKFLOW)
        upper = WORKFLOW.upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
