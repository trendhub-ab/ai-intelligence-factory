from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (ROOT / "run328_note_profile_settings_probe.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github/workflows/note-profile-settings-probe.yml").read_text(encoding="utf-8")


class Run328NoteProfileSettingsProbeTests(unittest.TestCase):
    def test_exact_public_profile_and_legacy_copy_are_preconditions(self):
        self.assertIn("run311.PUBLIC_PROFILE_URL", SCRIPT)
        self.assertIn("run311.LEGACY_PROFILE", SCRIPT)
        self.assertIn("run311.CURRENT_PROFILE", SCRIPT)
        self.assertIn('"Product Hunt"', SCRIPT)
        self.assertIn("run311._settings_control(page).click()", SCRIPT)

    def test_probe_inventories_current_ui_broadly(self):
        for marker in (
            "entryCandidates",
            "actionCandidates",
            "dialogs",
            "forms",
            "keywordMatches",
            "surface_t1",
            "surface_t3",
            "page.screenshot",
        ):
            self.assertIn(marker, SCRIPT)
        for selector in ("textarea", "input", "[contenteditable]", "[role]", "[data-testid]"):
            self.assertIn(selector, SCRIPT)

    def test_no_save_or_profile_mutation_exists(self):
        self.assertNotIn("_set_profile_field", SCRIPT)
        self.assertNotIn("_save_control", SCRIPT)
        self.assertNotIn(".fill(", SCRIPT)
        self.assertNotIn("keyboard.insert_text", SCRIPT)
        self.assertNotIn('name="保存"', SCRIPT)
        for marker in (
            '"save_control_clicked": False',
            '"field_filled": False',
            '"public_mutation": False',
            '"settings_mutation": False',
            '"zero_gemini_calls": True',
            '"notion_writes": 0',
        ):
            self.assertIn(marker, SCRIPT)

    def test_run328_history_is_preserved_but_live_workflow_is_run329(self):
        old_token = "PROBE_NOTE_PROFILE_SETTINGS_TRENDHUB_BIZ_READONLY"
        new_token = "PROBE_NOTE_PROFILE_DIRECT_ROUTE_TRENDHUB_BIZ_READONLY"
        command = "/aiif note profile probe"
        self.assertIn(old_token, SCRIPT)
        self.assertNotIn(old_token, WORKFLOW)
        self.assertIn(new_token, WORKFLOW)
        self.assertIn(command, WORKFLOW)
        self.assertIn("workflow_dispatch:", WORKFLOW)
        self.assertIn("issue_comment:", WORKFLOW)
        self.assertIn("github.event.issue.number == 71", WORKFLOW)
        self.assertIn("tests.test_run328_note_profile_settings_probe", WORKFLOW)
        self.assertIn("tests.test_run329_note_profile_direct_route_probe", WORKFLOW)
        self.assertIn("run329_note_profile_direct_route_probe.py", WORKFLOW)
        self.assertNotIn("xvfb-run -a python run328_note_profile_settings_probe.py", WORKFLOW)
        self.assertNotIn("schedule:", WORKFLOW)
        self.assertNotIn("push:", WORKFLOW)
        upper = WORKFLOW.upper()
        self.assertNotIn("GEMINI_API", upper)
        self.assertNotIn("GOOGLE_API_KEY", upper)
        self.assertNotIn("NOTION_API", upper)


if __name__ == "__main__":
    unittest.main()
