import os
import sys
import types
import unittest

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GH_PAT", "test-token")
os.environ.setdefault("GEMINI_QUOTA_PROJECT_ID", "test-project")
try:
    from google import genai  # noqa: F401
except ImportError:
    google_mod = sys.modules.get("google") or types.ModuleType("google")
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class APIError(Exception): pass
    class Client:
        def __init__(self, **_kwargs): self.chats = types.SimpleNamespace(create=lambda **_kw: None)
    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.update({"google": google_mod, "google.genai": genai_mod, "google.genai.errors": errors_mod})

import pipeline


class Run122RealArticleRegressionHardeningTests(unittest.TestCase):
    def _parsed(self, article: str, name: str = "Example"):
        return {
            "note_draft": article,
            "decision_text": "TRY",
            "score": 72,
            "title_text": f"{name}を限定環境で検証する。",
            "decision_reason_text": "一次情報を確認し、小さく検証する価値がある。",
            "action_text": "限定環境で比較検証する。",
            "source_summary_text": "公式一次情報が公開されている。",
        }

    def test_cobalt_sdk_is_not_cross_entity_named_fact_when_entity_and_sdk_are_evidenced(self):
        draft = "Cobalt SDKはRust向けSDKとして公開され、対応端末で利用できる。"
        evidence = "Cobalt is an application platform for Kobo. Rust SDK documentation and examples are available."
        self.assertEqual([], pipeline._find_source_boundary_violations(draft, evidence, "Cobalt"))

    def test_entity_descriptor_does_not_bootstrap_unknown_entity(self):
        draft = "OpenAI SDKは公式に提供されている。"
        evidence = "Cobalt SDK documentation is available. OpenAI is mentioned only as an unrelated link."
        failures = pipeline._find_source_boundary_violations(draft, evidence, "Cobalt")
        self.assertTrue(any("OpenAI SDK" in item for item in failures))

    def test_esp_idf_full_name_alias_is_supported_by_acronym(self):
        draft = "Espressif IoT Development Frameworkは公式Dockerイメージで利用できる。"
        evidence = "The official ESP-IDF Docker image contains the ESP-IDF toolchain."
        self.assertEqual([], pipeline._find_source_boundary_violations(draft, evidence, "ESP32 Firmware"))

    def test_protocol_end_marker_is_stripped_before_fact_gate(self):
        response = """・Decision: TRY\n・Decision Score: 合計: 72 / 100\n・Decision Reason: 小さく試す。\n・Action: 限定環境で比較検証する。\n・Source Summary: 公式資料。\n===NOTE_DRAFT_START===\n検証記事。\n\n本文です。\n===NOTE_DRAFT_END==="""
        parsed = pipeline._parse_gemini_response(response)
        self.assertNotIn("NOTE_DRAFT_END", parsed["note_draft"])
        self.assertNotIn("INTERNAL_DRAFT_DELIMITER_LEAKED", pipeline._find_final_wording_violations(parsed["note_draft"], {}))

    def test_marker_like_inline_prose_is_not_silently_removed(self):
        text = "本文で ===NOTE_DRAFT_END=== という文字列を説明する。"
        cleaned, count = pipeline._strip_internal_note_control_lines(text)
        self.assertEqual(0, count)
        self.assertEqual(text, cleaned)

    def test_constraints_and_risks_count_as_editorial_reservation(self):
        for article in (
            "導入候補です。対応機種には制約があり、将来の互換性リスクも残る。",
            "導入候補です。実務上の限界と注意点を確認してから試したい。",
            "導入候補です。一方で、本番未検証という課題が残る。",
        ):
            self.assertNotIn("missing observation or reservation", pipeline._find_humanization_violations(article))

    def test_content_specific_headings_are_not_fact_failure(self):
        article = """MCPの新しいロードマップが公開された。運用設計への影響を確認する。\n\n## 静かな大改修。\nステートレス化が進む。\n\n## 標準に追随できる設計へ。\n私なら限定環境で比較検証する。"""
        parsed = self._parsed(article, "MCP")
        ok, failures = pipeline.validate_fact_gate(parsed, "MCP", source_context="MCP roadmap official documentation")
        self.assertFalse(any("required heading missing" in f for f in failures))
        self.assertNotIn("ARTICLE_STRUCTURE_INCOMPLETE", failures)

    def test_long_unheaded_article_is_publication_review_not_fact_failure(self):
        article = ("MCPのロードマップが公開された。実務設計への影響を見る。" + "運用条件を確認する。" * 150
                   + "最後に私なら限定環境で比較検証する。")
        parsed = self._parsed(article, "MCP")
        ok, fact_failures = pipeline.validate_fact_gate(parsed, "MCP", source_context="MCP official roadmap")
        self.assertNotIn("ARTICLE_STRUCTURE_INCOMPLETE", fact_failures)
        state, issues = pipeline.validate_publication_readiness_gate(parsed, "MCP official roadmap", {"sufficient": True})
        self.assertEqual("REVIEW", state)
        self.assertIn("article_structure_needs_edit", issues)
        row = pipeline.map_gate_reasons("publication", ["article_structure_needs_edit"])[0]
        self.assertEqual(pipeline.REASON_CODE_STRUCTURE_MISSING, row["reason_code"])

    def test_short_unheaded_copy_is_not_overregulated(self):
        article = "新機能が公開された。まず小さく試す。"
        parsed = self._parsed(article)
        state, issues = pipeline.validate_publication_readiness_gate(parsed, "official source", {"sufficient": True})
        self.assertNotIn("article_structure_needs_edit", issues)

    def test_source_boundary_remains_hard_for_truly_unsupported_product(self):
        parsed = self._parsed("Cobaltは公開された。Enterprise Syncも公式に提供されている。", "Cobalt")
        ok, failures = pipeline.validate_fact_gate(parsed, "Cobalt", source_context="Cobalt SDK official docs")
        self.assertFalse(ok)
        self.assertTrue(any("Enterprise Sync" in f for f in failures))


if __name__ == "__main__":
    unittest.main()
