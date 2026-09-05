import json
import tempfile
import unittest
from pathlib import Path

import notion_access_policy_guard as guard


class NotionAccessPolicyGuardTests(unittest.TestCase):
    def test_rejects_mcp_query_symbol(self):
        failures = guard.find_forbidden_patterns("client.query_data_sources(payload)")
        self.assertTrue(failures)

    def test_rejects_explicit_sql_mode(self):
        failures = guard.find_forbidden_patterns('payload = {"mode": "sql"}')
        self.assertTrue(failures)

    def test_allows_public_api_and_view_language(self):
        text = (
            'requests.post("https://api.notion.com/v1/data_sources/id/query")\n'
            'preferred_mode = "view"\n'
        )
        self.assertEqual(guard.find_forbidden_patterns(text), [])

    def test_repository_scan_ignores_tests_but_checks_production(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tests").mkdir()
            (root / "tests" / "fixture.py").write_text(
                'payload = {"mode": "sql"}', encoding="utf-8"
            )
            (root / "runtime.py").write_text(
                'requests.get("https://api.notion.com/v1/data_sources/x")',
                encoding="utf-8",
            )
            self.assertEqual(guard.scan_repository(root), [])

            (root / "bad_runtime.py").write_text(
                "client.query_data_sources({})", encoding="utf-8"
            )
            failures = guard.scan_repository(root)
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0]["file"], "bad_runtime.py")

    def test_repository_manifest_covers_every_registered_database(self):
        root = Path(guard.__file__).resolve().parent
        data = guard.load_audit_manifest(root)
        self.assertEqual(guard.validate_audit_manifest(data), [])
        self.assertEqual(
            set(data["databases"]),
            guard.EXPECTED_AUDIT_DATABASE_KEYS,
        )

    def test_manifest_rejects_missing_database_and_bad_view_id(self):
        root = Path(guard.__file__).resolve().parent
        data = json.loads((root / guard.AUDIT_MANIFEST).read_text(encoding="utf-8"))
        data["databases"].pop("decision_monthly")
        data["databases"]["content_intelligence"]["views"]["ready_articles"] = "bad"
        failures = guard.validate_audit_manifest(data)
        reasons = " | ".join(item["reason"] for item in failures)
        self.assertIn("missing audit contract", reasons)
        self.assertIn("invalid view id", reasons)

    def test_member_manifest_rejects_stale_pre_run220_canonical_ids(self):
        root = Path(guard.__file__).resolve().parent
        data = json.loads((root / guard.AUDIT_MANIFEST).read_text(encoding="utf-8"))
        member = data["databases"]["member_presentation"]
        member["database_id"] = "d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1"
        member["data_source_id"] = "d1461b6f-0940-4bf9-803a-6686a37c4ba2"

        failures = guard.validate_audit_manifest(data)
        reasons = " | ".join(item["reason"] for item in failures)
        self.assertIn("stale_canonical_id: field=database_id", reasons)
        self.assertIn("stale_canonical_id: field=data_source_id", reasons)
        self.assertIn(guard.MEMBER_PRESENTATION_CANONICAL_DATABASE_ID, reasons)
        self.assertIn(guard.MEMBER_PRESENTATION_CANONICAL_DATA_SOURCE_ID, reasons)


if __name__ == "__main__":
    unittest.main()
