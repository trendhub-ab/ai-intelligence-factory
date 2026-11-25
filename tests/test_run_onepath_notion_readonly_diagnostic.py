import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

from run_onepath_notion_readonly_diagnostic import probe


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

    def test_http_429_is_specific_and_stops_without_retry(self):
        result = probe(self.fake(429), "private")
        self.assertEqual(result["http_status"], 429)
        self.assertEqual(result["reason"], "HTTP_429_RATE_LIMIT_STOP_NO_RETRY")
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

    def test_workflow_authority(self):
        src = (Path(__file__).resolve().parents[1] / ".github/workflows/onepath-p13-readonly-diagnostic.yml").read_text()
        for field in ("github.actor == 'trendhub-ab'", "github.run_attempt == 1",
                      "github.event.issue.user.login == 'trendhub-ab'",
                      "OWNER_GO_P13_READONLY_DIAGNOSTIC_45509465956",
                      "ref: 0241decaf4b9f5f1d9408e1b30d3d035b4a78500",
                      "runs-on: ubuntu-24.04", "persist-credentials: false",
                      "run_onepath_notion_readonly_diagnostic.py"):
            self.assertIn(field, src)
        for field in ("self-hosted", "gcloud ", "NOTE_STORAGE_STATE_B64",
                      "AIIF_NEXT_GEMINI_API_KEY", "contents: write", "actions: write",
                      "workflow_dispatch:", "schedule:", "push:", "pull_request:",
                      "onepath_reviewed_delivery.py", "onepath_packet_exchange.py",
                      "actions/upload-artifact"):
            self.assertNotIn(field, src)
