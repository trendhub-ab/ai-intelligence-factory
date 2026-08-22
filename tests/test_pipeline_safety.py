import importlib.util
import inspect
import json
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

    def test_batch_parser_rejects_duplicate_and_out_of_range_rows(self):
        payload = json.dumps([
            {"id": "B0001", "score": 72, "reason": "有望"},
            {"id": "B0001", "score": 73, "reason": "重複"},
            {"id": "B0002", "score": 101, "reason": "範囲外"},
        ])
        parsed, missing, diagnostic = pipeline._parse_batch_screening_response(
            payload, {"B0001", "B0002"}, include_diagnostic=True,
        )
        self.assertEqual({"B0001"}, set(parsed))
        self.assertEqual(["B0002"], missing)
        self.assertIn("duplicate_id:B0001", diagnostic)
        self.assertIn("score_out_of_range:B0002", diagnostic)

    def test_200_candidates_use_eight_batch_calls_and_batch_pacing(self):
        candidates = [
            {"screening_id": f"B{i:04d}", "repo": {"source": "GitHub", "nameWithOwner": str(i)}}
            for i in range(1, 201)
        ]
        def fake_batch(batch, **_kwargs):
            return ([{"repo": row["repo"], "screening_id": row["screening_id"], "raw_score": 50,
                      "final_score": 50, "score": 50, "reason": "ok", "calibrated": False,
                      "screening_status": "completed"} for row in batch], [], 1)
        with patch.object(pipeline, "SCREENING_BATCH_SIZE", 25), \
             patch.object(pipeline, "SCREENING_BATCH_PACING_SECONDS", 1), \
             patch.object(pipeline, "screen_batch", side_effect=fake_batch), \
             patch.object(pipeline.time, "sleep") as sleep:
            rows, calls = pipeline.screen_candidates_in_batches(candidates)
        self.assertEqual(200, len(rows))
        self.assertEqual(8, calls)
        self.assertEqual(7, sleep.call_count)

    def test_calibration_only_updates_raw_score_survivors(self):
        items = [
            {"screening_id": "B0001", "repo": {"source": "GitHub", "nameWithOwner": "one"}, "raw_score": 60,
             "final_score": 60, "score": 60, "reason": "raw", "calibrated": False, "screening_status": "completed"},
            {"screening_id": "B0002", "repo": {"source": "ArXiv", "nameWithOwner": "two"}, "raw_score": 50,
             "final_score": 50, "score": 50, "reason": "raw", "calibrated": False, "screening_status": "completed"},
        ]
        with patch.object(pipeline, "call_screening_provider", return_value=types.SimpleNamespace(
                text='[{"id":"B0001","score":67,"reason":"補正"}]')):
            result, calls = pipeline.calibrate_candidates(items)
        self.assertEqual(1, calls)
        self.assertEqual(67, result[0]["final_score"])
        self.assertTrue(result[0]["calibrated"])
        self.assertEqual(50, result[1]["final_score"])

    def test_observed_history_contains_final_scores_and_is_upload_fail_safe(self):
        item = {"screening_id": "B0001", "repo": {"source": "GitHub", "nameWithOwner": "one", "url": "https://x", "publishedAt": "today", "stargazerCount": 1},
                "raw_score": 61, "final_score": 66, "score": 66, "reason": "ok", "calibrated": True, "screening_status": "completed"}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(pipeline, "OBSERVED_HISTORY_DIR", directory), \
             patch.object(pipeline, "upload_observed_history_to_github", return_value=None):
            path = pipeline.save_observed_history([item], 1, 0, calibration_calls=1, total_collected=1)
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(66, payload["items"][0]["final_screening_score"])
        self.assertTrue(payload["items"][0]["calibrated"])

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

    def test_deep_dive_run_budget_stops_before_pacing_or_provider_call(self):
        budget = pipeline.DeepDiveModelBudget(0)
        with patch.object(pipeline, "DEEP_DIVE_MODEL_BUDGET", budget), \
             patch.object(pipeline.time, "sleep") as sleep, \
             patch.object(pipeline, "_generate_via_chat") as generate:
            with self.assertRaises(pipeline.DeepDiveRunBudgetExceededError):
                pipeline._call_model_pool(
                    "p", None, "deep_dive", 0, ["primary", "fallback"], deep_dive=True
                )
        sleep.assert_not_called()
        generate.assert_not_called()

    def test_session_exhausted_deep_dive_pool_is_detected_before_next_candidate(self):
        with patch.object(pipeline, "DEEP_DIVE_MODEL_POOL", ["m1", "m2"]):
            pipeline.SESSION_UNAVAILABLE_MODELS.update({"m1", "m2"})
            self.assertFalse(pipeline._model_pool_has_session_candidate(pipeline.DEEP_DIVE_MODEL_POOL))
            pipeline.SESSION_UNAVAILABLE_MODELS.remove("m2")
            self.assertTrue(pipeline._model_pool_has_session_candidate(pipeline.DEEP_DIVE_MODEL_POOL))

    def test_deep_dive_run_budget_is_not_misclassified_as_no_available_model(self):
        budget = pipeline.DeepDiveModelBudget(0)
        with patch.object(pipeline, "DEEP_DIVE_MODEL_BUDGET", budget), \
             patch.object(pipeline.time, "sleep"):
            try:
                pipeline._call_model_pool(
                    "p", None, "quality_retry", 0, ["primary", "fallback"], deep_dive=True
                )
            except Exception as exc:
                self.assertIsInstance(exc, pipeline.DeepDiveRunBudgetExceededError)
                self.assertNotIsInstance(exc, pipeline.NoAvailableModelError)
                self.assertIn("run budget exhausted", str(exc))
            else:
                self.fail("Deep Dive run budget exhaustion must raise")

    def test_rpd_marks_only_the_affected_model_exhausted(self):
        def fake_generate(model, *_args, **_kwargs):
            if model == "primary":
                raise FakeAPIError(429, "requestsPerDay quota exceeded")
            return types.SimpleNamespace(text="[]")
        with patch.object(pipeline, "APIError", FakeAPIError), patch.object(pipeline, "_generate_via_chat", side_effect=fake_generate):
            _, selected = pipeline._call_model_pool("p", None, "screening_batch", 0, ["primary", "fallback"])
        self.assertEqual("fallback", selected)
        self.assertIn("primary", pipeline.SESSION_EXHAUSTED_MODELS)

    def test_persistent_counter_shares_scope_across_api_keys_in_same_repository_scope(self):
        first = pipeline.PersistentGeminiDailyCounter(
            True, {"m": 18}, 18, ".runtime/test.json", "UTC",
            quota_project_id="project-a", api_key="first", quota_scope_id="owner/repo"
        )
        second = pipeline.PersistentGeminiDailyCounter(
            True, {"m": 18}, 18, ".runtime/test.json", "UTC",
            quota_project_id="project-a", api_key="second", quota_scope_id="owner/repo"
        )
        data = {"quota_date": "2026-08-17", "counter_scopes": {}}
        first._model_state(data, "m")["used"] = 18
        self.assertEqual(first.counter_scope, second.counter_scope)
        self.assertEqual(18, second._model_state(data, "m")["used"])
        serialized = json.dumps(data)
        self.assertNotIn("project-a", serialized)
        self.assertNotIn("owner/repo", serialized)
        self.assertNotIn("first", serialized)
        self.assertNotIn("second", serialized)

    def test_provider_project_change_does_not_reset_repository_local_counter(self):
        first = pipeline.PersistentGeminiDailyCounter(
            True, {"m": 18}, 18, ".runtime/test.json", "UTC",
            quota_project_id="project-a", quota_scope_id="owner/repo"
        )
        second = pipeline.PersistentGeminiDailyCounter(
            True, {"m": 18}, 18, ".runtime/test.json", "UTC",
            quota_project_id="project-b", quota_scope_id="owner/repo"
        )
        data = {"quota_date": "2026-08-17", "counter_scopes": {}}
        first._model_state(data, "m")["used"] = 18
        self.assertEqual(first.counter_scope, second.counter_scope)
        self.assertEqual(18, second._model_state(data, "m")["used"])

    def test_different_repository_scopes_are_separated(self):
        first = pipeline.PersistentGeminiDailyCounter(
            True, {"m": 18}, 18, ".runtime/test.json", "UTC", quota_scope_id="owner/repo-a"
        )
        second = pipeline.PersistentGeminiDailyCounter(
            True, {"m": 18}, 18, ".runtime/test.json", "UTC", quota_scope_id="owner/repo-b"
        )
        data = {"quota_date": "2026-08-17", "counter_scopes": {}}
        first._model_state(data, "m")["used"] = 18
        self.assertEqual(18, first._model_state(data, "m")["used"])
        self.assertEqual(0, second._model_state(data, "m")["used"])

    def test_legacy_api_key_and_project_scopes_are_conservatively_migrated(self):
        counter = pipeline.PersistentGeminiDailyCounter(
            True, {"m": 18}, 18, ".runtime/test.json", "UTC", quota_scope_id="owner/repo"
        )
        data = {
            "quota_date": "2026-08-17",
            "key_scopes": {
                "old-a": {"models": {"m": {"used": 5, "by_kind": {"deep_dive": 5}, "exhausted": False}}},
            },
            "project_scopes": {
                "old-project": {"models": {"m": {"used": 3, "by_kind": {"quality_retry": 3}, "exhausted": False}}},
            },
        }
        migrated = counter._normalized_day(data, "2026-08-17")
        state = counter._model_state(migrated, "m")
        self.assertEqual(8, state["used"])
        self.assertEqual(5, state["by_kind"]["deep_dive"])
        self.assertEqual(3, state["by_kind"]["quality_retry"])
        self.assertNotIn("key_scopes", migrated)
        self.assertNotIn("project_scopes", migrated)
        self.assertTrue(migrated["legacy_key_scopes_migrated"])
        self.assertTrue(migrated["legacy_project_scopes_migrated"])

    def test_model_budget_uses_configured_per_model_cap(self):
        counter = pipeline.PersistentGeminiDailyCounter(
            True, {"lite": 450, "deep": 18}, 18, ".runtime/test.json", "UTC", quota_project_id="project-a"
        )
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

    def test_free_note_mode_does_not_make_internal_notion_asset_free(self):
        with patch.object(pipeline, "ARTICLE_PUBLICATION_MODE", "free"):
            props = pipeline.build_notion_properties("Example", "https://example.com", 82, "score", "what", "why", "why-not", "action", "N/A")
        self.assertEqual(
            pipeline.VISIBILITY_SUBSCRIBER_ONLY,
            props[pipeline.PROP_SUBSCRIPTION_VISIBILITY]["select"]["name"],
        )

    def test_free_manuscript_removes_paywall_label_and_draft_delimiter(self):
        draft = "## この記事の結論\n無料部分\n---有料エリア---\n有料部分\n===NOTE_DRAFT_END==="
        with patch.object(pipeline, "ARTICLE_PUBLICATION_MODE", "free"):
            manuscript = pipeline.build_clean_note_manuscript(draft, "Example", "https://example.com", "N/A", "HackerNews", title_text="読者を惹くタイトル", discovery_url="https://news.ycombinator.com/item?id=1")
        self.assertIn("有料部分", manuscript)
        self.assertTrue(manuscript.startswith("# 読者を惹くタイトル。"))
        self.assertNotIn("ここから先は有料エリア", manuscript)
        self.assertNotIn("---有料エリア---", manuscript)
        self.assertNotIn("NOTE_DRAFT_END", manuscript)
        self.assertIn("**発見経路**: HackerNews", manuscript)
        self.assertIn("**原資料URL**: [Example](https://example.com)", manuscript)
        self.assertIn("**関連情報**: 発見元の[HackerNews投稿]", manuscript)
        self.assertIn("特定の効果・成果を保証するものではありません", manuscript)

    def test_article_display_variants_are_stable_per_article_and_not_fixed(self):
        first = pipeline._article_display_variant("article-a")
        self.assertEqual(first, pipeline._article_display_variant("article-a"))
        variants = {tuple(sorted(pipeline._article_display_variant(f"article-{i}").items())) for i in range(20)}
        self.assertGreater(len(variants), 1)
        self.assertNotEqual("Why", first["why"])
        self.assertNotEqual("What", first["what"])

    def test_humanization_gate_flags_fictitious_experience_and_missing_reservation(self):
        draft = "## 導入\n私は驚きました。使ってみて驚いた。\n\n## 本文\nこれは重要です。"
        warnings = pipeline._find_humanization_violations(draft)
        self.assertIn("unsupported personal experience", warnings)
        self.assertIn("missing observation or reservation", warnings)

    def test_humanization_gate_accepts_observation_without_fictitious_experience(self):
        draft = "## 導入\n一見すると魅力的です。ただ、原資料の条件は確認が必要です。\n\n## 本文\n実務では慎重に見ます。"
        self.assertNotIn("unsupported personal experience", pipeline._find_humanization_violations(draft))
        self.assertNotIn("missing observation or reservation", pipeline._find_humanization_violations(draft))

    def test_publication_readiness_blocks_research_to_production_leap(self):
        parsed = {"title_text": "検証結果。", "note_draft": "## 本文\n研究段階です。", "action_text": "私なら本番環境へ全面導入する。", "score": 62}
        state, issues = pipeline.validate_publication_readiness_gate(
            parsed, "This is an experimental research prototype and has not been validated in production.", {"sufficient": True},
        )
        self.assertEqual("REVIEW", state)
        self.assertIn("research_to_production_leap", issues)

    def test_publication_readiness_flags_marketing_headline_with_weak_evidence(self):
        parsed = {"title_text": "革命的なAIエージェント。", "note_draft": "## 本文\n概要です。", "action_text": "小さく検証する。", "score": 65}
        state, issues = pipeline.validate_publication_readiness_gate(
            parsed, "Product page describes an experimental prototype.", {"sufficient": True},
        )
        self.assertEqual("REVIEW", state)
        self.assertIn("headline_overclaim", issues)

    def test_human_appeal_detects_action_collapsed_to_generic_monitoring(self):
        parsed = {
            "title_text": "検証すべき論点。",
            "note_draft": "## はじめに\n現場の課題と原資料を整理する。\n\n### 私なら今はこうする。\n今後注視したい。",
            "action_text": "今後の動向を注視する。",
        }
        level, issues = pipeline.validate_human_appeal_gate(parsed)
        self.assertEqual("WEAK", level)
        self.assertIn("action_collapsed_to_generic_monitoring", issues)

    def test_human_appeal_preserves_grounded_limited_trial(self):
        parsed = {
            "title_text": "研究成果を、どこまで試すべきか？",
            "note_draft": "## 気になった背景\n現場で起きる課題から、原資料の範囲を確認する。\n\n### 実務で使うなら、私はこうする。\n現時点では本番導入を急がず、検証環境で既存方式との比較テストを行う。",
            "action_text": "検証環境で比較テストを実施する。",
        }
        level, issues = pipeline.validate_human_appeal_gate(parsed)
        self.assertEqual("ACCEPTABLE", level)
        self.assertNotIn("action_collapsed_to_generic_monitoring", issues)

    def test_human_appeal_detects_title_flattening_and_reedit_degradation(self):
        before = {
            "title_text": "研究成果を、どこまで試すべきか？",
            "note_draft": "### 私なら今はこうする。\n検証環境で小さく比較テストを試す。",
            "action_text": "検証環境で比較テストを試す。",
        }
        after = {
            "title_text": "この技術について。",
            "note_draft": "### 私なら今はこうする。\n今後の動向を注視したい。",
            "action_text": "今後の動向を注視する。",
        }
        _, issues = pipeline.validate_human_appeal_gate(after)
        self.assertIn("headline_flattened", issues)
        self.assertTrue(pipeline.human_appeal_materially_degraded(before, after))

    def test_formal_quality_gate_names_and_backward_compatibility_aliases(self):
        self.assertTrue(callable(pipeline.validate_publication_readiness_gate))
        self.assertTrue(callable(pipeline.validate_human_appeal_gate))
        self.assertIs(pipeline.validate_publication_readiness, pipeline.validate_publication_readiness_gate)
        self.assertIs(pipeline.validate_human_appeal, pipeline.validate_human_appeal_gate)

    def test_deep_dive_uses_formal_quality_gate_names(self):
        source = inspect.getsource(pipeline.generate_intelligence_report)
        self.assertIn("validate_fact_gate(", source)
        self.assertIn("validate_editorial_gate(", source)
        self.assertIn("validate_publication_readiness_gate(", source)
        self.assertIn("validate_human_appeal_gate(", source)

    def test_display_variants_use_flexible_intro_paragraph_guidance(self):
        paragraph_counts = {variant["intro_paragraphs"] for variant in pipeline.ARTICLE_DISPLAY_VARIANTS}
        self.assertEqual({2, 3, 4}, paragraph_counts)

    def test_source_boundary_accepts_pdf_ligature_and_spacing_variant(self):
        draft = "Diff VGとの比較実験では実行時間を評価した。"
        evidence = "The implementation compares DiﬀVG with our renderer."
        self.assertEqual([], pipeline._find_source_boundary_violations(draft, evidence))

    def test_fact_gate_rejects_internal_draft_delimiter(self):
        findings = pipeline._find_final_wording_violations("本文\n===NOTE_DRAFT_END===", {}, None)
        self.assertIn("INTERNAL_DRAFT_DELIMITER_LEAKED", findings)

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is installed in CI through requirements.txt")
    def test_eyecatch_uses_ready_status_not_decision_score(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(pipeline, "EYECATCH_BACKGROUND_DIR", directory):
                pipeline.Image.new("RGB", (1280, 670), color=(20, 30, 50)).save(Path(directory) / "default.png")
                output = Path(directory) / "score.png"
                self.assertEqual(str(output), pipeline.generate_eyecatch_image("title", str(output), "Unknown", decision_score=82, technical_impact=21, urgency=16))
                self.assertEqual((139, 92, 246), pipeline.Image.open(output).getpixel((130, 345)))
                low = Path(directory) / "low.png"
                self.assertEqual(str(low), pipeline.generate_eyecatch_image("title", str(low), "Unknown", decision_score=59, article_ready=True))
                self.assertIsNone(pipeline.generate_eyecatch_image("title", str(Path(directory) / "skip.png"), "Unknown", decision_score=90, article_ready=False))


    def test_eyecatch_score_band_colors_and_boundaries(self):
        cases = {
            0: (100, 116, 139), 59: (100, 116, 139),
            60: (34, 211, 238), 69: (34, 211, 238),
            70: (59, 130, 246), 79: (59, 130, 246),
            80: (139, 92, 246), 89: (139, 92, 246),
            90: (245, 185, 66), 100: (245, 185, 66),
        }
        for score, expected in cases.items():
            with self.subTest(score=score):
                self.assertEqual(expected, pipeline._eyecatch_score_color(score))

    def test_eyecatch_extracts_approved_score_components(self):
        breakdown = "Business Impact 19/25; Technical Impact 21/25; Urgency 12/20; Market Impact 14/15; Reliability 15/15; 合計 81/100"
        self.assertEqual((21, 12), pipeline._extract_eyecatch_score_components(breakdown))

    def test_eyecatch_score_components_fail_closed(self):
        self.assertEqual((None, None), pipeline._extract_eyecatch_score_components("Business Impact 20/25; 合計 80/100"))
        self.assertEqual((None, 12), pipeline._extract_eyecatch_score_components("Technical Impact 28/25; Urgency 12/20"))

    def test_synthetic_adapter_rejects_false_absence_claim(self):
        truth = {"forbidden_claims": [], "required_qualifiers": [], "numerical_truth": {}, "expected_flags": []}
        findings = pipeline.validate_synthetic_invariants(truth, "hardwareは確認できない", "Hardware: RTX 4090")
        self.assertEqual("INV-004", findings[0]["code"])

    def test_gate_funnel_counts_and_ready_zero_summary(self):
        funnel = pipeline.DeepDiveGateFunnel()
        review = pipeline.build_candidate_gate_record(
            1, "example", "https://example.com", 82, "completed",
            pipeline.GATE_STATUS_PASS, pipeline.GATE_STATUS_PASS,
            pipeline.GATE_STATUS_REVIEW, pipeline.GATE_STATUS_NOT_RUN,
            [{"reason_code": pipeline.REASON_CODE_PUB_ACTION_EVIDENCE_MISMATCH, "message": "action too strong"}],
            pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW, True,
        )
        funnel.record(review)
        self.assertEqual(1, funnel.counters["deep_dive_candidates_attempted"])
        self.assertEqual(1, funnel.counters["publication_readiness_review"])
        self.assertEqual(0, funnel.counters["ready_count"])
        self.assertIn("READY ARTICLES: 0", funnel.render_ready_zero_summary())
        self.assertIn("Publication Readiness Review", funnel.render_text())

    def test_reason_codes_preserve_publication_and_human_appeal_causes(self):
        publication = pipeline.map_gate_reasons("publication", ["headline_overclaim", "research_to_production_leap"])
        appeal = pipeline.map_gate_reasons("human_appeal", ["action_collapsed_to_generic_monitoring"])
        self.assertEqual(pipeline.REASON_CODE_PUB_HEADLINE_OVERCLAIM, publication[0]["reason_code"])
        self.assertEqual(pipeline.REASON_CODE_PUB_UNSUPPORTED_CONCLUSION, publication[1]["reason_code"])
        self.assertEqual(pipeline.REASON_CODE_APPEAL_ACTION_COLLAPSE, appeal[0]["reason_code"])

    def test_review_and_quality_failure_are_saved_only_to_private_directories(self):
        repo = {"nameWithOwner": "owner/repo", "url": "https://example.com/repo"}
        parsed = {"note_draft": "## はじめに\n本文", "title_text": "題名。", "score": 80,
                  "action_text": "小さく検証する。", "why_not_important_text": "条件未確認"}
        gate = pipeline.build_candidate_gate_record(
            1, repo["nameWithOwner"], repo["url"], 80, "completed",
            pipeline.GATE_STATUS_FAIL, pipeline.GATE_STATUS_NOT_RUN,
            pipeline.GATE_STATUS_NOT_RUN, pipeline.GATE_STATUS_NOT_RUN,
            [{"reason_code": pipeline.REASON_CODE_FACT_UNSUPPORTED_CLAIM, "message": "unsupported"}],
            pipeline.CONTENT_STATUS_QUALITY_FAILED,
        )
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(pipeline, "REVIEW_CANDIDATES_DIR", os.path.join(directory, "review")), \
             patch.object(pipeline, "QUALITY_FAILURES_DIR", os.path.join(directory, "failed")), \
             patch.object(pipeline, "update_notion_quality_failed") as notion_update:
            review_path = pipeline.save_needs_editorial_review_article(repo, parsed, gate, {"primary_url": repo["url"]}, "review")
            failure_path = pipeline.save_quality_failed_article(repo, parsed, gate, {"primary_url": repo["url"]}, "failed")
            self.assertTrue(Path(review_path).exists())
            self.assertTrue(Path(review_path).with_suffix(".md").exists())
            self.assertTrue(Path(failure_path).exists())
            self.assertIn("本文", json.loads(Path(failure_path).read_text(encoding="utf-8"))["article"])
            notion_update.assert_not_called()

    def test_external_review_markdown_has_rubric_without_telegram_body(self):
        record = {
            "pipeline_status": pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,
            "failed_gate": "Publication Readiness",
            "decision_score": 82,
            "article": "記事本文",
            "gate_history": {"reason_codes": [{"reason_code": "PUB_ACTION_EVIDENCE_MISMATCH", "message": "action"}]},
        }
        markdown = pipeline.build_external_review_markdown(record)
        self.assertIn("# Review Candidate", markdown)
        self.assertIn("External Review Rubric", markdown)
        self.assertIn("記事本文", markdown)
        self.assertNotIn("Telegram", markdown)

    def test_false_positive_negative_regression_cases_are_registered_without_gate_change(self):
        fp = pipeline.build_regression_case("fp_001", "publication_readiness", "REVIEW", "A", "PUB_ACTION_EVIDENCE_MISMATCH", "article")
        fn = pipeline.build_regression_case("fn_001", "fact", "Ready", "D", "FACT_UNSUPPORTED_CLAIM", "article")
        self.assertEqual("PASS", fp["expected_result"])
        self.assertEqual("critical", fn["severity"])
        with tempfile.TemporaryDirectory() as directory, patch.object(pipeline, "REGRESSION_CASES_DIR", directory):
            path = pipeline.register_regression_case(fn)
            self.assertTrue(Path(path).exists())
            self.assertEqual("real_false_negative", json.loads(Path(path).read_text(encoding="utf-8"))["source_type"])

    def test_evidence_sufficiency_accepts_short_semantic_primary_evidence(self):
        source_info = {
            "primary_source_resolved": True,
            "context": "Author: Lab A\nMethod: an attention routing algorithm.\n"
                       "Limitation: not validated outside the benchmark.\n"
                       "Benchmark: 30 ms on the stated dataset.",
            "source_details": {}, "supplement_candidates": [], "checked_urls": set(),
            "evidence_documents": [{"url": "https://example.com", "retrieved": True}],
        }
        source_info["evidence_metadata"] = pipeline._build_evidence_metadata(source_info["context"], False)
        result = pipeline.assess_evidence_sufficiency(source_info)
        self.assertEqual(pipeline.EVIDENCE_SUFFICIENT, result["state"])

    def test_evidence_sufficiency_rejects_long_marketing_copy_without_support(self):
        source_info = {
            "primary_source_resolved": True,
            "context": ("The world's best AI platform delivers amazing results for every team. " * 80),
            "source_details": {}, "supplement_candidates": [], "checked_urls": set(),
            "evidence_documents": [{"url": "https://example.com", "retrieved": True}],
        }
        source_info["evidence_metadata"] = pipeline._build_evidence_metadata(source_info["context"], False)
        result = pipeline.assess_evidence_sufficiency(source_info)
        self.assertEqual(pipeline.EVIDENCE_INSUFFICIENT, result["state"])

    def test_evidence_supplement_can_make_missing_limitation_sufficient(self):
        source_info = {
            "primary_source_resolved": True,
            "context": "Author: Lab A\nMethod: an attention routing algorithm.\nBenchmark: 30 ms on the stated dataset.",
            "source_details": {},
            "supplement_candidates": [{"url": "https://example.com/appendix", "role": "SUPPLEMENTAL_SOURCE", "source_type": "official_docs"}],
            "checked_urls": {"https://example.com"},
            "evidence_documents": [{"url": "https://example.com", "retrieved": True}],
            "deep_source_urls": [], "evidence_supplement_attempts": 0,
        }
        source_info["evidence_metadata"] = pipeline._build_evidence_metadata(source_info["context"], False)
        self.assertEqual(pipeline.EVIDENCE_SUPPLEMENT_REQUIRED, pipeline.assess_evidence_sufficiency(source_info)["state"])
        with patch.object(pipeline, "fetch_webpage_context", return_value="Limitation: not validated outside this benchmark."):
            pipeline.supplement_source_evidence(source_info)
        result = pipeline.assess_evidence_sufficiency(source_info)
        self.assertEqual(pipeline.EVIDENCE_SUFFICIENT, result["state"])
        self.assertEqual(["https://example.com/appendix"], source_info["deep_source_urls"])

    def test_evidence_insufficient_skips_gemini_and_records_avoided_call(self):
        repo = {"nameWithOwner": "owner/marketing", "url": "https://example.com/marketing", "source": "GitHub"}
        source_info = {
            "primary_url": repo["url"], "primary_source_resolved": True,
            "context": "The world's best AI platform for every team.", "source_details": {},
            "supplement_candidates": [], "checked_urls": {repo["url"]},
            "evidence_documents": [{"url": repo["url"], "retrieved": True}],
            "method": pipeline.GROUNDING_SOURCE_NATIVE, "deep_source_scanned": False,
        }
        source_info["evidence_metadata"] = pipeline._build_evidence_metadata(source_info["context"], False)
        funnel = pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "prepare_source_context", return_value=source_info), \
             patch.object(pipeline, "resolve_followup_freshness", return_value={"triggered": False, "followup_found": False, "context": ""}), \
             patch.object(pipeline, "call_gemini_grounded_deep_dive") as gemini:
            self.assertIsNone(pipeline.generate_intelligence_report(repo, persist_results=True, candidate_rank=1))
        gemini.assert_not_called()
        self.assertEqual(1, funnel.counters["deep_dive_calls_avoided"])
        self.assertEqual(pipeline.EVIDENCE_INSUFFICIENT, funnel.records[0]["evidence_sufficiency"])

    def test_dynamic_retry_uses_reason_code_targeting_without_length_feedback(self):
        feedback, sections = pipeline.build_dynamic_retry_instruction([
            {"reason_code": pipeline.REASON_CODE_FACT_NUMERICAL_MISMATCH, "message": "number"},
            {"reason_code": pipeline.REASON_CODE_APPEAL_ACTION_COLLAPSE, "message": "action"},
        ])
        self.assertIn(pipeline.REASON_CODE_FACT_NUMERICAL_MISMATCH, feedback)
        self.assertIn(pipeline.REASON_CODE_APPEAL_ACTION_COLLAPSE, feedback)
        self.assertEqual(["numbers", "action"], sections)
        self.assertNotIn("文字数", feedback)

    def test_funnel_keeps_supplement_required_before_success(self):
        funnel = pipeline.DeepDiveGateFunnel()
        record = pipeline.build_candidate_gate_record(
            1, "example", "https://example.com", 80, "completed",
            final_status=pipeline.ARTICLE_STATUS_READY,
            evidence_result={"state": pipeline.EVIDENCE_SUFFICIENT,
                             "initial_state": pipeline.EVIDENCE_SUPPLEMENT_REQUIRED,
                             "supplement_attempted": True, "supplement_success": True},
        )
        funnel.record(record)
        self.assertEqual(1, funnel.counters["evidence_supplement_required"])
        self.assertEqual(1, funnel.counters["evidence_supplement_success"])
        self.assertEqual(1, funnel.counters["evidence_sufficient"])

    def _evidence_info(self, context, **extra):
        info = {
            "primary_source_resolved": True, "context": context, "source_details": {},
            "supplement_candidates": [], "checked_urls": {"https://example.com"},
            "evidence_documents": [{"url": "https://example.com", "retrieved": True}],
        }
        info.update(extra)
        info["evidence_metadata"] = pipeline._build_evidence_metadata(context, False)
        return info

    def test_missing_limitations_can_be_safe_with_low_risk_action_scope(self):
        info = self._evidence_info("Author: Lab A. Method: routing algorithm. Benchmark: 30 ms on the stated dataset.")
        result = pipeline.assess_evidence_sufficiency(info)
        self.assertEqual(pipeline.EVIDENCE_SUFFICIENT, result["state"])
        self.assertTrue(result["limitations_disclosed"])
        self.assertEqual("LOW", result["action_risk_tier"])
        self.assertTrue(result["action_supported_at_current_tier"])

    def test_research_freshness_can_be_limited_to_paper_time(self):
        info = self._evidence_info(
            "Authors: Lab A. This paper presents a method and benchmark result. Future work is planned.",
            source="ArXiv", freshness_status_available=False,
        )
        result = pipeline.assess_evidence_sufficiency(info)
        self.assertEqual(pipeline.EVIDENCE_SUFFICIENT, result["state"])
        self.assertTrue(result["freshness_scope_limited"])

    def test_current_price_requires_resolved_freshness(self):
        info = self._evidence_info(
            "Author: Vendor. Method: hosted API. Current pricing is described as 20 USD. Limitation: usage varies.",
            freshness_status_available=False,
        )
        result = pipeline.assess_evidence_sufficiency(info)
        self.assertEqual(pipeline.EVIDENCE_INSUFFICIENT, result["state"])
        self.assertIn("freshness_status_available_if_time_sensitive", result["blocking_missing"])

    def test_high_risk_action_is_not_supported_by_weak_evidence(self):
        info = self._evidence_info(
            "Author: Lab A. Method: routing algorithm. Benchmark: 30 ms on the stated dataset.",
            requested_action_risk_tier="HIGH",
        )
        result = pipeline.assess_evidence_sufficiency(info)
        self.assertEqual(pipeline.EVIDENCE_SUFFICIENT, result["state"])
        self.assertEqual("HIGH", result["action_risk_downgraded_from"])
        self.assertEqual("LOW", result["action_risk_tier"])

    def test_medium_and_high_action_downgrade_to_low_after_supplement_is_exhausted(self):
        context = "Author: Lab A. Method: routing algorithm. Benchmark: 30 ms on the stated dataset."
        for tier in ("MEDIUM", "HIGH"):
            info = self._evidence_info(
                context, requested_action_risk_tier=tier,
                evidence_supplement_attempted=True,
            )
            result = pipeline.assess_evidence_sufficiency(info)
            self.assertEqual(pipeline.EVIDENCE_SUFFICIENT, result["state"])
            self.assertEqual("LOW", result["action_risk_tier"])
            self.assertEqual(tier, result["action_risk_downgraded_from"])
            self.assertTrue(result["action_supported_at_current_tier"])

    def test_medium_action_requests_supplement_before_downgrade_when_candidate_exists(self):
        info = self._evidence_info(
            "Author: Lab A. Method: routing algorithm. Benchmark: 30 ms on the stated dataset.",
            requested_action_risk_tier="MEDIUM",
            supplement_candidates=[{"url": "https://example.com/docs", "role": "PRIMARY_SOURCE"}],
        )
        result = pipeline.assess_evidence_sufficiency(info)
        self.assertEqual(pipeline.EVIDENCE_SUPPLEMENT_REQUIRED, result["state"])

    def test_real_article_regression_cases_are_registered_and_not_allowed_to_over_reject(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(pipeline, "REGRESSION_CASES_DIR", directory):
            paths = pipeline.register_real_article_regression_cases()
        self.assertEqual(4, len(paths))
        titles = {row["title"] for row in pipeline.REAL_ARTICLE_REGRESSION_CASES}
        self.assertEqual({"Model Hypnosis", "Topological Attribution Distance (TAD)", "When Agents Coordinate", "Taffy"}, titles)
        for case in pipeline.REAL_ARTICLE_REGRESSION_CASES:
            self.assertTrue(pipeline.real_article_regression_allows(case["case_id"], pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW))
            self.assertFalse(pipeline.real_article_regression_allows(case["case_id"], pipeline.CONTENT_STATUS_QUALITY_FAILED))

    def test_evidence_reason_codes_are_specific(self):
        rows = pipeline.evidence_reason_rows({"blocking_missing": ["primary_source_resolved", "high_risk_action_unsupported"]})
        self.assertEqual(pipeline.REASON_CODE_PRIMARY_SOURCE_UNRESOLVED, rows[0]["reason_code"])
        self.assertEqual(pipeline.REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED, rows[1]["reason_code"])

    def test_gate_history_keeps_executed_gate_states_and_grounding_stages(self):
        record = pipeline.build_candidate_gate_record(
            1, "example", "https://example.com", 80, "completed",
            pipeline.GATE_STATUS_PASS, pipeline.GATE_STATUS_WARNING,
            pipeline.GATE_STATUS_REVIEW, pipeline.GATE_STATUS_WARNING,
            final_status=pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,
            retry_diagnostics={"retry_attempted": True, "trigger_reason_codes": [{"reason_code": "PUB_SCORE_NARRATIVE_MISMATCH"}]},
            candidate_origin="pending_retry",
        )
        self.assertEqual(pipeline.GATE_STATUS_REVIEW, record["publication_readiness_gate"])
        self.assertEqual(pipeline.GATE_STATUS_WARNING, record["human_appeal_gate"])
        self.assertTrue(record["retry_attempted"])
        self.assertEqual("pending_retry", record["candidate_origin"])

    def test_funnel_separates_retry_new_and_generation_stages(self):
        funnel = pipeline.DeepDiveGateFunnel()
        record = pipeline.build_candidate_gate_record(
            1, "example", "https://example.com", 80, "completed",
            final_status=pipeline.ARTICLE_STATUS_READY, candidate_origin="pending_retry",
            retry_diagnostics={"retry_attempted": True, "retry_succeeded": True,
                               "trigger_reason_codes": [{"reason_code": "FACT_UNSUPPORTED_CLAIM"}]},
        )
        funnel.record(record)
        funnel.incr("generation_api_completed")
        funnel.incr("article_parsed")
        funnel.incr("quality_evaluation_completed")
        self.assertEqual(1, funnel.counters["pending_retry_candidates_attempted"])
        self.assertEqual(0, funnel.counters["new_deep_dive_candidates_attempted"])
        self.assertEqual(1, funnel.counters["retry_attempted"])
        self.assertEqual(1, funnel.counters["generation_api_completed"])

    def test_numeric_and_actor_gaps_do_not_block_when_article_does_not_assert_them(self):
        info = self._evidence_info("Method: routing algorithm. Limitation: benchmark scope only.")
        result = pipeline.assess_evidence_sufficiency(info)
        self.assertEqual(pipeline.EVIDENCE_SUFFICIENT, result["state"])
        self.assertFalse(result["actor_attribution_allowed"])
        self.assertTrue(result["numeric_claims_allowed"])

    def test_action_risk_tier_classifies_actual_article_action(self):
        self.assertEqual("LOW", pipeline.classify_action_risk_tier("まずは限定PoCと比較テストを行う。"))
        self.assertEqual("MEDIUM", pipeline.classify_action_risk_tier("限定ユーザーへ導入する。"))
        self.assertEqual("HIGH", pipeline.classify_action_risk_tier("全社へ全面導入し、本番移行する。"))

    def test_source_context_adds_official_metadata_url_as_supplement_candidate(self):
        repo = {
            "source": "ProductHunt", "nameWithOwner": "product", "url": "https://www.producthunt.com/posts/product",
            "primaryUrl": "https://www.producthunt.com/posts/product",
            "sourceDetails": {"official_url": "https://vendor.example/docs"},
        }
        with patch.object(pipeline, "fetch_webpage_context", return_value=""), \
             patch.object(pipeline, "_fetch_html_document", return_value=("", [], repo["primaryUrl"])):
            info = pipeline.prepare_source_context(repo)
        self.assertEqual("https://vendor.example/docs", info["supplement_candidates"][0]["url"])

    def test_producthunt_redirect_resolves_official_site_and_docs_candidates(self):
        redirect = "https://www.producthunt.com/r/product"
        official = "https://vendor.example"
        repo = {
            "source": "ProductHunt", "nameWithOwner": "product", "url": redirect,
            "primaryUrl": redirect, "sourceDetails": {"producthunt_url": redirect},
        }
        with patch.object(pipeline, "_resolve_producthunt_official_url", return_value=official), \
             patch.object(pipeline, "fetch_webpage_context", return_value=""), \
             patch.object(pipeline, "_fetch_html_document", return_value=("", [("https://vendor.example/docs", "Documentation"), ("https://github.com/vendor/product", "GitHub")], official)):
            info = pipeline.prepare_source_context(repo)
        self.assertEqual(official, info["primary_url"])
        self.assertEqual({"https://vendor.example/docs", "https://github.com/vendor/product"}, {row["url"] for row in info["supplement_candidates"]})

    def test_producthunt_redirect_resolver_accepts_external_final_url(self):
        redirect = "https://www.producthunt.com/r/product"
        with patch.object(pipeline, "_http_get_limited", return_value=(b"", "text/html", "https://vendor.example")):
            self.assertEqual("https://vendor.example", pipeline._resolve_producthunt_official_url(redirect))

    def test_ready_zero_summary_counts_detailed_evidence_reason_code(self):
        funnel = pipeline.DeepDiveGateFunnel()
        for rank in range(1, 8):
            funnel.record(pipeline.build_candidate_gate_record(
                rank, f"example-{rank}", f"https://example.com/{rank}", 80, "skipped",
                reason_codes=[{"reason_code": pipeline.REASON_CODE_TECHNICAL_CLAIMS_INSUFFICIENT, "message": "technical_claims_available"}],
                final_status="Evidence Insufficient",
                evidence_result={"state": pipeline.EVIDENCE_INSUFFICIENT},
            ))
        self.assertIn("TECHNICAL_CLAIMS_INSUFFICIENT: 7", funnel.render_ready_zero_summary())

    def test_evidence_metadata_recalls_release_note_technical_entities_and_limitations(self):
        metadata = pipeline._build_evidence_metadata(
            "Go 1.27 adds package rand and NewTestServer. The API is experimental and not supported in WIP mode. Runtime: 12 ms.", True,
        )
        self.assertEqual("FOUND", metadata["coverage"]["method"])
        self.assertEqual("FOUND", metadata["coverage"]["limitations"])
        self.assertIn("NewTestServer", metadata["named_technical_entities"])
        self.assertIn("12 ms", metadata["numeric_claims"])

    def test_openrouter_technical_names_are_not_actor_attribution_mismatches(self):
        reason = pipeline._reason_code("source-boundary unsupported named fact: Model Context Protocol, NewTestServer", "fact")
        self.assertEqual(pipeline.REASON_CODE_FACT_UNSUPPORTED_NAMED_FACT, reason)
        self.assertNotEqual(pipeline.REASON_CODE_FACT_ACTOR_MISMATCH, reason)

    def test_semantic_background_heading_satisfies_why_structure_role(self):
        parsed = {
            "note_draft": "## 気になった背景\n背景\n## 結論\n結論\n## 概要\n概要\n## 要点\n要点\n## 私ならこうする\n判断\n## 最終判断\n最終判断",
            "decision_text": "TRY", "score": 63, "title_text": "検証する価値はある。",
            "decision_reason_text": "理由", "paradigm_shift_text": "変化", "alternative_comparison_text": "比較", "migration_cost_text": "コスト",
            "why_not_important_text": "限定的", "who_should_use_text": "検証チーム", "who_should_not_use_text": "本番チーム",
            "action_text": "限定PoCを実施する。", "future_scenario_text": "将来", "source_summary_text": "原資料",
        }
        _, failures = pipeline.validate_fact_gate(parsed, "example", source_context="Method: documented.")
        self.assertNotIn("required heading missing: 重要性", failures)

    def test_taffy_low_risk_poc_does_not_create_score_narrative_mismatch(self):
        parsed = {"title_text": "Taffyの限定検証。", "note_draft": "## 本文\n限定PoCで比較する。", "action_text": "検証環境で限定PoCと比較テストを行う。", "score": 63}
        _, issues = pipeline.validate_publication_readiness_gate(parsed, "Official documentation.", {"sufficient": True})
        self.assertNotIn("score_narrative_mismatch", issues)

    def test_go_127_concrete_ci_action_keeps_decision_voice(self):
        parsed = {"title_text": "Go 1.27はCIで確認する。", "note_draft": "## 気になった背景\n変更点を確認する。\n## 実務で使うなら\nCIで回帰テストとprofilingを実行する。", "action_text": "CIで回帰テストとprofilingを実施する。"}
        _, issues = pipeline.validate_human_appeal_gate(parsed)
        self.assertNotIn("decision_voice_missing", issues)

    def test_pacing_condition_generalization_remains_fact_failure(self):
        failures = pipeline._find_final_wording_violations("この最適化で高速になる。", {"required_qualifiers": ["toy example"]})
        self.assertIn("EVIDENCE_CLASS_GENERALIZED", failures)

    def test_retry_diagnostics_separate_trigger_from_final_reason_codes(self):
        trigger = [{"reason_code": pipeline.REASON_CODE_FACT_UNSUPPORTED_NAMED_FACT, "message": "old issue"}]
        final = [{"reason_code": pipeline.REASON_CODE_PUB_HEADLINE_OVERCLAIM, "message": "remaining issue"}]
        diagnostics = pipeline.finalize_retry_diagnostics(
            {"retry_attempted": True, "trigger_reason_codes": trigger}, final, "NEEDS_EDITORIAL_REVIEW", "final draft",
        )
        self.assertEqual(trigger, diagnostics["trigger_reason_codes"])
        self.assertEqual(final, diagnostics["final_reason_codes"])
        self.assertFalse(diagnostics["retry_succeeded"])

    def test_arxiv_transient_integrity_failure_is_pending_retry_not_quality_failed(self):
        repo = {"source": "ArXiv", "nameWithOwner": "paper", "url": "https://arxiv.org/abs/2601.12345"}
        funnel = pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "_verify_arxiv_source_integrity", return_value=(False, "TRANSIENT: arXiv再照会に失敗", repo)), \
             patch.object(pipeline, "save_quality_failed_article") as quality_failed:
            result = pipeline.generate_intelligence_report(repo, persist_results=True, candidate_rank=1)
        self.assertIsNone(result)
        quality_failed.assert_not_called()
        self.assertEqual(pipeline.CONTENT_STATUS_PENDING_RETRY, funnel.records[0]["final_status"])

    def test_arxiv_title_mismatch_remains_fail_closed(self):
        repo = {"source": "ArXiv", "nameWithOwner": "paper", "url": "https://arxiv.org/abs/2601.12345"}
        funnel = pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "_verify_arxiv_source_integrity", return_value=(False, "arXiv title mismatch", repo)), \
             patch.object(pipeline, "save_quality_failed_article") as quality_failed, \
             patch.object(pipeline, "send_telegram_alert"):
            result = pipeline.generate_intelligence_report(repo, persist_results=True, candidate_rank=1)
        self.assertIsNone(result)
        quality_failed.assert_called_once()
        self.assertEqual(pipeline.CONTENT_STATUS_QUALITY_FAILED, funnel.records[0]["final_status"])


class TestArxivEvidenceLinkFiltering(unittest.TestCase):
    def test_research_link_parser_excludes_arxiv_navigation_urls(self):
        html = """
        <a href="/prevnext?id=2608.19140&function=next">next</a>
        <a href="/IgnoreMe">ignore</a>
        <a href="/">arXiv home</a>
        <a href="/pdf/2608.19140.pdf">PDF</a>
        <a href="https://github.com/example/project">GitHub</a>
        """
        parser = pipeline._ResearchLinkParser("https://arxiv.org/abs/2608.19140")
        parser.feed(html)
        urls = [url for url, _ in parser.links]
        self.assertIn("https://arxiv.org/pdf/2608.19140.pdf", urls)
        self.assertIn("https://github.com/example/project", urls)
        self.assertFalse(any("/prevnext" in url for url in urls))
        self.assertFalse(any("/IgnoreMe" in url for url in urls))
        self.assertNotIn("https://arxiv.org/", urls)

    def test_prepare_source_context_prioritizes_same_paper_pdf(self):
        repo = {
            "source": "ArXiv",
            "nameWithOwner": "paper",
            "url": "https://arxiv.org/abs/2608.19140v1",
            "primaryUrl": "https://arxiv.org/abs/2608.19140v1",
            "sourceContext": "Abstract with method and benchmark details.",
            "sourceDetails": {},
        }
        extracted = [
            ("https://arxiv.org/prevnext?id=2608.19140&function=next", "next"),
            ("https://arxiv.org/IgnoreMe", "ignore"),
            ("https://github.com/example/project", "GitHub"),
        ]
        with patch.object(pipeline, "_fetch_html_document", return_value=("landing text", extracted, repo["primaryUrl"])), \
             patch.object(pipeline, "_fetch_arxiv_official_link_context", return_value=[]):
            info = pipeline.prepare_source_context(repo)
        urls = [row["url"] for row in info["supplement_candidates"]]
        self.assertEqual("https://arxiv.org/pdf/2608.19140.pdf", urls[0])
        self.assertIn("https://github.com/example/project", urls)
        self.assertFalse(any("/prevnext" in url or "/IgnoreMe" in url for url in urls))

    def test_arxiv_future_work_does_not_trigger_freshness_navigation(self):
        html = b"""
        <html><body>future planned work
        <a href='/prevnext?id=2608.19140&function=next'>next</a>
        <a href='/help'>update help</a>
        </body></html>
        """
        source_info = {
            "context": "Future work is planned.",
            "primary_url": "https://arxiv.org/abs/2608.19140v1",
        }
        with patch.object(pipeline, "_http_get_limited", return_value=(html, "text/html", source_info["primary_url"])), \
             patch.object(pipeline, "fetch_webpage_context") as fetch:
            result = pipeline.resolve_followup_freshness(source_info)
        self.assertFalse(result["triggered"])
        self.assertFalse(result["followup_found"])
        fetch.assert_not_called()

    def test_evidence_document_default_matches_spec(self):
        self.assertEqual(3, pipeline.MAX_EVIDENCE_DOCUMENTS)


if __name__ == "__main__":
    unittest.main()
