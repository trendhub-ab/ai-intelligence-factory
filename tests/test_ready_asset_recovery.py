import unittest


class ReadyAssetRecoveryContractTests(unittest.TestCase):
    def test_exact_target_only_and_terminal_guard(self):
        from ready_asset_recovery import run_exact_ready_asset_recovery

        calls = []

        class Pipeline:
            logger = None
            def generate_intelligence_report(self, repo, notion_page_id=None, screening_score=None,
                                             screening_reason="", persist_results=True,
                                             candidate_rank=0, candidate_origin="new"):
                calls.append((repo, notion_page_id, persist_results, candidate_origin))
                return ("body", "accepted")

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
        )
        self.assertEqual(blocked["status"], "blocked_terminal")
        self.assertEqual(calls, [])

    def test_failed_or_missing_exact_target_never_dispatches(self):
        from ready_asset_recovery import run_exact_ready_asset_recovery

        class Pipeline:
            logger = None
            def generate_intelligence_report(self, *args, **kwargs):
                raise AssertionError("generation must not run")

        missing = run_exact_ready_asset_recovery(
            Pipeline(),
            "c" * 32,
            load_exact=lambda _pipeline, _sync_id: None,
            regeneration_decision=lambda sync_id: (True, "not_queued"),
        )
        self.assertEqual(missing["status"], "exact_target_missing")

    def test_generation_rejection_does_not_become_ready(self):
        from ready_asset_recovery import run_exact_ready_asset_recovery

        class Pipeline:
            logger = None
            def generate_intelligence_report(self, *args, **kwargs):
                return ("diagnostic body", "rejected")

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
        )
        self.assertEqual(result["status"], "not_ready")
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main()
