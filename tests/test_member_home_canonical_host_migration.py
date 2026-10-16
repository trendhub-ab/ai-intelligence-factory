import unittest
from pathlib import Path
from unittest import mock

import member_presentation_identity as identity
import provision_member_presentation_db as provisioner


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "member-presentation-sync.yml"
RUN221 = ROOT / "docs" / "reference" / "RUN221_MEMBER_DB_HOST_ISOLATION.md"
MIGRATION = ROOT / "docs" / "reference" / "MEMBER_HOME_CANONICAL_HOST_MIGRATION.md"

CANONICAL_DB = "b2787ee0-5b58-4ca7-b4eb-774f60237f1f"
CANONICAL_DS = "7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404"
MEMBER_HOME = "3c5479ff-dca9-8103-bff0-f2d5f408d35f"
FORMER_API_HOST = "3c5479ff-dca9-8178-867c-d9249a3ff5c8"


class _Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class MemberHomeCanonicalHostMigrationTests(unittest.TestCase):
    def test_member_home_is_the_default_physical_host_and_bootstrap_parent(self):
        self.assertEqual(identity.API_HOST_PAGE_ID, MEMBER_HOME)
        self.assertEqual(provisioner.API_HOST_PAGE_ID, MEMBER_HOME)
        self.assertEqual(provisioner.PARENT_PAGE_ID, MEMBER_HOME)

    def test_canonical_identity_and_creation_ban_do_not_change(self):
        self.assertEqual(identity.CANONICAL_DATABASE_ID, CANONICAL_DB)
        self.assertEqual(identity.CANONICAL_DATA_SOURCE_ID, CANONICAL_DS)
        self.assertEqual(identity.ALLOW_CREATE_DEFAULT, "false")

    def test_workflow_pins_member_home_and_keeps_creation_disabled(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f"MEMBER_PRESENTATION_CANONICAL_DATABASE_ID: '{CANONICAL_DB}'", text)
        self.assertIn(f"MEMBER_PRESENTATION_CANONICAL_DATA_SOURCE_ID: '{CANONICAL_DS}'", text)
        self.assertIn(f"MEMBER_PRESENTATION_API_HOST_PAGE_ID: '{MEMBER_HOME}'", text)
        self.assertNotIn(f"MEMBER_PRESENTATION_API_HOST_PAGE_ID: '{FORMER_API_HOST}'", text)
        self.assertIn("MEMBER_PRESENTATION_ALLOW_CREATE: 'false'", text)
        self.assertNotIn("GEMINI_API_KEY", text)

    def test_database_under_member_home_passes_host_verification(self):
        with mock.patch.object(provisioner, "API_HOST_PAGE_ID", MEMBER_HOME), \
             mock.patch.object(provisioner.requests, "get", return_value=_Response(200, {
                 "parent": {"type": "page_id", "page_id": MEMBER_HOME}
             })):
            provisioner._verify_api_host()

    def test_database_under_former_run221_host_fails_closed(self):
        with mock.patch.object(provisioner, "API_HOST_PAGE_ID", MEMBER_HOME), \
             mock.patch.object(provisioner.requests, "get", return_value=_Response(200, {
                 "parent": {"type": "page_id", "page_id": FORMER_API_HOST}
             })):
            with self.assertRaisesRegex(RuntimeError, "physical host mismatch"):
                provisioner._verify_api_host()

    def test_run221_is_historical_and_new_migration_reference_is_authoritative(self):
        run221 = RUN221.read_text(encoding="utf-8")
        self.assertIn("Status: **superseded**", run221)
        self.assertIn(FORMER_API_HOST, run221)
        self.assertTrue(MIGRATION.exists())
        migration = MIGRATION.read_text(encoding="utf-8")
        for marker in (
            MEMBER_HOME,
            CANONICAL_DB,
            CANONICAL_DS,
            "240",
            "MEMBER_HOME_API_ACCESS=PASS",
            "rollback",
            "zero model calls",
            "no Daily",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, migration)


if __name__ == "__main__":
    unittest.main()
