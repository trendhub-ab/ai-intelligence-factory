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


if __name__ == "__main__":
    unittest.main()
