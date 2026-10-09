import unittest
from pathlib import Path

import member_presentation_identity as identity


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "member-presentation-sync.yml"
RUN221 = ROOT / "docs" / "reference" / "RUN221_MEMBER_DB_HOST_ISOLATION.md"
MIGRATION = ROOT / "docs" / "reference" / "MEMBER_HOME_PHYSICAL_HOST_MIGRATION_2026-10-10.md"

MEMBER_HOME = "3c5479ff-dca9-8103-bff0-f2d5f408d35f"
PRE_MIGRATION_API_HOST = "3c5479ff-dca9-8178-867c-d9249a3ff5c8"
CANONICAL_DB = "b2787ee0-5b58-4ca7-b4eb-774f60237f1f"
CANONICAL_DS = "7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404"
DECISION_BRIEF = "3d0479ff-dca9-81de-b614-fef528d2f32c"


class MemberHomePhysicalHostMigrationTests(unittest.TestCase):
    def test_current_api_host_is_member_home(self):
        self.assertEqual(identity.API_HOST_PAGE_ID, MEMBER_HOME)

    def test_production_workflow_pins_member_home_as_physical_host(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f"MEMBER_PRESENTATION_API_HOST_PAGE_ID: '{MEMBER_HOME}'", text)
        self.assertNotIn(f"MEMBER_PRESENTATION_API_HOST_PAGE_ID: '{PRE_MIGRATION_API_HOST}'", text)
        self.assertIn("MEMBER_PRESENTATION_ALLOW_CREATE: 'false'", text)
        self.assertNotIn("GEMINI_API_KEY", text)

    def test_run221_is_preserved_as_superseded_history(self):
        text = RUN221.read_text(encoding="utf-8")
        self.assertIn("Status: **superseded", text)
        self.assertIn(PRE_MIGRATION_API_HOST, text)
        self.assertIn("HTTP 404", text)

    def test_migration_record_captures_identity_and_read_proof(self):
        self.assertTrue(MIGRATION.exists(), "migration record must exist")
        text = MIGRATION.read_text(encoding="utf-8")
        for marker in (
            MEMBER_HOME,
            PRE_MIGRATION_API_HOST,
            CANONICAL_DB,
            CANONICAL_DS,
            DECISION_BRIEF,
            "38003400357",
            "114066553647",
            "HTTP 200",
            "rollback",
            "Gemini/model calls: **0**",
            "Daily: **not run**",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
