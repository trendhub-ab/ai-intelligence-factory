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
    from google import genai  # noqa: F401
except ImportError:
    google_mod = types.ModuleType("google")
    google_mod.__path__ = []
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class APIError(Exception):
        pass
    class Client:
        def __init__(self, **_kwargs):
            self.models = types.SimpleNamespace()
    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.update({"google": google_mod, "google.genai": genai_mod, "google.genai.errors": errors_mod})

import pipeline  # noqa: E402


class TestArticleAuditArtifact(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.audit_dir = Path(self.tmp.name) / "article_audit"
        self.repo = {"nameWithOwner": "owner/example", "url": "https://example.com/item", "source": "HackerNews"}
        self.source = {"primary_url": "https://example.com/original", "evidence_urls": ["https://example.com/original"]}
        self.parsed = {"note_draft": "# Final\n最終稿", "score": 81}

    def _files(self):
        return {p.name: p.read_text(encoding="utf-8") for p in self.audit_dir.rglob("*.md")}

    def test_quality_failed_preserves_three_human_review_stages(self):
        snapshots = {
            "generated_original": "# Original\n初稿",
            "after_quality_retry": "# Retry\n再構成稿",
            "final_after_rescue": "# Rescue\n最終救済稿",
        }
        with patch.object(pipeline, "ARTICLE_AUDIT_DIR", str(self.audit_dir)):
            pipeline.save_article_audit_package(
                self.repo, "QUALITY_FAILED", self.parsed, self.source,
                {"reason": "fact"}, "fact failed", snapshots=snapshots,
            )
        files = self._files()
        self.assertIn("generated_original.md", files)
        self.assertIn("after_quality_retry.md", files)
        self.assertIn("final_after_rescue.md", files)
        self.assertIn("初稿", files["generated_original.md"])
        self.assertIn("再構成稿", files["after_quality_retry.md"])
        self.assertIn("最終救済稿", files["final_after_rescue.md"])
        self.assertIn("RUN_SUMMARY.md", files)

    def test_ready_keeps_only_final_publishable_manuscript(self):
        snapshots = {"generated_original": "初稿", "after_quality_retry": "再稿"}
        with patch.object(pipeline, "ARTICLE_AUDIT_DIR", str(self.audit_dir)):
            pipeline.save_article_audit_package(
                self.repo, "READY", self.parsed, self.source, None, "",
                snapshots=snapshots, clean_manuscript="# Ready\n公開稿",
            )
        files = self._files()
        self.assertIn("final.md", files)
        self.assertIn("公開稿", files["final.md"])
        self.assertNotIn("generated_original.md", files)
        self.assertNotIn("after_quality_retry.md", files)

    def test_pending_retry_keeps_latest_available_manuscript(self):
        with patch.object(pipeline, "ARTICLE_AUDIT_DIR", str(self.audit_dir)):
            pipeline.save_article_audit_package(
                self.repo, "PENDING_RETRY", self.parsed, self.source, None, "budget exhausted",
                snapshots={"generated_original": "初稿"},
            )
        files = self._files()
        self.assertIn("current.md", files)
        self.assertIn("最終稿", files["current.md"])
        self.assertIn("budget exhausted", files["current.md"])

    def test_audit_writer_has_no_gemini_dependency(self):
        import inspect
        source = inspect.getsource(pipeline.save_article_audit_package)
        self.assertNotIn("call_gemini", source)
        self.assertNotIn("client.models", source)

    def test_daily_artifact_upload_includes_article_audit(self):
        workflow = (ROOT / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
        self.assertIn("article_audit/", workflow)
        self.assertIn("private-gate-review-${{ github.run_number }}", workflow)


if __name__ == "__main__":
    unittest.main()
