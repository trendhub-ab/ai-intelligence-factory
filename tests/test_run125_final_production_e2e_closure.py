import os
import sys
import types
import unittest
from pathlib import Path

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


class Run125FinalProductionE2EClosureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = (Path(__file__).parent / "fixtures" / "run125_mcp_real_e2e_rejected.md").read_text(encoding="utf-8")
        # remove private regen comment; only public manuscript behavior is under test
        cls.article = cls.fixture.split("-->", 1)[-1].strip()

    def test_real_mcp_request_tool_call_shape_is_not_numeric_claim(self):
        failures = pipeline._find_unsupported_numeric_claims(
            self.article,
            "The roadmap describes agentic messaging and long-running interactions; no request-rate limit is stated.",
        )
        self.assertFalse(any("1リクエスト" in item for item in failures), failures)

    def test_real_gate_path_does_not_reintroduce_protocol_false_positive(self):
        parsed = {
            "note_draft": "従来の単純な1リクエスト・1ツール呼び出しから、長時間動作するエージェントへ利用形態が変化している。",
            "decision_text": next(iter(pipeline.ALLOWED_DECISIONS)),
            "score": 70,
            "title_text": "MCPの通信設計を確認する。",
            "decision_reason_text": "一次情報にある通信設計を限定検証するため。",
            "action_text": "検証環境で限定的に試す。",
            "source_summary_text": "公式ロードマップを確認した。",
        }
        _ok, failures = pipeline.validate_fact_gate(
            parsed,
            "modelcontextprotocol",
            source_context="Official MCP roadmap: agentic messaging for long-running interactions and tool invocation patterns.",
            source="HackerNews",
        )
        self.assertFalse(any("unsupported numeric claim: 1リクエスト" in item for item in failures), failures)

    def test_request_tool_call_rate_or_limit_is_still_guarded(self):
        for draft in (
            "上限は1リクエスト・1ツール呼び出しである。",
            "毎秒1リクエスト・1ツール呼び出しまで処理できる。",
            "処理回数は1リクエスト。",
        ):
            failures = pipeline._find_unsupported_numeric_claims(draft, "Official docs discuss requests but state no such numeric limit.")
            self.assertTrue(any("1リクエスト" in item for item in failures), (draft, failures))

    def test_json_schema_is_generic_technical_spec_not_product_fact(self):
        draft = "ツール定義にはJSON Schemaを標準で利用する。"
        source = "The roadmap discusses tool definitions consuming model context and progressive discovery."
        failures = pipeline._find_source_boundary_violations(draft, source, repo_name="modelcontextprotocol")
        self.assertFalse(any("JSON Schema" in item for item in failures), failures)

    def test_generic_descriptor_does_not_whitelist_unknown_vendor_product(self):
        draft = "Acme Schemaを標準で採用する。"
        source = "The roadmap discusses tool definitions and progressive discovery."
        failures = pipeline._find_source_boundary_violations(draft, source, repo_name="modelcontextprotocol")
        self.assertTrue(any("Acme Schema" in item for item in failures), failures)

    def test_real_mcp_article_is_not_false_monotony_from_other_bucket(self):
        warnings = pipeline._find_humanization_violations(self.article)
        self.assertNotIn("monotonous sentence endings", warnings, warnings)

    def test_true_repeated_masu_endings_are_still_detected(self):
        draft = "".join(f"項目{i}を確認します。" for i in range(1, 10))
        warnings = pipeline._find_humanization_violations(draft)
        self.assertIn("monotonous sentence endings", warnings, warnings)

    def test_mixed_plain_form_endings_are_not_one_bucket(self):
        draft = "仕様を確認する。課題は残っている。変更は必要だ。導入条件がある。運用で試した。制約も示された。比較できる。急ぐ必要はない。"
        warnings = pipeline._find_humanization_violations(draft)
        self.assertNotIn("monotonous sentence endings", warnings, warnings)

    def test_retry_instruction_repairs_rhythm_not_only_suffix(self):
        instruction, sections = pipeline.build_dynamic_retry_instruction([
            {"reason_code": pipeline.REASON_CODE_EDITORIAL_STRUCTURE_ERROR, "message": "monotonous sentence endings", "gate": "editorial", "severity": pipeline.GATE_SEVERITY_REVIEW}
        ])
        self.assertIn("語尾だけを機械的に置換せず", instruction)
        self.assertIn("文の長短", instruction)
        self.assertIn("structure", sections)

    def test_run125_adds_no_provider_call_site(self):
        py = Path(pipeline.__file__).read_text(encoding="utf-8")
        self.assertEqual(7, py.count("_generate_via_chat("))
        self.assertEqual(1, py.count("genai.Client("))


if __name__ == "__main__":
    unittest.main()
