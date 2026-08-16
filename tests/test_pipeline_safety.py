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
                "lead": "読者を引き込む導入です。",
                "reader_question": "自社でも同じ課題に直面していませんか？",
                "conclusion": "現時点では研究段階です。",
                "why_now": "一次情報が公開されました。",
                "what": "これは検証用の説明です。",
                "free_summary": ["事実を確認", "限界も確認"],
                "judgement": "今は動かず追試を待ちます（WATCH）（レベル3）。",
                "editor_observation": "ここは期待できる一方、実運用の証拠はまだ限られています。",
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
        self.assertNotIn("レベル3", parsed["note_draft"])
        self.assertIn("## この記事の結論", parsed["note_draft"])
        self.assertTrue(parsed["note_draft"].startswith("読者を引き込む導入です。"))
        self.assertIn("自社でも同じ課題に直面していませんか？", parsed["note_draft"])
        self.assertIn("実運用の証拠はまだ限られています。", parsed["note_draft"])
        self.assertIn("### 結局、どうするべきか", parsed["note_draft"])
        self.assertNotIn("---有料エリア---", parsed["note_draft"])

    def test_free_mode_removes_legacy_paywall_marker_from_manuscript(self):
        draft = "## この記事の結論\n結論\n\n---有料エリア---\n\n### 私ならこう考える\n判断"
        manuscript = pipeline.build_clean_note_manuscript(
            draft, "Example", "https://example.com", "", "HackerNews"
        )
        self.assertNotIn("有料エリア", manuscript)
        self.assertIn("### 私ならこう考える", manuscript)

    def test_deep_dive_notion_properties_mark_article_as_free(self):
        properties = pipeline.build_notion_properties(
            "Example", "https://example.com", 82, "score", "what", "why", "why-not",
            "action", "N/A", report_meta={"decision_text": "WATCH"},
        )
        self.assertEqual(
            pipeline.VISIBILITY_FREE_ARTICLE,
            properties[pipeline.PROP_SUBSCRIPTION_VISIBILITY]["select"]["name"],
        )

    def test_pillow_eyecatch_uses_score_color_and_skips_low_scores(self):
        with tempfile.TemporaryDirectory() as directory:
            old_background_dir = pipeline.EYECATCH_BACKGROUND_DIR
            try:
                pipeline.EYECATCH_BACKGROUND_DIR = directory
                pipeline.Image.new("RGB", (1280, 670), color=(20, 30, 50)).save(
                    Path(directory) / "default.png"
                )
                output = Path(directory) / "score.png"
                result = pipeline.generate_eyecatch_image(
                    "title", str(output), "Unknown", decision_score=82,
                    technical_impact=21, urgency=16,
                )
                self.assertEqual(str(output), result)
                self.assertTrue(output.exists())
                image = pipeline.Image.open(output)
                self.assertEqual((1280, 670), image.size)
                self.assertEqual((239, 68, 68), image.getpixel((130, 345)))

                skipped = Path(directory) / "skipped.png"
                self.assertIsNone(pipeline.generate_eyecatch_image(
                    "title", str(skipped), "Unknown", decision_score=59,
                    technical_impact=10, urgency=10,
                ))
                self.assertFalse(skipped.exists())
            finally:
                pipeline.EYECATCH_BACKGROUND_DIR = old_background_dir

    def test_structured_prompt_does_not_expose_internal_decision_codes(self):
        prompt = pipeline.build_structured_decision_prompt(
            "name", "https://example.com", 0, "desc", source_context="source"
        )
        for code in pipeline.ALLOWED_DECISIONS:
            self.assertNotRegex(prompt, rf"\b{code}\b")

    def test_fact_gate_rejects_unparenthesized_numeric_decision_label(self):
        failures = pipeline._find_decision_code_leak("これは動向を注視すべきレベル3の情報です。")
        self.assertTrue(failures)
        self.assertIn("numeric decision label", failures[0])

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

    def test_hackernews_attribution_separates_discovery_and_primary_source(self):
        draft = "## この記事の結論\n結論\n---有料エリア---\n本文"
        manuscript = pipeline.build_clean_note_manuscript(
            draft,
            "Example article",
            "https://author.example/article",
            "",
            "HackerNews",
            source_details={
                "hn_url": "https://news.ycombinator.com/item?id=123",
                "external_url": "https://author.example/article",
            },
        )
        self.assertIn("**発見経路**: Hacker News", manuscript)
        self.assertIn("**原資料**: リンク先の原著記事・技術報告", manuscript)
        self.assertIn("**原資料URL**: [Example article](https://author.example/article)", manuscript)
        self.assertIn("発見元のHacker News投稿", manuscript)
        self.assertNotIn("**ソース**: HackerNews", manuscript)
        self.assertTrue(manuscript.endswith("導入・利用にあたっては、一次情報と自社の条件を確認してください。"))

    def test_hackernews_without_external_url_uses_hn_as_primary_source(self):
        draft = "結論\n---有料エリア---\n本文"
        manuscript = pipeline.build_clean_note_manuscript(
            draft,
            "HN post",
            "https://news.ycombinator.com/item?id=456",
            "",
            "HackerNews",
            source_details={"hn_url": "https://news.ycombinator.com/item?id=456"},
        )
        self.assertIn("**原資料**: Hacker News掲載の投稿", manuscript)
        self.assertIn("https://news.ycombinator.com/item?id=456", manuscript)

    def test_article_source_intro_makes_reference_clear_at_start(self):
        intro = pipeline._article_source_intro(
            "HackerNews",
            "Auto-research with codex",
            {"external_url": "https://author.example/article"},
        )
        self.assertTrue(intro.startswith("この記事は、Hacker Newsで発見した"))
        self.assertIn("Auto-research with codex", intro)

    def test_editorial_prompt_requires_copywriter_title(self):
        prompt = pipeline.build_structured_decision_prompt(
            "Example project", "https://example.com", 10, "説明", source_context="一次情報"
        )
        self.assertIn("人間のコピーライター", prompt)
        self.assertIn("根拠のない数字・最上級表現は避ける", prompt)
        self.assertIn("ときどき", prompt)
        self.assertIn("実際に試した・導入した・取材した等の経験は", prompt)
        self.assertIn("【事実・推論・助言の書き分け】", prompt)
        self.assertIn("筆者の推論は歓迎する", prompt)

    def test_note_title_is_always_closed_with_period_or_question_mark(self):
        self.assertTrue(pipeline._normalize_note_title("Netflixの推薦は変わる？").endswith("？"))
        self.assertTrue(pipeline._normalize_note_title("LLM推薦の現在地").endswith("。"))
        self.assertNotIn("!", pipeline._normalize_note_title("LLM推薦の現在地!"))

    def test_api_key_scopes_keep_persistent_model_counters_independent(self):
        first = pipeline.PersistentGeminiDailyCounter(
            True, {"model": 18}, 18, ".runtime/test.json", "UTC", api_key="first-key"
        )
        second = pipeline.PersistentGeminiDailyCounter(
            True, {"model": 18}, 18, ".runtime/test.json", "UTC", api_key="second-key"
        )
        data = {"quota_date": "2026-08-16", "key_scopes": {}}
        first_state = first._model_state(data, "model")
        first_state["used"] = 18
        self.assertEqual(18, first._model_state(data, "model")["used"])
        self.assertEqual(0, second._model_state(data, "model")["used"])
        self.assertNotEqual(first.key_scope, second.key_scope)
        self.assertNotIn("first-key", json.dumps(data))

    def test_model_budget_never_exceeds_verified_rpd_limit(self):
        counter = pipeline.PersistentGeminiDailyCounter(
            True, {"gemini-3.7-flash": 99}, 99, ".runtime/test.json", "UTC", api_key="key"
        )
        self.assertEqual(20, counter.budget_for("gemini-3.7-flash"))
        self.assertEqual(99, counter.budget_for("unregistered-model"))

    def test_legacy_counter_does_not_carry_usage_to_current_key(self):
        counter = pipeline.PersistentGeminiDailyCounter(
            True, {"model": 18}, 18, ".runtime/test.json", "UTC", api_key="new-key"
        )
        legacy = {"quota_date": "2026-08-16", "models": {"model": {"used": 18, "exhausted": True}}}
        normalized = counter._normalized_day(legacy, "2026-08-16")
        self.assertNotIn("models", normalized)
        self.assertEqual(0, counter._model_state(normalized, "model")["used"])

    def test_hn_context_without_external_article_is_not_sufficient(self):
        repo = {
            "source": "HackerNews", "nameWithOwner": "HN item", "description": "desc",
            "sourceContext": "HNのコメント本文 " * 100,
            "sourceDetails": {"external_url": "https://example.com/article"},
        }
        with patch.object(pipeline, "fetch_webpage_context", return_value=""):
            context = pipeline.prepare_source_context(repo)
        self.assertIn("Hacker News post text", context["context"])
        self.assertFalse(context["sufficient"])

    def test_fact_helpers_reject_internal_reference_and_unverified_hn_testimony(self):
        self.assertTrue(pipeline._find_undefined_reference_markers("効率化が進んでいる [1.1]。"))
        self.assertTrue(pipeline._find_heading_spacing_issues("### 見出し\n本文"))
        self.assertTrue(pipeline._find_unverified_hn_testimonial_claims(
            "企業の現場で働く構造生物学者の証言では効率化した。", "HackerNews"
        ))

    def test_round_robin_prevents_source_order_starvation(self):
        sources = {
            "GitHub": [{"nameWithOwner": "g1"}, {"nameWithOwner": "g2"}],
            "HackerNews": [{"nameWithOwner": "h1"}, {"nameWithOwner": "h2"}],
            "ArXiv": [{"nameWithOwner": "a1"}],
            "ProductHunt": [{"nameWithOwner": "p1"}],
        }
        result = pipeline.round_robin_candidates(sources, 6)
        self.assertEqual(["g1", "h1", "a1", "p1", "g2", "h2"], [x["nameWithOwner"] for x in result])

    def test_batch_parser_preserves_valid_items_and_recovers_only_missing(self):
        payload = json.dumps([
            {"id": "B0001", "score": 72, "reason": "有望"},
            {"id": "B0003", "score": 61, "reason": "検討価値"},
        ])
        parsed, missing = pipeline._parse_batch_screening_response(payload, {"B0001", "B0002", "B0003"})
        self.assertEqual({"B0001", "B0003"}, set(parsed))
        self.assertEqual(["B0002"], missing)

    def test_batch_parser_returns_truncation_diagnostic_for_invalid_json(self):
        parsed, missing, diagnostic = pipeline._parse_batch_screening_response(
            '[{"id":"B0001","score":72,"reason":"途中',
            {"B0001"},
            include_diagnostic=True,
        )
        self.assertEqual({}, parsed)
        self.assertEqual(["B0001"], missing)
        self.assertTrue(diagnostic.startswith("json_decode_error:"))

    def test_screening_and_calibration_use_separate_output_token_caps(self):
        seen = []

        def fake_pool(prompt, config, kind, reserve):
            seen.append((kind, config, reserve))
            return types.SimpleNamespace(text="[]"), "test-model"

        with patch.object(pipeline, "_call_screening_pool", side_effect=fake_pool):
            pipeline.call_screening_provider("screen", "screening_batch")
            pipeline.call_screening_provider("calibrate", "global_calibration")

        self.assertEqual(pipeline.SCREENING_BATCH_MAX_OUTPUT_TOKENS, seen[0][1]["max_output_tokens"])
        self.assertEqual(pipeline.GLOBAL_CALIBRATION_MAX_OUTPUT_TOKENS, seen[1][1]["max_output_tokens"])
        self.assertEqual("application/json", seen[0][1]["response_mime_type"])

    def test_screening_recovery_consumes_screening_retry_budget(self):
        budget = pipeline.GeminiBudget(daily_budget=10, screening_retry_budget=1, deep_dive_retry_budget=1)
        budget.consume("screening_recovery")
        self.assertEqual(1, budget.screening_retry_count)
        self.assertFalse(budget.can_screening_retry())

    def test_recovery_splits_missing_batch_into_small_chunks(self):
        candidates = [
            {"screening_id": f"B{i:04d}", "repo": {"nameWithOwner": f"n{i}", "stargazerCount": 0}}
            for i in range(1, 26)
        ]
        seen_sizes = []

        def fake_screen(batch, *_args, recovery=False, **_kwargs):
            seen_sizes.append(len(batch))
            if not recovery:
                return [], batch, 1
            completed = [
                {"repo": item["repo"], "screening_id": item["screening_id"], "raw_score": 50,
                 "final_score": 50, "reason": "test", "calibrated": False,
                 "screening_status": "completed"}
                for item in batch
            ]
            return completed, [], 1

        with patch.object(pipeline, "SCREENING_BATCH_SIZE", 25), \
             patch.object(pipeline, "SCREENING_RECOVERY_BATCH_SIZE", 10), \
             patch.object(pipeline, "screen_batch", side_effect=fake_screen), \
             patch.object(pipeline.GEMINI_BUDGET, "can_request", return_value=True), \
             patch.object(pipeline.GEMINI_BUDGET, "can_screening_retry", return_value=True):
            result, calls = pipeline.screen_candidates_in_batches(candidates)

        self.assertEqual([25, 10, 10, 5], seen_sizes)
        self.assertEqual(4, calls)
        self.assertEqual(25, len(result))

    def test_200_candidates_are_partitioned_into_eight_screening_batches(self):
        candidates = [
            {"screening_id": f"B{i:04d}", "repo": {"nameWithOwner": f"n{i}", "stargazerCount": 0}}
            for i in range(1, 201)
        ]
        seen_sizes = []

        def fake_screen(batch, *_args, **_kwargs):
            seen_sizes.append(len(batch))
            completed = [
                {"repo": item["repo"], "screening_id": item["screening_id"], "raw_score": 50,
                 "final_score": 50, "reason": "test", "calibrated": False,
                 "screening_status": "completed"}
                for item in batch
            ]
            return completed, [], 1

        with patch.object(pipeline, "SCREENING_BATCH_SIZE", 25), \
             patch.object(pipeline, "screen_batch", side_effect=fake_screen), \
             patch.object(pipeline.GEMINI_BUDGET, "can_request", return_value=True):
            result, calls = pipeline.screen_candidates_in_batches(candidates)
        self.assertEqual([25] * 8, seen_sizes)
        self.assertEqual(8, calls)
        self.assertEqual(200, len(result))

    def test_observed_history_records_failed_candidate_without_notion(self):
        item = {
            "screening_id": "B0001",
            "repo": {"source": "GitHub", "nameWithOwner": "n", "url": "https://example.com", "publishedAt": None, "stargazerCount": 1},
            "raw_score": None, "final_score": None, "reason": "Screening APIで判定できなかった",
            "calibrated": False, "screening_status": "failed", "error_category": "quota_or_transport",
        }
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(pipeline, "OBSERVED_HISTORY_DIR", tmp), \
             patch.object(pipeline, "upload_observed_history_to_github", return_value=None):
            path = pipeline.save_observed_history([item], 1, 1)
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual("failed", payload["items"][0]["screening_status"])
        self.assertFalse(payload["items"][0]["stocked"])


if __name__ == "__main__":
    unittest.main()
