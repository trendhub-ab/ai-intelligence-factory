import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch

import documentation_freshness_guard as freshness
import member_presentation_identity as identity
import notion_access_policy_guard as access_guard
import provision_member_presentation_db as provisioner


ROOT = Path(__file__).resolve().parents[1]
OLD_DB = "d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1"
OLD_DS = "d1461b6f-0940-4bf9-803a-6686a37c4ba2"
NEW_AUDIT_VIEW = "view://3d1479ff-dca9-8149-8334-000c097549f5"


class _Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class Run232NotionIntegrationReconciliationTests(unittest.TestCase):
    def test_repository_manifest_points_to_canonical_member_db_and_new_view(self):
        data = json.loads((ROOT / "notion_audit_views.json").read_text(encoding="utf-8"))
        member = data["databases"]["member_presentation"]
        self.assertEqual(member["database_id"], identity.CANONICAL_DATABASE_ID)
        self.assertEqual(member["data_source_id"], identity.CANONICAL_DATA_SOURCE_ID)
        self.assertEqual(member["views"]["required_missing"], NEW_AUDIT_VIEW)
        self.assertNotEqual(member["database_id"], OLD_DB)
        self.assertNotEqual(member["data_source_id"], OLD_DS)

    def test_access_guard_rejects_old_member_ids_even_when_view_format_is_valid(self):
        data = access_guard.load_audit_manifest(ROOT)
        data = json.loads(json.dumps(data))
        member = data["databases"]["member_presentation"]
        member["database_id"] = OLD_DB
        member["data_source_id"] = OLD_DS
        failures = access_guard.validate_audit_manifest(data)
        reasons = " | ".join(item["reason"] for item in failures)
        self.assertIn("stale_canonical_id: field=database_id", reasons)
        self.assertIn("stale_canonical_id: field=data_source_id", reasons)

    def test_documentation_freshness_rejects_old_ids_as_active_manifest_values(self):
        stale = json.dumps(
            {
                "databases": {
                    "member_presentation": {
                        "database_id": OLD_DB,
                        "data_source_id": OLD_DS,
                    }
                }
            }
        )
        errors = freshness.member_audit_manifest_errors(stale)
        self.assertTrue(any("retired pre-Run220 database_id" in error for error in errors))
        self.assertTrue(any("retired member data_source_id" in error for error in errors))

    def test_documentation_freshness_accepts_current_manifest(self):
        manifest = (ROOT / "notion_audit_views.json").read_text(encoding="utf-8")
        self.assertEqual(freshness.member_audit_manifest_errors(manifest), [])

    def test_blank_canonical_title_fails_closed_before_host_validation(self):
        response = _Response(
            200,
            {
                "parent": {"database_id": identity.CANONICAL_DATABASE_ID},
                "title": [],
            },
        )
        with patch.object(provisioner.requests, "get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "title could not be read"):
                provisioner._resolve_canonical()

    def test_unexpected_parent_type_has_diagnostic_failure(self):
        response = _Response(200, {"parent": {"type": "workspace", "workspace": True}})
        with patch.object(provisioner.requests, "get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "unexpected parent type 'workspace'"):
                provisioner._verify_api_host()

    def test_cross_db_and_member_sync_pin_identical_canonical_identity(self):
        member_sync = (ROOT / ".github/workflows/member-presentation-sync.yml").read_text(encoding="utf-8")
        cross_db = (ROOT / ".github/workflows/cross-db-contract-guard.yml").read_text(encoding="utf-8")
        expected = {
            "MEMBER_PRESENTATION_CANONICAL_DATABASE_ID": identity.CANONICAL_DATABASE_ID,
            "MEMBER_PRESENTATION_CANONICAL_DATA_SOURCE_ID": identity.CANONICAL_DATA_SOURCE_ID,
            "MEMBER_PRESENTATION_API_HOST_PAGE_ID": identity.API_HOST_PAGE_ID,
            "MEMBER_PRESENTATION_ALLOW_CREATE": identity.ALLOW_CREATE_DEFAULT,
        }
        for key, value in expected.items():
            pattern = re.compile(rf"{re.escape(key)}:\s*['\"]{re.escape(value)}['\"]")
            self.assertRegex(member_sync, pattern, key)
            self.assertRegex(cross_db, pattern, key)

    def test_python_identity_source_is_shared_by_provisioner_and_guards(self):
        provision_source = (ROOT / "provision_member_presentation_db.py").read_text(encoding="utf-8")
        access_source = (ROOT / "notion_access_policy_guard.py").read_text(encoding="utf-8")
        freshness_source = (ROOT / "documentation_freshness_guard.py").read_text(encoding="utf-8")
        for source in (provision_source, access_source, freshness_source):
            self.assertIn("member_presentation_identity", source)


if __name__ == "__main__":
    unittest.main()
