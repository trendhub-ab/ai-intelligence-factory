import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import run203_runtime_state_channel as run203


class _Response:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class Run203RuntimeStateChannelTests(unittest.TestCase):
    def test_stale_main_workflow_settings_migrate_to_runtime_state(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "GEMINI_COUNTER_BRANCH": "main",
            "EYECATCH_GITHUB_BRANCH": "main",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(run203.resolve_runtime_state_branch(), "runtime-state")

    def test_explicit_main_runtime_state_is_hard_rejected(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "AIIF_RUNTIME_STATE_BRANCH": "main",
            "GEMINI_COUNTER_BRANCH": "runtime-state",
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(RuntimeError, "must never target"):
                run203.resolve_runtime_state_branch()

    def test_synthetic_import_remains_side_effect_free(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "SYNTHETIC_REGRESSION_MODE": "true",
            "GEMINI_COUNTER_BRANCH": "main",
        }
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(run203.resolve_runtime_state_branch(), "")

    def test_install_redirects_all_shared_state_and_existing_counter(self):
        counter = SimpleNamespace(branch="main")
        fake_pipeline = SimpleNamespace(
            EYECATCH_GITHUB_BRANCH="main",
            GEMINI_COUNTER_BRANCH="main",
            PERSISTENT_GEMINI_COUNTER=counter,
        )
        with tempfile.TemporaryDirectory() as tmp:
            github_env = Path(tmp) / "github_env"
            env = {
                "GITHUB_ACTIONS": "true",
                "GEMINI_COUNTER_BRANCH": "main",
                "EYECATCH_GITHUB_BRANCH": "main",
                "GITHUB_ENV": str(github_env),
            }
            with patch.dict(os.environ, env, clear=True):
                run203.install(fake_pipeline)
                self.assertEqual(fake_pipeline.EYECATCH_GITHUB_BRANCH, "runtime-state")
                self.assertEqual(fake_pipeline.GEMINI_COUNTER_BRANCH, "runtime-state")
                self.assertEqual(counter.branch, "runtime-state")
                self.assertEqual(os.environ["GEMINI_COUNTER_BRANCH"], "runtime-state")
                persisted = github_env.read_text(encoding="utf-8")
                self.assertIn("AIIF_RUNTIME_STATE_BRANCH=runtime-state", persisted)
                self.assertIn("GEMINI_COUNTER_BRANCH=runtime-state", persisted)
                self.assertIn("EYECATCH_GITHUB_BRANCH=runtime-state", persisted)

    def test_preflight_proves_same_pat_can_write_runtime_state_not_main(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "trendhub-ab/ai-intelligence-factory",
            "GITHUB_RUN_ID": "12345",
            "GH_PAT": "test-token",
            "GEMINI_COUNTER_BRANCH": "main",
            "EYECATCH_GITHUB_BRANCH": "main",
        }
        get = Mock(side_effect=[_Response(200), _Response(404)])
        put = Mock(return_value=_Response(201, {"content": {"sha": "new"}}))
        http = SimpleNamespace(get=get, put=put)
        with patch.dict(os.environ, env, clear=True), \
             patch.object(run203, "_http_client", return_value=http):
            result = run203.preflight_runtime_state_channel()

        self.assertEqual(result["branch"], "runtime-state")
        self.assertEqual(result["path"], run203.RUNTIME_STATE_HEALTH_PATH)
        branch_url = get.call_args_list[0].args[0]
        self.assertTrue(branch_url.endswith("/branches/runtime-state"))
        write = put.call_args.kwargs["json"]
        self.assertEqual(write["branch"], "runtime-state")
        self.assertNotEqual(write["branch"], "main")
        self.assertEqual(put.call_args.kwargs["headers"]["Authorization"], "Bearer test-token")

    def test_preflight_fails_before_provider_when_runtime_state_is_not_writable(self):
        env = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_REPOSITORY": "trendhub-ab/ai-intelligence-factory",
            "GH_PAT": "test-token",
            "GEMINI_COUNTER_BRANCH": "main",
        }
        get = Mock(side_effect=[_Response(200), _Response(404)])
        put = Mock(return_value=_Response(409, text="repository rule violation"))
        http = SimpleNamespace(get=get, put=put)
        with patch.dict(os.environ, env, clear=True), \
             patch.object(run203, "_http_client", return_value=http):
            with self.assertRaisesRegex(RuntimeError, "write preflight failed"):
                run203.preflight_runtime_state_channel()

    def test_production_entrypoint_installs_and_preflights_infra_before_pipeline(self):
        text = Path("production_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("import run203_runtime_state_channel as runtime_state_channel", text)
        self.assertIn("runtime_state_channel.install(pipeline_module)", text)
        self.assertIn("runtime_state_channel.preflight_runtime_state_channel()", text)
        self.assertLess(
            text.index("runtime_state_channel.install(pipeline_module)"),
            text.index("run172_production_reliability.install(pipeline_module)"),
        )
        self.assertLess(
            text.index("runtime_state_channel.preflight_runtime_state_channel()"),
            text.index("pipeline.main()"),
        )
        # Runtime-state isolation is infrastructure, not article policy. Keeping the
        # alias prevents the publication-policy Run-layer detector from invalidating
        # Ready manuscripts for operational-only changes.
        self.assertNotIn("run203_runtime_state_channel.install(pipeline_module)", text)

    def test_inventory_apply_uses_same_state_preflight_but_plan_stays_read_only(self):
        text = Path("portfolio_inventory_bootstrap.py").read_text(encoding="utf-8")
        self.assertIn("run203_runtime_state_channel.apply_runtime_state_env()", text)
        self.assertIn('str(sys.argv[1]).lower() == "apply"', text)
        self.assertIn("run203_runtime_state_channel.preflight_runtime_state_channel()", text)


if __name__ == "__main__":
    unittest.main()
