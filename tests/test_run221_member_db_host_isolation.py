import os
import unittest
from pathlib import Path
from unittest import mock

import provision_member_presentation_db as provisioner


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "member-presentation-sync.yml"
RUN221 = ROOT / "docs" / "reference" / "RUN221_MEMBER_DB_HOST_ISOLATION.md"

CANONICAL_DB = "b2787ee0-5b58-4ca7-b4eb-774f60237f1f"
CANONICAL_DS = "7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404"
MEMBER_HOME = "3c5479ff-dca9-8103-bff0-f2d5f408d35f"
API_HOST = "3c5479ff-dca9-8178-867c-d9249a3ff5c8"


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


class Run221MemberDbHostIsolationTests(unittest.TestCase):
    def test_member_home_and_api_host_are_deliberately_different(self):
        self.assertNotEqual(MEMBER_HOME, API_HOST)
        self.assertEqual(provisioner.API_HOST_PAGE_ID, API_HOST)
        self.assertEqual(provisioner.PARENT_PAGE_ID, API_HOST)

    def test_workflow_pins_api_host_and_disables_creation(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(f"MEMBER_PRESENTATION_CANONICAL_DATABASE_ID: '{CANONICAL_DB}'", text)
        self.assertIn(f"MEMBER_PRESENTATION_CANONICAL_DATA_SOURCE_ID: '{CANONICAL_DS}'", text)
        self.assertIn(f"MEMBER_PRESENTATION_API_HOST_PAGE_ID: '{API_HOST}'", text)
        self.assertIn("MEMBER_PRESENTATION_ALLOW_CREATE: 'false'", text)
        self.assertNotIn("GEMINI_API_KEY", text)

    def test_physical_host_mismatch_fails_closed(self):
        def get(url, **_kwargs):
            if f"/data_sources/{CANONICAL_DS}" in url:
                return _Response(200, {
                    "parent": {"database_id": CANONICAL_DB},
                    "title": [{"plain_text": "AI・技術一覧｜判断DB"}],
                })
            if f"/databases/{CANONICAL_DB}" in url:
                return _Response(200, {"parent": {"type": "page_id", "page_id": MEMBER_HOME}})
            raise AssertionError(url)

        with mock.patch.object(provisioner.decision_intelligence, "NOTION_DECISION_INTELLIGENCE_API_KEY", "test-key"), \
             mock.patch.object(provisioner.requests, "get", side_effect=get), \
             mock.patch.object(provisioner.requests, "post", side_effect=AssertionError("fallback/create must not run")):
            with self.assertRaisesRegex(RuntimeError, "physical host mismatch"):
                provisioner.provision()

    def test_unreadable_database_host_check_fails_closed(self):
        def get(url, **_kwargs):
            if f"/data_sources/{CANONICAL_DS}" in url:
                return _Response(200, {
                    "parent": {"database_id": CANONICAL_DB},
                    "title": [{"plain_text": "AI・技術一覧｜判断DB"}],
                })
            if f"/databases/{CANONICAL_DB}" in url:
                return _Response(404)
            raise AssertionError(url)

        with mock.patch.object(provisioner.decision_intelligence, "NOTION_DECISION_INTELLIGENCE_API_KEY", "test-key"), \
             mock.patch.object(provisioner.requests, "get", side_effect=get), \
             mock.patch.object(provisioner.requests, "post", side_effect=AssertionError("fallback/create must not run")):
            with self.assertRaisesRegex(RuntimeError, "not readable while verifying its API host"):
                provisioner.provision()

    def test_bootstrap_parent_defaults_to_api_host_not_member_home(self):
        self.assertEqual(provisioner.PARENT_PAGE_ID, API_HOST)
        self.assertNotEqual(provisioner.PARENT_PAGE_ID, MEMBER_HOME)

    def test_operator_contract_records_observed_failure_and_linked_view_architecture(self):
        text = RUN221.read_text(encoding="utf-8")
        for marker in (
            CANONICAL_DB,
            CANONICAL_DS,
            MEMBER_HOME,
            API_HOST,
            "physical API host",
            "linked views",
            "HTTP 404",
            "created: False",
            "206",
            "zero_gemini_calls=true",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertIn("must not be physically moved under the member home", text)

    def test_missing_api_host_is_not_accepted_in_normal_operation(self):
        with mock.patch.object(provisioner.decision_intelligence, "NOTION_DECISION_INTELLIGENCE_API_KEY", "test-key"), \
             mock.patch.object(provisioner, "API_HOST_PAGE_ID", ""), \
             mock.patch.object(provisioner.requests, "get", side_effect=AssertionError("host validation should fail before host GET")):
            with self.assertRaisesRegex(RuntimeError, "MEMBER_PRESENTATION_API_HOST_PAGE_ID is required"):
                provisioner._verify_api_host()


if __name__ == "__main__":
    unittest.main()
