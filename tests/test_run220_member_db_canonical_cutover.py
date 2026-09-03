import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import provision_member_presentation_db as provisioner


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "member-presentation-sync.yml"

CANONICAL_DB = "b2787ee0-5b58-4ca7-b4eb-774f60237f1f"
CANONICAL_DS = "7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404"
OLD_DB = "d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1"
OLD_DS = "d1461b6f-0940-4bf9-803a-6686a37c4ba2"


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


class Run220MemberDbCanonicalCutoverTests(unittest.TestCase):
    def test_canonical_ids_are_pinned_in_code(self):
        self.assertEqual(provisioner.CANONICAL_DATABASE_ID, CANONICAL_DB)
        self.assertEqual(provisioner.CANONICAL_DATA_SOURCE_ID, CANONICAL_DS)
        self.assertFalse(provisioner.ALLOW_CREATE)

    def test_workflow_pins_same_destination_and_disables_create(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(CANONICAL_DB, text)
        self.assertIn(CANONICAL_DS, text)
        self.assertIn("MEMBER_PRESENTATION_ALLOW_CREATE: 'false'", text)
        self.assertIn("Resolve canonical member DB", text)
        self.assertNotIn(OLD_DB, text)
        self.assertNotIn(OLD_DS, text)

    def test_provision_uses_canonical_destination_without_search_or_create(self):
        payload = {
            "parent": {"database_id": CANONICAL_DB},
            "title": [{"plain_text": "AI・技術一覧｜判断DB"}],
        }
        with tempfile.TemporaryDirectory() as td:
            env_file = Path(td) / "github_env"
            with mock.patch.object(provisioner.decision_intelligence, "NOTION_DECISION_INTELLIGENCE_API_KEY", "test-key"), \
                 mock.patch.object(provisioner.requests, "get", return_value=_Response(200, payload)) as get_mock, \
                 mock.patch.object(provisioner.requests, "post", side_effect=AssertionError("search/create must not run")), \
                 mock.patch.dict(os.environ, {"GITHUB_ENV": str(env_file)}, clear=False):
                result = provisioner.provision()

            self.assertFalse(result["created"])
            self.assertTrue(result["canonical"])
            self.assertEqual(result["database_id"], CANONICAL_DB)
            self.assertEqual(result["data_source_id"], CANONICAL_DS)
            self.assertEqual(get_mock.call_count, 1)
            env_text = env_file.read_text(encoding="utf-8")
            self.assertIn(f"NOTION_MEMBER_PRESENTATION_DATABASE_ID={CANONICAL_DB}", env_text)
            self.assertIn(f"NOTION_MEMBER_PRESENTATION_DATA_SOURCE_ID={CANONICAL_DS}", env_text)

    def test_unreadable_canonical_destination_fails_closed(self):
        with mock.patch.object(provisioner.decision_intelligence, "NOTION_DECISION_INTELLIGENCE_API_KEY", "test-key"), \
             mock.patch.object(provisioner.requests, "get", return_value=_Response(403)), \
             mock.patch.object(provisioner.requests, "post", side_effect=AssertionError("fallback search/create must not run")):
            with self.assertRaisesRegex(RuntimeError, "refusing to create or select another DB"):
                provisioner.provision()

    def test_parent_mismatch_fails_closed(self):
        payload = {
            "parent": {"database_id": "00000000-0000-0000-0000-000000000000"},
            "title": [{"plain_text": "AI・技術一覧｜判断DB"}],
        }
        with mock.patch.object(provisioner.decision_intelligence, "NOTION_DECISION_INTELLIGENCE_API_KEY", "test-key"), \
             mock.patch.object(provisioner.requests, "get", return_value=_Response(200, payload)), \
             mock.patch.object(provisioner.requests, "post", side_effect=AssertionError("fallback search/create must not run")):
            with self.assertRaisesRegex(RuntimeError, "Canonical member presentation ID mismatch"):
                provisioner.provision()


if __name__ == "__main__":
    unittest.main()
