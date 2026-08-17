import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", "0")

try:
    import requests  # noqa: F401
except ImportError:
    requests = types.ModuleType("requests")
    for name in ("get", "post", "put", "patch"):
        setattr(requests, name, lambda *args, **kwargs: None)
    sys.modules["requests"] = requests

try:
    from google import genai  # noqa: F401
except ImportError:
    google_mod = types.ModuleType("google")
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
    sys.modules.update({"google": google_mod, "google.genai": genai_mod, "google.genai.errors": errors_mod})

try:
    from PIL import Image as PillowImage  # noqa: F401
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    pil_mod = types.ModuleType("PIL")
    image_mod = types.ModuleType("PIL.Image")
    draw_mod = types.ModuleType("PIL.ImageDraw")
    font_mod = types.ModuleType("PIL.ImageFont")
    class DummyImage:
        def convert(self, *_args): return self
        def resize(self, *_args): return self
        def crop(self, *_args): return self
        def save(self, *_args, **_kwargs): pass
    image_mod.Image = DummyImage
    image_mod.Resampling = types.SimpleNamespace(LANCZOS=1)
    image_mod.new = lambda *_args, **_kwargs: DummyImage()
    image_mod.open = lambda *_args, **_kwargs: DummyImage()
    image_mod.alpha_composite = lambda image, _overlay: image
    draw_mod.Draw = lambda *_args, **_kwargs: types.SimpleNamespace(line=lambda *_a, **_k: None, rounded_rectangle=lambda *_a, **_k: None, text=lambda *_a, **_k: None)
    font_mod.truetype = lambda *_args, **_kwargs: object()
    font_mod.load_default = lambda: object()
    pil_mod.Image, pil_mod.ImageDraw, pil_mod.ImageFont = image_mod, draw_mod, font_mod
    sys.modules.update({"PIL": pil_mod, "PIL.Image": image_mod, "PIL.ImageDraw": draw_mod, "PIL.ImageFont": font_mod})

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


class TestPipelineSafety(unittest.TestCase):
    def setUp(self):
        pipeline.SESSION_EXHAUSTED_MODELS.clear()
        pipeline.SESSION_UNAVAILABLE_MODELS.clear()

    def test_import_does_not_select_or_ping_models(self):
        self.assertIsNone(pipeline.SELECTED_SCREENING_MODEL)
        self.assertIsNone(pipeline.SELECTED_DEEP_DIVE_MODEL)

    def test_ssrf_rejects_private_address(self):
        with patch.object(pipeline.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 80))]):
            with self.assertRaises(ValueError):
                pipeline._validate_public_http_url("http://example.test/private")

    def test_ssrf_allows_public_address(self):
        with patch.object(pipeline.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 443))]):
            pipeline._validate_public_http_url("https://example.com/")

    def test_round_robin_prevents_source_starvation(self):
        sources = {"GitHub": [{"nameWithOwner": "g1"}, {"nameWithOwner": "g2"}], "HackerNews": [{"nameWithOwner": "h1"}, {"nameWithOwner": "h2"}], "ArXiv": [{"nameWithOwner": "a1"}], "ProductHunt": [{"nameWithOwner": "p1"}]}
        result = pipeline.round_robin_candidates(sources, 6)
        self.assertEqual(["g1", "h1", "a1", "p1", "g2", "h2"], [x["nameWithOwner"] for x in result])

    def test_batch_parser_keeps_valid_rows_and_only_recovers_missing(self):
        payload = json.dumps([{"id": "B0001", "score": 72, "reason": "有望"}, {"id": "B0003", "score": 61, "reason": "検討価値"}])
        parsed, missing = pipeline._parse_batch_screening_response(payload, {"B0001", "B0002", "B0003"})
        self.assertEqual({"B0001", "B0003"}, set(parsed))
        self.assertEqual(["B0002"], missing)

    def test_batch_parser_reports_truncation(self):
        parsed, missing, diagnostic = pipeline._parse_batch_screening_response('[{"id":"B0001"', {"B0001"}, include_diagnostic=True)
        self.assertEqual({}, parsed)
        self.assertEqual(["B0001"], missing)
        self.assertTrue(diagnostic.startswith("json_decode_error:"))

    def test_503_retries_once_then_falls_back_without_exhausting_model(self):
        calls = []
        def fake_generate(model, *_args, **_kwargs):
            calls.append(model)
            if model == "primary":
                raise FakeAPIError(503, "unavailable")
            return types.SimpleNamespace(text="[]")
        with patch.object(pipeline, "APIError", FakeAPIError), patch.object(pipeline, "_generate_via_chat", side_effect=fake_generate), patch.object(pipeline.time, "sleep"):
            _, selected = pipeline._call_model_pool("p", None, "screening_batch", 0, ["primary", "fallback"])
        self.assertEqual("fallback", selected)
        self.assertEqual(["primary", "primary", "fallback"], calls)
        self.assertIn("primary", pipeline.SESSION_UNAVAILABLE_MODELS)
        self.assertNotIn("primary", pipeline.SESSION_EXHAUSTED_MODELS)

    def test_rpd_marks_only_the_affected_model_exhausted(self):
        def fake_generate(model, *_args, **_kwargs):
            if model == "primary":
                raise FakeAPIError(429, "requestsPerDay quota exceeded")
            return types.SimpleNamespace(text="[]")
        with patch.object(pipeline, "APIError", FakeAPIError), patch.object(pipeline, "_generate_via_chat", side_effect=fake_generate):
            _, selected = pipeline._call_model_pool("p", None, "screening_batch", 0, ["primary", "fallback"])
        self.assertEqual("fallback", selected)
        self.assertIn("primary", pipeline.SESSION_EXHAUSTED_MODELS)

    def test_persistent_counter_separates_api_key_scopes(self):
        first = pipeline.PersistentGeminiDailyCounter(True, {"m": 18}, 18, ".runtime/test.json", "UTC", api_key="first")
        second = pipeline.PersistentGeminiDailyCounter(True, {"m": 18}, 18, ".runtime/test.json", "UTC", api_key="second")
        data = {"quota_date": "2026-08-17", "key_scopes": {}}
        first._model_state(data, "m")["used"] = 18
        self.assertEqual(18, first._model_state(data, "m")["used"])
        self.assertEqual(0, second._model_state(data, "m")["used"])
        self.assertNotIn("first", json.dumps(data))

    def test_model_budget_uses_configured_per_model_cap(self):
        counter = pipeline.PersistentGeminiDailyCounter(True, {"lite": 450, "deep": 18}, 18, ".runtime/test.json", "UTC", api_key="k")
        self.assertEqual(450, counter.budget_for("lite"))
        self.assertEqual(18, counter.budget_for("unknown"))

    def test_pending_retry_does_not_change_stock_status(self):
        captured = {}
        def fake_patch(_url, **kwargs):
            captured.update(kwargs["json"]["properties"])
            return FakeResponse(200)
        with patch.object(pipeline, "NOTION_API_KEY", "notion"), patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            self.assertTrue(pipeline.update_notion_pending_retry("page", "item", "503"))
        self.assertEqual(pipeline.CONTENT_STATUS_PENDING_RETRY, captured[pipeline.PROP_CONTENT_STATUS]["select"]["name"])
        self.assertNotIn(pipeline.PROP_STATUS, captured)

    def test_notion_uses_data_source_parent_when_configured(self):
        with patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "source-id"):
            self.assertEqual({"data_source_id": "source-id"}, pipeline._notion_parent())
            self.assertIn("/data_sources/source-id/query", pipeline._notion_query_url())

    def test_free_mode_is_reflected_in_deep_dive_properties(self):
        with patch.object(pipeline, "ARTICLE_PUBLICATION_MODE", "free"):
            props = pipeline.build_notion_properties("Example", "https://example.com", 82, "score", "what", "why", "why-not", "action", "N/A")
        self.assertEqual(pipeline.VISIBILITY_FREE_ARTICLE, props[pipeline.PROP_SUBSCRIPTION_VISIBILITY]["select"]["name"])

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is installed in CI through requirements.txt")
    def test_eyecatch_uses_score_color_and_skips_low_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(pipeline, "EYECATCH_BACKGROUND_DIR", directory):
                pipeline.Image.new("RGB", (1280, 670), color=(20, 30, 50)).save(Path(directory) / "default.png")
                output = Path(directory) / "score.png"
                self.assertEqual(str(output), pipeline.generate_eyecatch_image("title", str(output), "Unknown", decision_score=82, technical_impact=21, urgency=16))
                self.assertEqual((239, 68, 68), pipeline.Image.open(output).getpixel((130, 345)))
                self.assertIsNone(pipeline.generate_eyecatch_image("title", str(Path(directory) / "skip.png"), "Unknown", decision_score=59))

    def test_synthetic_adapter_rejects_false_absence_claim(self):
        truth = {"forbidden_claims": [], "required_qualifiers": [], "numerical_truth": {}, "expected_flags": []}
        findings = pipeline.validate_synthetic_invariants(truth, "hardwareは確認できない", "Hardware: RTX 4090")
        self.assertEqual("INV-004", findings[0]["code"])


if __name__ == "__main__":
    unittest.main()
