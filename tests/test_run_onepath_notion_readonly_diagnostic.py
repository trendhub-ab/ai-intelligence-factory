import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

from run_onepath_notion_readonly_diagnostic import probe, MAX_REQUESTS, MAX_SECONDS


class DiagnosticTests(unittest.TestCase):
    def fake(self, status):
        module = SimpleNamespace()
        def builder(*args):
            def request(*args):
                if status != 200:
                    raise HTTPError("https://private.invalid/path", status, "secret", {}, None)
                return SimpleNamespace(status=200)
            return SimpleNamespace(open=request)
        module.build_opener = builder
        def read(method, path, payload, token):
            try:
                return module.build_opener().open(None)
            except HTTPError:
                raise ValueError("P13_NOTION_READ_FAILED") from None
        module._http_readonly = read
        class Client:
            def __init__(self, token, transport):
                self.transport = transport
            def read_inventory(self):
                self.transport("GET", "/v1/data_sources/hidden", None, "private")
                self.transport("GET", "/v1/blocks/hidden/children", None, "private")
                return SimpleNamespace(content_pages=(), queue_rows=(), lineage_documents=())
        module.NotionReadOnlyClient = Client
        return module

    def test_http_429_is_counted_and_unrecovered_error_is_preserved(self):
        result = probe(self.fake(429), "private")
        self.assertEqual(result["http_status"], 429)
        self.assertEqual(result["reason"], "P13_NOTION_READ_FAILED")
        self.assertEqual(result["rate_limit_responses"], 1)
        self.assertEqual(result["requests"], 1)
        self.assertFalse(result["full_inventory_verified"])
        self.assertNotIn("private", str(result))

    def test_budget_never_claims_full_inventory(self):
        result = probe(self.fake(200), "private", max_requests=1)
        self.assertEqual(result["reason"], "PROBE_BUDGET_REACHED")
        self.assertEqual(result["requests"], 1)
        self.assertFalse(result["full_inventory_verified"])

    def test_full_inventory_receipt_is_read_only(self):
        result = probe(self.fake(200), "private")
        self.assertTrue(result["full_inventory_verified"])
        self.assertEqual(result["requests"], 2)
        for key in ("notion_writes", "note_writes", "model_calls"):
            self.assertEqual(result[key], 0)
        self.assertFalse(result["vm_started"])

    def test_full_scan_budget_is_bounded(self):
        self.assertEqual(MAX_REQUESTS, 6000)
        self.assertEqual(MAX_SECONDS, 1800)
        result = probe(self.fake(200), "private", clock=iter([0, 1801]).__next__)
        self.assertEqual(result["reason"], "PROBE_BUDGET_REACHED")
        self.assertEqual(result["requests"], 0)
        self.assertFalse(result["full_inventory_verified"])

    def test_successful_retry_is_counted_and_budget_applies_to_retry(self):
        def recovering():
            module = self.fake(200)
            outcomes = iter([429, 200, 200])
            def builder(*args):
                def request(*args):
                    status = next(outcomes)
                    if status == 429:
                        raise HTTPError("https://private.invalid/path", 429, "secret", {}, None)
                    return SimpleNamespace(status=200)
                return SimpleNamespace(open=request)
            module.build_opener = builder
            def read(method, path, payload, token):
                try:
                    return module.build_opener().open(None)
                except HTTPError:
                    return module.build_opener().open(None)
            module._http_readonly = read
            return module
        result = probe(recovering(), "private")
        self.assertTrue(result["full_inventory_verified"])
        self.assertEqual(result["requests"], 3)
        self.assertEqual(result["rate_limit_responses"], 1)
        self.assertEqual(result["reason"], "NONE")
        result = probe(recovering(), "private", max_requests=1)
        self.assertFalse(result["full_inventory_verified"])
        self.assertEqual(result["requests"], 1)
        self.assertEqual(result["rate_limit_responses"], 1)
        self.assertEqual(result["reason"], "PROBE_BUDGET_REACHED")

    def test_workflow_authority(self):
        src = (Path(__file__).resolve().parents[1] / ".github/workflows/onepath-p13-readonly-diagnostic.yml").read_text()
        for field in ("github.actor == 'trendhub-ab'", "github.run_attempt == 1",
                      "github.event.issue.user.login == 'trendhub-ab'",
                      "OWNER_GO_P13_REPAIRED_READONLY_DIAGNOSTIC_45598412302",
                      "ref: 0a20749c370b3fd1fbd601f479c2b703775d6858",
                      "runs-on: ubuntu-24.04", "timeout-minutes: 35", "persist-credentials: false",
                      "run_onepath_notion_readonly_diagnostic.py"):
            self.assertIn(field, src)
        for field in ("self-hosted", "gcloud ", "NOTE_STORAGE_STATE_B64",
                      "AIIF_NEXT_GEMINI_API_KEY", "contents: write", "actions: write",
                      "workflow_dispatch:", "schedule:", "push:", "pull_request:",
                      "onepath_reviewed_delivery.py", "onepath_packet_exchange.py",
                      "actions/upload-artifact"):
            self.assertNotIn(field, src)
