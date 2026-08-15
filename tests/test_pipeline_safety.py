import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")


try:
    import requests  # noqa: F401
except ImportError:
    requests_stub = types.ModuleType("requests")
    for name in ("get", "post", "put", "patch"):
        setattr(requests_stub, name, lambda *args, **kwargs: None)
    sys.modules["requests"] = requests_stub

try:
    from google import genai  # noqa: F401
except ImportError:
    google_mod = types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")

    class APIError(Exception):
        pass

    class Client:
        def __init__(self, **kwargs):
            self.chats = types.SimpleNamespace(create=lambda **kw: None)

    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.update({
        "google": google_mod,
        "google.genai": genai_mod,
        "google.genai.errors": errors_mod,
    })


spec = importlib.util.spec_from_file_location("pipeline_under_test", ROOT / "pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(pipeline)


class FakeAPIError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class FakeResponse:
    def __init__(self, status_code=200, text="ok", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}

    def json(self):
        return self._payload


class PipelineSafetyTests(unittest.TestCase):
    def setUp(self):
        pipeline.SESSION_EXHAUSTED_MODELS.clear()
        pipeline.SESSION_UNAVAILABLE_MODELS.clear()

    def test_ssrf_rejects_private_address(self):
        resolved = [(2, 1, 6, "", ("127.0.0.1", 80))]
        with patch.object(pipeline.socket, "getaddrinfo", return_value=resolved):
            with self.assertRaises(ValueError):
                pipeline._validate_public_http_url("http://example.test/private")

    def test_ssrf_accepts_public_address(self):
        resolved = [(2, 1, 6, "", ("93.184.216.34", 443))]
        with patch.object(pipeline.socket, "getaddrinfo", return_value=resolved):
            pipeline._validate_public_http_url("https://example.com/")

    def test_screening_rpd_falls_back_to_next_model(self):
        pipeline.SCREENING_MODEL_POOL = ["primary", "fallback"]
        calls = []

        def fake_generate(model_name, *args, **kwargs):
            calls.append(model_name)
            if model_name == "primary":
                raise FakeAPIError(429, "requestsPerDay quota exceeded")
            return types.SimpleNamespace(text="SCORE=80 REASON=有望")

        def fake_mark(model_name, reason):
            pipeline.SESSION_EXHAUSTED_MODELS.add(model_name)

        with patch.object(pipeline, "APIError", FakeAPIError), \
             patch.object(pipeline, "_generate_via_chat", side_effect=fake_generate), \
             patch.object(pipeline, "_mark_model_exhausted", side_effect=fake_mark), \
             patch.object(pipeline.time, "sleep"):
            response, selected = pipeline._call_screening_pool("p", None, "screening", 3)

        self.assertEqual("fallback", selected)
        self.assertEqual(["primary", "fallback"], calls)
        self.assertIn("primary", pipeline.SESSION_EXHAUSTED_MODELS)
        self.assertIn("SCORE=80", response.text)

    def test_deep_pool_404_is_not_mislabeled_daily_quota(self):
        pipeline.DEEP_DIVE_MODEL_POOL = ["m1", "m2"]
        pipeline.DEEP_DIVE_MODEL_BUDGET.used = 0
        pipeline.DEEP_DIVE_MODEL_BUDGET.budget = 10

        with patch.object(pipeline, "APIError", FakeAPIError), \
             patch.object(pipeline, "_generate_via_chat", side_effect=FakeAPIError(404, "not found")), \
             patch.object(pipeline.time, "sleep"):
            with self.assertRaises(pipeline.NoAvailableModelError):
                pipeline._call_deep_dive_pool("p", None, "deep_dive")

    def test_notion_upgrade_sets_ready_only_after_body_append(self):
        call_order = []

        def fake_patch(url, **kwargs):
            call_order.append(url)
            return FakeResponse(200)

        with patch.object(pipeline, "NOTION_API_KEY", "notion"), \
             patch.object(pipeline, "build_notion_properties", return_value={"Status": "Ready"}), \
             patch.object(pipeline, "build_notion_manuscript_children", return_value=[]), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            ok = pipeline.upgrade_notion_page_with_report(
                "page-id", "name", "url", 80, "score", "what", "why", "why-not",
                "action", "N/A", "manuscript",
            )

        self.assertTrue(ok)
        self.assertIn("/blocks/page-id/children", call_order[0])
        self.assertIn("/pages/page-id", call_order[1])

    def test_failed_notion_save_is_not_returned_as_success(self):
        parsed = {
            "note_draft": "draft", "title_text": "title", "score": 80,
            "score_breakdown_text": "score", "what_text": "what",
            "why_important_text": "why", "why_not_important_text": "why-not",
            "action_text": "action", "paradigm_shift_text": "shift",
            "alternative_comparison_text": "compare", "migration_cost_text": "cost",
        }
        source_info = {
            "sufficient": True, "primary_url": "https://example.com", "context": "source",
            "method": pipeline.GROUNDING_SOURCE_NATIVE,
        }
        grounding = {
            "grounding_status": pipeline.GROUNDING_SOURCE_NATIVE,
            "evidence_urls": ["https://example.com"],
        }
        repo = {
            "nameWithOwner": "example", "description": "desc", "url": "https://example.com",
            "stargazerCount": 1, "source": "HackerNews", "publishedAt": None,
        }

        with patch.multiple(
            pipeline,
            prepare_source_context=lambda repo: source_info,
            call_gemini_grounded_deep_dive=lambda *a, **k: (types.SimpleNamespace(text="x"), grounding),
            _parse_gemini_response=lambda text: parsed.copy(),
            validate_fact_gate=lambda *a, **k: (True, []),
            validate_editorial_gate=lambda *a, **k: (True, []),
            build_clean_note_manuscript=lambda *a, **k: "clean",
            generate_eyecatch_image=lambda *a, **k: "image.png",
            upload_eyecatch_to_github=lambda *a, **k: "https://example.com/image.png",
            save_to_notion=lambda *a, **k: False,
            send_telegram_alert=lambda *a, **k: None,
        ), patch.object(pipeline.os, "makedirs"):
            result = pipeline.generate_intelligence_report(
                repo, notion_page_id=None, screening_score=80, screening_reason="reason",
            )

        self.assertIsNone(result)

    def test_fact_gate_rejects_fabricated_cli(self):
        failures = pipeline._find_unsupported_syntax_claims(
            "```bash\npip install fabricated-package\n```", "official text without commands"
        )
        self.assertTrue(failures)


if __name__ == "__main__":
    unittest.main()
