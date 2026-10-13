import unittest


class ReadyAssetRecoveryContractTests(unittest.TestCase):
    def test_exact_target_only_and_terminal_guard(self):
        from operational_output_contract import run_exact_ready_asset_recovery

        calls = []

        class Pipeline:
            logger = None
            def generate_intelligence_report(self, repo, notion_page_id=None, screening_score=None,
                                             screening_reason="", persist_results=True,
                                             candidate_rank=0, candidate_origin="new"):
                calls.append((repo, notion_page_id, persist_results, candidate_origin))
                return "body"

        item = {
            "notion_page_id": "a" * 32,
            "screening_score": 65,
            "screening_reason": "asset persistence recovery",
            "repo": {"nameWithOwner": "Exact Article", "source": "ArXiv"},
        }
        result = run_exact_ready_asset_recovery(
            Pipeline(),
            "a" * 32,
            load_exact=lambda _pipeline, sync_id: item if sync_id == "a" * 32 else None,
            regeneration_decision=lambda sync_id: (True, "not_queued"),
            verify_ready=lambda _pipeline, sync_id: sync_id == "a" * 32,
        )
        self.assertEqual(result["status"], "ready_recovered")
        self.assertEqual(result["sync_id"], "a" * 32)
        self.assertEqual(calls, [(item["repo"], "a" * 32, True, "ready_asset_recovery")])

        calls.clear()
        blocked = run_exact_ready_asset_recovery(
            Pipeline(),
            "b" * 32,
            load_exact=lambda _pipeline, _sync_id: item,
            regeneration_decision=lambda sync_id: (False, "delivery_state_already_delivered"),
            verify_ready=lambda _pipeline, _sync_id: True,
        )
        self.assertEqual(blocked["status"], "blocked_terminal")
        self.assertEqual(calls, [])

    def test_failed_or_missing_exact_target_never_dispatches(self):
        from operational_output_contract import run_exact_ready_asset_recovery

        class Pipeline:
            logger = None
            def generate_intelligence_report(self, *args, **kwargs):
                raise AssertionError("generation must not run")

        missing = run_exact_ready_asset_recovery(
            Pipeline(),
            "c" * 32,
            load_exact=lambda _pipeline, _sync_id: None,
            regeneration_decision=lambda sync_id: (True, "not_queued"),
            verify_ready=lambda _pipeline, _sync_id: True,
        )
        self.assertEqual(missing["status"], "exact_target_missing")

    def test_truthy_generation_without_persisted_ready_stays_not_ready(self):
        from operational_output_contract import run_exact_ready_asset_recovery

        class Pipeline:
            logger = None
            def generate_intelligence_report(self, *args, **kwargs):
                return "quality-pass manuscript"

        item = {
            "notion_page_id": "d" * 32,
            "screening_score": 65,
            "screening_reason": "asset persistence recovery",
            "repo": {"nameWithOwner": "Exact Article", "source": "ArXiv"},
        }
        result = run_exact_ready_asset_recovery(
            Pipeline(),
            "d" * 32,
            load_exact=lambda _pipeline, _sync_id: item,
            regeneration_decision=lambda sync_id: (True, "not_queued"),
            verify_ready=lambda _pipeline, _sync_id: False,
        )
        self.assertEqual(result["status"], "not_ready")
        self.assertFalse(result["ready"])

    def test_loader_reads_exact_page_directly_instead_of_scanning_recent_rows(self):
        from operational_output_contract import load_exact_existing_item

        target = "e" * 32
        calls = []

        class Response:
            status_code = 200
            def json(self):
                return {
                    "id": target,
                    "properties": {
                        "Name": {"title": [{"plain_text": "Task Context Shapes Component Roles in Language Models"}]},
                        "URL": {"url": "https://arxiv.org/abs/2610.13895"},
                        "Source": {"select": {"name": "ArXiv"}},
                        "Source Summary": {"rich_text": [{"plain_text": "summary"}]},
                        "Engagement": {"number": 0},
                        "Screening Score": {"number": 65},
                        "Screening Reason": {"rich_text": [{"plain_text": "publication reliability slot"}]},
                        "Published At": {"date": {"start": "2026-10-13"}},
                        "License": {"rich_text": []},
                    },
                }

        class Requests:
            def get(self, url, headers=None, timeout=None):
                calls.append(url)
                return Response()

        class Pipeline:
            requests = Requests()
            PROP_NAME = "Name"
            PROP_URL = "URL"
            PROP_SOURCE = "Source"
            PROP_SOURCE_SUMMARY = "Source Summary"
            PROP_ENGAGEMENT = "Engagement"
            PROP_SCREENING_SCORE = "Screening Score"
            PROP_SCREENING_REASON = "Screening Reason"
            PROP_PUBLISHED_AT = "Published At"
            PROP_LICENSE = "License"
            NOTION_SAVE_THRESHOLD_SCORE = 60
            @staticmethod
            def _notion_headers():
                return {"Authorization": "test"}
            @staticmethod
            def _notion_plain_text(prop):
                rows = prop.get("title") or prop.get("rich_text") or []
                return "".join(row.get("plain_text", "") for row in rows)

        item = load_exact_existing_item(Pipeline(), target)
        self.assertEqual(calls, [f"https://api.notion.com/v1/pages/{target}"])
        self.assertEqual(item["notion_page_id"], target)
        self.assertEqual(item["repo"]["source"], "ArXiv")
        self.assertEqual(item["repo"]["url"], "https://arxiv.org/abs/2610.13895")

    def test_persisted_ready_verifier_reads_exact_page(self):
        from operational_output_contract import exact_page_is_ready

        target = "f" * 32
        calls = []

        class Response:
            status_code = 200
            def json(self):
                return {"id": target, "properties": {"Article Status": {"select": {"name": "Ready"}}}}

        class Requests:
            def get(self, url, headers=None, timeout=None):
                calls.append(url)
                return Response()

        class Pipeline:
            requests = Requests()
            PROP_ARTICLE_STATUS = "Article Status"
            ARTICLE_STATUS_READY = "Ready"
            @staticmethod
            def _notion_headers():
                return {"Authorization": "test"}

        self.assertTrue(exact_page_is_ready(Pipeline(), target))
        self.assertEqual(calls, [f"https://api.notion.com/v1/pages/{target}"])


if __name__ == "__main__":
    unittest.main()
