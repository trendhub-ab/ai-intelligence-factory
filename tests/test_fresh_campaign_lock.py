"""Offline adversarial tests for the stage-3 Fresh-only lock."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import fresh_campaign_lock as fresh


def _env():
    return {
        "AIIF_LOCAL_SKILLS_CANARY_SOURCE": "GitHub",
        "AIIF_FRESH_CAMPAIGN_LOCK": "true",
        "AIIF_RUN_MODE": "local_skills_canary_validation",
        "AIIF_X_DISCOVERY_ENABLED": "false",
        "AIIF_GEMINI_TEMP_EXCLUDED_MODELS": "",
        "FRESH_SUPPLY_TRIAL_PROTOCOL": "",
        "GEMINI_SCREENING_MODEL_CANDIDATES": fresh.EXPECTED_SCREENING,
        "GEMINI_DEEP_DIVE_MODEL_CANDIDATES": fresh.EXPECTED_DEEP_DIVE,
        "MAX_SCREENING_CANDIDATES": "200",
        "GITHUB_FETCH_LIMIT": "50", "HN_FETCH_LIMIT": "50",
        "ARXIV_FETCH_LIMIT": "50", "OFFICIAL_VENDOR_FETCH_LIMIT": "50",
        "GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET": "1",
        "GEMINI_API_KEY": "dummy-never-used", "GH_PAT": "dummy",
        "NOTION_API_KEY": "dummy",
    }


class FakeProviderError(Exception):
    def __init__(self, code):
        super().__init__(str(code))
        self.code = code


class FreshCampaignLockTests(TestCase):
    def test_source_and_credentials_are_required_before_any_external_call(self):
        self.assertEqual(fresh.verify_environment(_env()), "GitHub")
        for key, bad in (
            ("AIIF_LOCAL_SKILLS_CANARY_SOURCE", ""),
            ("AIIF_LOCAL_SKILLS_CANARY_SOURCE", "ProductHunt"),
            ("AIIF_FRESH_CAMPAIGN_LOCK", "false"),
            ("GEMINI_API_KEY", ""),
            ("AIIF_GEMINI_TEMP_EXCLUDED_MODELS", "gemini-3.5-flash"),
            ("GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET", "12"),
            ("FRESH_SUPPLY_TRIAL_PROTOCOL", "source-supply-gh-3-cohorts-v1"),
        ):
            with self.subTest(key=key, bad=bad):
                changed = _env()
                changed[key] = bad
                with self.assertRaises(RuntimeError):
                    fresh.verify_environment(changed)

    def test_503_is_terminal_even_when_fallback_possible(self):
        calls = []
        def provider(*args, **kwargs):
            calls.append(args[0])
            raise FakeProviderError(503)
        with TemporaryDirectory() as td:
            guard = fresh.SendGuard(provider, None, Path(td), "GitHub")
            with self.assertRaises(fresh.FreshCampaignAbort):
                guard.send("gemini-3.5-flash-lite", "synthetic prompt", request_kind="screening")
            self.assertEqual(calls, ["gemini-3.5-flash-lite"])
            audit = json.loads((Path(td) / fresh.AUDIT_RELATIVE).read_text())
            self.assertEqual(audit["status"], "PROVIDER_503_HARD_STOP")
            self.assertEqual(audit["attempted_model_sends"], 1)

    def test_429_is_terminal(self):
        with TemporaryDirectory() as td:
            guard = fresh.SendGuard(
                lambda *a, **kw: (_ for _ in ()).throw(FakeProviderError(429)),
                None, Path(td), "ArXiv"
            )
            with self.assertRaises(fresh.FreshCampaignAbort):
                guard.send("gemini-3.5-flash-lite", "synthetic", request_kind="screening")
            self.assertEqual(guard.total, 1)
            self.assertEqual(guard.status, "PROVIDER_429_HARD_STOP")

    def test_all_attempts_count_including_non_terminal_errors(self):
        calls = []
        def provider(*args, **kw):
            calls.append(1)
            if len(calls) == 1:
                raise FakeProviderError(404)
            return "synthetic"
        with TemporaryDirectory() as td:
            guard = fresh.SendGuard(provider, None, Path(td), "HackerNews")
            with self.assertRaises(FakeProviderError):
                guard.send("gemini-3.5-flash-lite", "synthetic", request_kind="screening")
            for _ in range(fresh.MAX_GEMINI_SENDS - 1):
                guard.send("gemini-3.5-flash-lite", "synthetic", request_kind="screening")
            with self.assertRaises(fresh.FreshCampaignAbort):
                guard.send("gemini-3.5-flash-lite", "synthetic", request_kind="screening")
            self.assertEqual(len(calls), fresh.MAX_GEMINI_SENDS)
            self.assertEqual(guard.status, "MODEL_SEND_BUDGET_EXHAUSTED")

    def test_deep_dive_retry_cannot_spend_second_provider_call(self):
        with TemporaryDirectory() as td:
            calls = []
            guard = fresh.SendGuard(lambda *a, **kw: calls.append(1), None, Path(td), "OfficialVendor")
            guard.send("gemini-3.7-flash", "synthetic", request_kind="deep_dive", count_as_deep_dive=True)
            with self.assertRaises(fresh.FreshCampaignAbort):
                guard.send("gemini-3.8-flash", "synthetic", request_kind="deep_dive_retry",
                           count_as_deep_dive=True)
            self.assertEqual(calls, [1])

    def test_quality_retry_and_unknown_model_are_forbidden(self):
        with TemporaryDirectory() as td:
            guard = fresh.SendGuard(lambda *a, **kw: "ok", None, Path(td), "GitHub")
            for model, kind in (("gemini-3.8-flash", "quality_retry"), ("other-model", "screening")):
                with self.subTest(model=model):
                    with self.assertRaises(fresh.FreshCampaignAbort):
                        guard.send(model, "synthetic", request_kind=kind)
            self.assertEqual(guard.total, 0)

    def test_audit_mismatch_rejects_bypassed_transport(self):
        with TemporaryDirectory() as td:
            guard = fresh.SendGuard(lambda *a, **kw: "ok", None, Path(td), "GitHub")
            guard.send("gemini-3.5-flash-lite", "synthetic", request_kind="screening")
            with self.assertRaises(fresh.FreshCampaignAbort):
                guard.assert_usage_reconciled(SimpleNamespace(
                    GEMINI_USAGE_AUDIT=SimpleNamespace(records=[{}, {}])
                ))
            self.assertEqual(guard.status, "PROVIDER_SEND_LEDGER_MISMATCH")

    def test_unrelated_python_change_requires_new_registration(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            (root / "production_pipeline.py").write_text("entrypoint\n")
            (root / "small.py").write_text("frozen\n")
            with patch.object(fresh, "FROZEN_BLOBS", {"small.py": fresh.git_blob_sha(root / "small.py")}), \
                 patch.object(fresh, "LOCKED_ENTRYPOINT_BLOB", fresh.git_blob_sha(root / "production_pipeline.py")), \
                 patch.object(fresh.subprocess, "run") as proc:
                proc.return_value.stdout = "quality_wrapper.py\n"
                with self.assertRaisesRegex(RuntimeError, "Post-baseline"):
                    fresh.verify_checkout(root)
                proc.return_value.stdout = "tests/new_test.py\nproduction_pipeline.py\nfresh_campaign_lock.py\n"
                fresh.verify_checkout(root)

    def test_live_entrypoint_requires_lock_for_source_specific_run(self):
        source = (Path(__file__).resolve().parents[1] / "production_pipeline.py").read_text()
        self.assertIn("if source and not locked:", source)
        self.assertIn("install_locked_fresh", source)
