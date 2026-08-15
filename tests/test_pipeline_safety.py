import importlib.util
import json
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

    def test_model_unavailable_is_marked_pending_retry_not_quality_failed(self):
        repo = {
            "nameWithOwner": "example", "description": "desc", "url": "https://example.com",
            "stargazerCount": 1, "source": "HackerNews", "publishedAt": None,
        }
        source_info = {
            "sufficient": True, "primary_url": "https://example.com", "context": "source",
            "method": pipeline.GROUNDING_SOURCE_NATIVE,
        }
        with patch.multiple(
            pipeline,
            prepare_source_context=lambda repo: source_info,
            call_gemini_grounded_deep_dive=lambda *a, **k: (_ for _ in ()).throw(
                pipeline.NoAvailableModelError("503 unavailable")
            ),
            update_notion_pending_retry=lambda *a, **k: True,
            update_notion_quality_failed=lambda *a, **k: self.fail("API outage must not be Quality Failed"),
        ):
            result = pipeline.generate_intelligence_report(
                repo, notion_page_id="page-id", screening_score=80, screening_reason="reason",
            )
        self.assertIsNone(result)

    def test_pending_retry_items_are_reconstructed_from_notion(self):
        page = {
            "id": "page-id",
            "properties": {
                "Name": {"title": [{"plain_text": "item"}]},
                "URL": {"url": "https://example.com"},
                "Source": {"select": {"name": "HackerNews"}},
                "Screening Score": {"number": 70},
                "Screening Reason": {"rich_text": [{"plain_text": "reason"}]},
                "Engagement Score": {"number": 12},
                "Published At": {"date": {"start": "2026-08-15"}},
            },
        }
        with patch.object(pipeline, "NOTION_API_KEY", "notion"), \
             patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "source"), \
             patch.object(pipeline, "_query_notion_db_with_retry", return_value=FakeResponse(payload={"results": [page]})):
            items = pipeline.get_pending_retry_items()
        self.assertEqual(1, len(items))
        self.assertEqual("page-id", items[0]["notion_page_id"])
        self.assertEqual("item", items[0]["repo"]["nameWithOwner"])

    def test_pending_retry_status_is_used_for_transient_failures(self):
        captured = {}

        def fake_patch(url, **kwargs):
            captured.update(kwargs["json"]["properties"])
            return FakeResponse(200)

        with patch.object(pipeline, "NOTION_API_KEY", "notion"), \
             patch.object(pipeline.requests, "patch", side_effect=fake_patch):
            ok = pipeline.update_notion_pending_retry("page-id", "item")
        self.assertTrue(ok)
        self.assertEqual(
            pipeline.CONTENT_STATUS_PENDING_RETRY,
            captured[pipeline.PROP_CONTENT_STATUS]["select"]["name"],
        )

    def test_fact_gate_rejects_fabricated_cli(self):
        failures = pipeline._find_unsupported_syntax_claims(
            "```bash\npip install fabricated-package\n```", "official text without commands"
        )
        self.assertTrue(failures)

    def test_hype_gate_rejects_transformative_and_superlative_claims(self):
        samples = (
            "統計学習理論の教科書を書き換えるレベルの成果です。",
            "これは歴史的な成果です。",
            "理論的ブレイクスルーです。",
            "研究の価値は極めて高いです。",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(pipeline._find_hype_claims(sample))

    def test_hype_gate_allows_explicit_negation(self):
        samples = (
            "これは教科書を書き換えるものではない。",
            "現段階でブレイクスルーとは言えない。",
        )
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual([], pipeline._find_hype_claims(sample))

    def test_hype_gate_does_not_treat_compute_load_as_value_hype(self):
        self.assertEqual([], pipeline._find_hype_claims("この処理は極めて計算負荷の高い方法です。"))

    def test_structured_parser_builds_fixed_markdown_and_maps_decision(self):
        payload = {
            "management": {
                "source_summary": "一次情報の要約",
                "what": "何が起きたか",
                "why_important": "意味",
                "paradigm_shift": "変化は限定的",
                "alternative_comparison": "比較根拠不足",
                "migration_cost": "未確認",
                "decision_level": 3,
                "decision_reason": "追試待ち",
                "scores": {"business": 10, "technical": 20, "urgency": 5, "market": 5, "reliability": 10},
                "why_not_important": "直接適用しない読者",
                "who_should_use": "研究担当",
                "who_should_not_use": "一般運用担当",
                "action": "継続観測",
                "future_scenarios": ["追試が出たら再評価"],
                "article_value": 70,
            },
            "article": {
                "title": "検証用タイトル",
                "conclusion": "現時点では研究段階です。",
                "why_now": "一次情報が公開されました。",
                "what": "これは検証用の説明です。",
                "free_summary": ["事実を確認", "限界も確認"],
                "judgement": "今は動かず追試を待ちます（WATCH）。",
                "paid_sections": [
                    {"heading": "根拠", "body": "根拠の範囲を説明します。"},
                    {"heading": "限界", "body": "現時点の限界を説明します。"},
                    {"heading": "観測点", "body": "今後の観測点を説明します。"},
                ],
                "final_recommendation": "四半期ごとに確認します。",
            },
        }
        parsed = pipeline._parse_gemini_response(json.dumps(payload, ensure_ascii=False))

        self.assertEqual("WATCH", parsed["decision_text"])
        self.assertEqual(50, parsed["score"])
        self.assertNotIn("WATCH", parsed["note_draft"])
        self.assertIn("## この記事の結論", parsed["note_draft"])
        self.assertIn("### 結局、どうするべきか", parsed["note_draft"])
        self.assertIn("---有料エリア---", parsed["note_draft"])

    def test_structured_prompt_does_not_expose_internal_decision_codes(self):
        prompt = pipeline.build_structured_decision_prompt(
            "name", "https://example.com", 0, "desc", source_context="source"
        )
        for code in pipeline.ALLOWED_DECISIONS:
            self.assertNotRegex(prompt, rf"\b{code}\b")

    def test_structured_parser_fails_closed_without_decision_level(self):
        payload = {"management": {"scores": {
            "business": 1, "technical": 1, "urgency": 1, "market": 1, "reliability": 1,
        }}, "article": {}}
        with self.assertRaisesRegex(ValueError, "decision_level"):
            pipeline._parse_structured_gemini_response(json.dumps(payload))

    def test_finish_reason_detects_max_tokens(self):
        reason = types.SimpleNamespace(name="MAX_TOKENS")
        response = types.SimpleNamespace(candidates=[types.SimpleNamespace(finish_reason=reason)])
        self.assertEqual("MAX_TOKENS", pipeline._response_finish_reason(response))

    def test_deep_dive_call_uses_structured_output_config(self):
        captured = {}
        response = types.SimpleNamespace(text="{}", candidates=[])

        def fake_pool(prompt, config=None, kind="deep_dive"):
            captured.update(config or {})
            return response, "model"

        source_info = {
            "sufficient": True,
            "primary_url": "https://example.com",
            "context": "source",
            "method": pipeline.GROUNDING_SOURCE_NATIVE,
        }
        repo = {"url": "https://example.com"}
        with patch.object(pipeline, "_call_deep_dive_pool", side_effect=fake_pool), \
             patch.object(pipeline, "_extract_usage_metadata"), \
             patch.object(pipeline, "extract_grounding_metadata", return_value={
                 "grounding_status": pipeline.GROUNDING_SOURCE_NATIVE,
                 "evidence_urls": ["https://example.com"],
             }):
            pipeline.call_gemini_grounded_deep_dive("prompt", repo, source_info)

        self.assertEqual("application/json", captured["response_mime_type"])
        self.assertIs(pipeline.DEEP_DIVE_RESPONSE_SCHEMA, captured["response_schema"])
        self.assertEqual(pipeline.GEMINI_DEEP_DIVE_THINKING_LEVEL, captured["thinking_config"]["thinking_level"])
        self.assertEqual(pipeline.GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS, captured["max_output_tokens"])

    def test_structured_schema_excludes_generate_content_incompatible_keywords(self):
        def walk(value):
            if isinstance(value, dict):
                self.assertNotIn("additionalProperties", value)
                self.assertNotIn("additional_properties", value)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(pipeline.DEEP_DIVE_RESPONSE_SCHEMA)


if __name__ == "__main__":
    unittest.main()
