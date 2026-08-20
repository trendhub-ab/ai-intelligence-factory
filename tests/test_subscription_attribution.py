import csv
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
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")

# Safe import shims for minimal local environments.
try:
    from google import genai  # noqa: F401
except ImportError:
    google_mod = sys.modules.get("google") or types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class APIError(Exception): pass
    class Client:
        def __init__(self, **_kwargs):
            self.chats = types.SimpleNamespace(create=lambda **_kw: None)
    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.setdefault("google", google_mod)
    sys.modules["google.genai"] = genai_mod
    sys.modules["google.genai.errors"] = errors_mod

spec = importlib.util.spec_from_file_location("pipeline_subscription_under_test", ROOT / "pipeline.py")
pipeline = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(pipeline)

attrib_spec = importlib.util.spec_from_file_location("subscription_attribution_under_test", ROOT / "subscription_attribution.py")
attrib = importlib.util.module_from_spec(attrib_spec)
assert attrib_spec.loader
attrib_spec.loader.exec_module(attrib)


class TestSubscriptionAttributionFoundation(unittest.TestCase):
    def test_article_id_is_stable_across_tracking_query_variants(self):
        a = pipeline.build_article_attribution_id("GitHub", "https://github.com/acme/repo?utm_source=x")
        b = pipeline.build_article_attribution_id("GitHub", "https://github.com/acme/repo?utm_medium=y")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("aif-"))

    def test_article_id_does_not_change_with_discovery_source(self):
        github = pipeline.build_article_attribution_id("GitHub", "https://example.com/primary")
        hn = pipeline.build_article_attribution_id("HackerNews", "https://example.com/primary")
        self.assertEqual(github, hn)

    def test_tracking_url_preserves_business_query_and_replaces_attribution_keys(self):
        with patch.object(pipeline, "ENABLE_SUBSCRIPTION_ATTRIBUTION", True), \
             patch.object(pipeline, "SUBSCRIPTION_CAMPAIGN_ID", "campaign"):
            url = pipeline.build_subscription_tracking_url(
                "aif-123", "https://example.com/join?plan=pro&utm_source=old&aif_article_id=old#offer"
            )
        self.assertIn("plan=pro", url)
        self.assertIn("utm_source=note", url)
        self.assertIn("utm_medium=free_article", url)
        self.assertIn("utm_campaign=campaign", url)
        self.assertIn("utm_content=aif-123", url)
        self.assertIn("aif_article_id=aif-123", url)
        self.assertNotIn("utm_source=old", url)
        self.assertTrue(url.endswith("#offer"))

    def test_invalid_or_missing_landing_url_never_inserts_broken_cta(self):
        with patch.object(pipeline, "ENABLE_SUBSCRIPTION_ATTRIBUTION", True), \
             patch.object(pipeline, "SUBSCRIPTION_LANDING_URL", "javascript:alert(1)"):
            self.assertEqual("", pipeline.build_subscription_tracking_url("aif-123"))
            self.assertEqual("", pipeline.build_subscription_cta("aif-123"))

    def test_free_manuscript_cta_sells_db_and_monthly_summary_not_paid_article(self):
        with patch.object(pipeline, "ENABLE_SUBSCRIPTION_ATTRIBUTION", True), \
             patch.object(pipeline, "SUBSCRIPTION_LANDING_URL", "https://example.com/membership"):
            manuscript = pipeline.build_clean_note_manuscript(
                "本文は最後まで無料です。", "acme/repo", "https://github.com/acme/repo",
                "MIT", source="GitHub", title_text="無料記事タイトル"
            )
        self.assertIn("会員向け意思決定DB＋月次サマリーを見る", manuscript)
        self.assertIn("本文は最後まで無料です。", manuscript)
        self.assertNotIn("有料記事", manuscript)
        self.assertIsNone(pipeline.PAID_AREA_PATTERN.search(manuscript))

    def test_ready_manifest_contains_only_aggregate_article_metadata(self):
        repo = {"source": "GitHub", "url": "https://github.com/acme/repo", "nameWithOwner": "acme/repo"}
        parsed = {"title_text": "Title", "score": 88}
        context = {"score": 84, "commercial_score": 78, "shelf_life_score": 72,
                   "shelf_life": "EVERGREEN", "portfolio_topic": "DEVTOOLS",
                   "deep_dive_priority_score": 81.9}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(pipeline, "SUBSCRIPTION_ATTRIBUTION_DIR", directory), \
             patch.object(pipeline, "SUBSCRIPTION_LANDING_URL", "https://example.com/join"), \
             patch.object(pipeline, "_upload_subscription_attribution_to_github", return_value=None):
            path = pipeline.save_subscription_attribution_record(
                repo, parsed, "2026-08-21T00:00:00+09:00", "page-1", context
            )
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual("note_free_article", data["channel"])
        self.assertEqual("subscriber_decision_db_plus_monthly_summary", data["offer"])
        self.assertEqual("awaiting_external_metrics", data["measurement_status"])
        self.assertTrue(data["cta_enabled"])
        serialized = json.dumps(data).lower()
        for forbidden in ("email", "customer_id", "payment_id"):
            self.assertNotIn(forbidden, serialized)

    def test_metrics_import_rejects_unknown_article_id(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.csv"
            path.write_text("article_id,attribution_method,note_views\nunknown,note_dashboard_only,10\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown article_id"):
                attrib.load_metrics(path, {"aif-known"})

    def test_metrics_import_rejects_pii_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.csv"
            path.write_text("article_id,attribution_method,email,note_views\naif-known,note_dashboard_only,user@example.com,10\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "PII-like columns"):
                attrib.load_metrics(path, {"aif-known"})

    def test_note_dashboard_only_cannot_claim_subscriber_conversion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.csv"
            path.write_text(
                "article_id,attribution_method,note_views,new_subscribers\n"
                "aif-known,note_dashboard_only,100,2\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "cannot support metrics"):
                attrib.load_metrics(path, {"aif-known"})

    def test_tracked_cta_can_measure_clicks_but_not_claim_revenue(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metrics.csv"
            path.write_text(
                "article_id,attribution_method,note_views,cta_clicks,subscription_revenue_yen\n"
                "aif-known,tracked_cta,100,5,1980\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "cannot support metrics"):
                attrib.load_metrics(path, {"aif-known"})

    def test_rollup_calculates_subscription_conversion_without_enabling_ranking_feedback(self):
        manifests = {"aif-1": {"article_id": "aif-1", "source": "GitHub", "note_title": "T"}}
        rows = [{
            "article_id": "aif-1", "attribution_method": "end_to_end", "note_url": "https://note.com/x", "period_start": "2026-08-01",
            "period_end": "2026-08-31", "note_views": 1000.0, "cta_clicks": 50.0,
            "new_subscribers": 5.0, "retained_subscribers": 4.0, "subscription_revenue_yen": 9900.0,
        }]
        rollup = attrib.build_rollup(manifests, rows)
        self.assertAlmostEqual(0.05, rollup["overall_cta_click_rate"])
        self.assertAlmostEqual(0.10, rollup["overall_subscriber_conversion_per_click"])
        self.assertAlmostEqual(0.005, rollup["overall_subscriber_conversion_per_view"])
        self.assertFalse(rollup["ranking_feedback_enabled"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
