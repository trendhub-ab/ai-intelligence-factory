import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")

try:
    from google import genai  # noqa: F401
except ImportError:
    google_mod = sys.modules.get("google") or types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")

    class APIError(Exception):
        pass

    class Client:
        def __init__(self, **_kwargs):
            self.chats = types.SimpleNamespace(create=lambda **_kw: None)

    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.setdefault("google", google_mod)
    sys.modules["google.genai"] = genai_mod
    sys.modules["google.genai.errors"] = errors_mod

spec = importlib.util.spec_from_file_location("pipeline_attribution_upload_under_test", ROOT / "pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(pipeline)


class TestSubscriptionAttributionGithubUpload(unittest.TestCase):
    def test_existing_manifest_is_read_from_same_runtime_branch_before_update(self):
        with tempfile.TemporaryDirectory() as directory:
            local_path = Path(directory) / "aif-test.json"
            local_path.write_text('{"article_id":"aif-test"}\n', encoding="utf-8")

            def fake_get(_url, **kwargs):
                if kwargs.get("params") == {"ref": "runtime-state"}:
                    return types.SimpleNamespace(
                        status_code=200,
                        text="",
                        json=lambda: {"sha": "existing-sha"},
                    )
                return types.SimpleNamespace(status_code=404, text="", json=lambda: {})

            def fake_put(_url, **kwargs):
                payload = kwargs["json"]
                status = 200 if payload.get("sha") == "existing-sha" else 422
                return types.SimpleNamespace(
                    status_code=status,
                    text="" if status == 200 else '"sha" wasn\'t supplied',
                    json=lambda: {"content": {"download_url": "https://example.com/aif-test.json"}},
                )

            with patch.object(
                pipeline, "GH_PAT", "test-token"
            ), patch.object(
                pipeline, "EYECATCH_GITHUB_REPO", "trendhub-ab/ai-intelligence-factory"
            ), patch.object(
                pipeline, "EYECATCH_GITHUB_BRANCH", "runtime-state"
            ), patch.object(
                pipeline.requests, "get", side_effect=fake_get
            ) as get_mock, patch.object(
                pipeline.requests, "put", side_effect=fake_put
            ) as put_mock:
                pipeline._upload_subscription_attribution_to_github(
                    str(local_path), "aif-test"
                )

            self.assertEqual(
                {"ref": "runtime-state"},
                get_mock.call_args.kwargs.get("params"),
            )
            payload = put_mock.call_args.kwargs["json"]
            self.assertEqual("runtime-state", payload["branch"])
            self.assertEqual("existing-sha", payload.get("sha"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
