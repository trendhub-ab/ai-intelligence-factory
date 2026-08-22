import os
import sys
import types
import unittest
from pathlib import Path

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


class TestRun100HumanAuditRegressions(unittest.TestCase):
    def setUp(self):
        pipeline._reset_article_display_variant_rotation()

    def test_mcp_full_name_is_supported_when_primary_evidence_uses_acronym(self):
        draft = "OpenAIのAPIはModel Context Protocolに対応している。"
        context = "Tools supported: MCP, computer use, code interpreter."
        failures = pipeline._find_source_boundary_violations(draft, context)
        self.assertFalse(
            any("Model Context" in failure for failure in failures),
            failures,
        )

    def test_short_acronym_alias_requires_token_boundary(self):
        expanded = pipeline._expand_evidence_aliases("storage layer behavior")
        self.assertNotIn("Retrieval Augmented Generation", expanded)

    def test_alias_expansion_does_not_invent_unrelated_named_facts(self):
        draft = "OpenAIのAPIはEnterprise Syncを提供している。"
        context = "Tools supported: MCP, computer use, code interpreter."
        failures = pipeline._find_source_boundary_violations(draft, context)
        self.assertTrue(any("Enterprise Sync" in failure for failure in failures), failures)

    def test_ordinal_structure_is_audit_warning_not_publication_blocker(self):
        article = (
            "第一に、入力条件を確認します。十分な説明文です。\n\n"
            "第二に、再現条件を確認します。十分な説明文です。\n\n"
            "第三に、制約を確認します。ただ、本番条件には未検証部分が残ります。"
        )
        ok, warnings = pipeline.validate_editorial_gate({"note_draft": article}, "meshoptimizer")
        self.assertTrue(ok, warnings)
        self.assertIn("mechanical ordinal structure", warnings)

    def test_material_list_like_editorial_defect_still_blocks(self):
        article = "\n".join(f"- 項目{i}" for i in range(20))
        ok, warnings = pipeline.validate_editorial_gate({"note_draft": article}, "list-heavy")
        self.assertFalse(ok)
        self.assertIn("article too list-like; rewrite as natural prose", warnings)

    def test_run_local_variant_balancing_prevents_run100_heading_collision(self):
        first = pipeline._article_display_variant("ESP32 Firmware Development with Docker Sandboxes")
        second = pipeline._article_display_variant("Kobo can run apps now")
        self.assertNotEqual(first["style"], second["style"])
        # Quality Retry for the same article must retain its already assigned profile.
        self.assertEqual(first, pipeline._article_display_variant("ESP32 Firmware Development with Docker Sandboxes"))


if __name__ == "__main__":
    unittest.main()
