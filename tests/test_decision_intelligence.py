import importlib
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Minimal google-genai fallback for environments without the SDK.
try:
    importlib.import_module("google.genai")
    importlib.import_module("google.genai.errors")
except ImportError:
    google_pkg = sys.modules.get("google") or types.ModuleType("google")
    google_pkg.__path__ = getattr(google_pkg, "__path__", [])
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class _Client:
        def __init__(self, *a, **k):
            self.models = MagicMock()
    class _APIError(Exception):
        pass
    genai_mod.Client = _Client
    errors_mod.APIError = _APIError
    google_pkg.genai = genai_mod
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_mod
    sys.modules["google.genai.errors"] = errors_mod

os.environ.setdefault("SYNTHETIC_REGRESSION_MODE", "false")
import decision_intelligence as di  # noqa: E402
import pipeline  # noqa: E402
import migrate_decision_intelligence as migration  # noqa: E402


def response(status=200, data=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = data or {}
    r.text = text
    r.raise_for_status.side_effect = None if status < 400 else RuntimeError(text or f"HTTP {status}")
    return r


def tech_schema():
    return {k: {"type": v} for k, v in di.TECH_REQUIRED_PROPERTY_TYPES.items()}


def history_schema():
    return {k: {"type": v} for k, v in di.HISTORY_REQUIRED_PROPERTY_TYPES.items()}


def valid_management_text():
    return """=== MANAGEMENT DATA ===
・Source Summary: 一次情報で方式と制約を確認した。
・What: 新しい実装方式が公開された。
・Why Important: 限定環境で検証価値がある。
・技術的パラダイムシフト: 小さい。
・代替との比較: 比較根拠不足。
・移行コストとリスク: 追加検証が必要。
・Decision: TRY
・Decision Reason: 限定環境で比較する価値がある。
・Decision Score: Business Impact 15/25; Technical Impact 18/25; Urgency 8/20; Market Impact 6/15; Reliability 10/15; 合計 57/100
・Adoption Score: Evidence Quality 20/25; Production Maturity 15/25; Use-case Utility / Fit 14/20; Reliability / Security Risk 10/15; Integration / Migration Feasibility 7/10; Ecosystem / Support Durability 3/5; 合計 69/100
・Adoption Status: TEST
・Evidence Confidence: MEDIUM
・Production Readiness: MEDIUM
・Main Risk: 制約条件が限定的であり、一般化には追加検証が必要。
・Best For: 限定環境で比較検証できるチーム。
・Avoid For: 無検証で本番全面導入したい用途。
・Short Rationale: 一次情報で方式は確認できるが、本番一般化には追加検証が必要。
・Why NOT Important: 直ちに本番導入する必要はない。
・Who Should Use: 検証チーム。
・Who Should NOT Use: 即時本番投入を求めるチーム。
・Action: 限定環境で比較テストする。
・Future Scenario: 条件が整えば採用判断が進む。
・Article Value: 75
===NOTE_DRAFT_START===
これはテスト記事です。
## はじめに
一次情報に基づいて整理します。
## 先に判断を書くと。
限定環境で試す価値があります。
## なぜ今、目を向けるのか。
実務への影響があります。
## 何が起きている？
方式が公開されました。
## 要点を整理すると。
制約があります。
### 私なら今はこうする。
限定環境で比較します。
### 結局、どう見るか。
本番導入は追加検証後です。
"""


class TestSchemaPreflight(unittest.TestCase):
    def test_disabled_does_not_touch_network(self):
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", False), patch.object(di.requests, "get") as get:
            di.preflight_decision_intelligence_schema()
            get.assert_not_called()

    def test_enabled_requires_dedicated_token(self):
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_DECISION_INTELLIGENCE_API_KEY", ""), \
             patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", "tech"), \
             patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"):
            with self.assertRaisesRegex(ValueError, "NOTION_DECISION_INTELLIGENCE_API_KEY"):
                di.preflight_decision_intelligence_schema()

    def test_headers_use_dedicated_token_not_internal_token(self):
        with patch.object(di, "NOTION_DECISION_INTELLIGENCE_API_KEY", "decision-token"):
            self.assertEqual("Bearer decision-token", di._headers()["Authorization"])

    def test_enabled_requires_both_databases(self):
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_DECISION_INTELLIGENCE_API_KEY", "x"), \
             patch.object(di, "NOTION_TECH_DATABASE_ID", ""), patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", ""):
            with self.assertRaises(ValueError):
                di.preflight_decision_intelligence_schema()

    def test_complete_schema_passes(self):
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_DECISION_INTELLIGENCE_API_KEY", "x"), \
             patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", "tech"), \
             patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"), \
             patch.object(di.requests, "get", side_effect=[
                 response(data={"properties": tech_schema()}), response(data={"properties": history_schema()})
             ]):
            di.preflight_decision_intelligence_schema()

    def test_schema_type_mismatch_fails(self):
        bad = tech_schema()
        bad[di.TECH_PROP_ADOPTION_SCORE] = {"type": "rich_text"}
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_DECISION_INTELLIGENCE_API_KEY", "x"), \
             patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", "tech"), \
             patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"), \
             patch.object(di.requests, "get", side_effect=[
                 response(data={"properties": bad}), response(data={"properties": history_schema()})
             ]):
            with self.assertRaises(ValueError):
                di.preflight_decision_intelligence_schema()


class TestEntityResolution(unittest.TestCase):
    def test_github_cross_source_resolves_same_entity(self):
        direct = di.resolve_canonical_entity_id({
            "source": "GitHub", "nameWithOwner": "OpenAI/example", "url": "https://github.com/OpenAI/example"
        })
        hn = di.resolve_canonical_entity_id({
            "source": "HackerNews", "nameWithOwner": "Example", "url": "https://github.com/openai/example?utm_source=hn",
            "sourceDetails": {"hn_url": "https://news.ycombinator.com/item?id=1"},
        })
        self.assertEqual("github:openai/example", direct.entity_id)
        self.assertEqual(direct.entity_id, hn.entity_id)

    def test_arxiv_versions_and_pdf_resolve_same_entity(self):
        a = di.resolve_canonical_entity_id({"source": "ArXiv", "nameWithOwner": "Paper", "url": "https://arxiv.org/abs/2608.12345v1"})
        b = di.resolve_canonical_entity_id({"source": "ArXiv", "nameWithOwner": "Paper", "url": "https://arxiv.org/pdf/2608.12345v3.pdf"})
        self.assertEqual("arxiv:2608.12345", a.entity_id)
        self.assertEqual(a.entity_id, b.entity_id)

    def test_same_title_different_urls_are_not_fuzzy_merged(self):
        a = di.resolve_canonical_entity_id({"source": "HackerNews", "nameWithOwner": "Same title", "url": "https://example.com/project-a"})
        b = di.resolve_canonical_entity_id({"source": "HackerNews", "nameWithOwner": "Same title", "url": "https://example.org/project-b"})
        self.assertNotEqual(a.entity_id, b.entity_id)

    def test_discovery_only_url_is_ambiguous(self):
        r = di.resolve_canonical_entity_id({"source": "HackerNews", "nameWithOwner": "Unknown", "url": "https://news.ycombinator.com/item?id=123"})
        self.assertEqual("AMBIGUOUS", r.status)
        self.assertTrue(r.entity_id.startswith("legacy:"))

    def test_generic_article_url_is_ambiguous_not_technology_identity(self):
        r = di.resolve_canonical_entity_id({
            "source": "HackerNews",
            "nameWithOwner": "Mojo is now open source",
            "url": "https://www.modular.com/blog/mojo-open-source",
        })
        self.assertEqual("AMBIGUOUS", r.status)
        self.assertTrue(r.entity_id.startswith("legacy:"))

    def test_root_project_url_can_be_resolved(self):
        r = di.resolve_canonical_entity_id({
            "source": "HackerNews",
            "nameWithOwner": "OpenLogi",
            "url": "https://openlogi.org/en",
        })
        self.assertEqual("RESOLVED", r.status)
        self.assertEqual("web:openlogi.org/", r.entity_id)


class TestPromptAndParser(unittest.TestCase):
    def test_prompt_contains_adoption_fields_without_extra_call(self):
        prompt = pipeline.build_decision_prompt("x", "https://example.com", 0, "desc")
        for label in ("Adoption Score", "Adoption Status", "Evidence Confidence", "Production Readiness", "Main Risk", "Best For", "Avoid For"):
            self.assertIn(label, prompt)

    def test_parser_keeps_decision_and_adoption_scores_separate(self):
        parsed = pipeline._parse_gemini_response(valid_management_text())
        self.assertEqual(57, parsed["score"])
        self.assertEqual(69, parsed["adoption_score"])
        self.assertEqual("TEST", parsed["adoption_status"])
        self.assertEqual("MEDIUM", parsed["evidence_confidence"])
        self.assertEqual("MEDIUM", parsed["production_readiness"])

    def test_missing_adoption_score_is_not_backfilled_from_decision_score(self):
        parsed = pipeline._parse_gemini_response(valid_management_text().replace("・Adoption Score:", "・Legacy Adoption Score:"))
        self.assertEqual(57, parsed["score"])
        self.assertEqual(0, parsed["adoption_score"])

    def test_article_gate_detects_adoption_management_leak(self):
        leaks = pipeline._find_management_score_leak("Adoption Status: ADOPT")
        self.assertTrue(any("decision intelligence" in x for x in leaks))


class TestAssessmentValidation(unittest.TestCase):
    def setUp(self):
        self.parsed = pipeline._parse_gemini_response(valid_management_text())
        self.evidence = {"state": pipeline.EVIDENCE_SUFFICIENT, "decision_scope_safe": True}

    def test_valid_assessment_passes(self):
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True):
            ok, failures = pipeline.validate_decision_intelligence_assessment(
                self.parsed, self.evidence,
                "一次情報では方式と制約条件が説明され、限定環境での検証が必要と記載されている。",
                {},
            )
        self.assertTrue(ok, failures)

    def test_adopt_requires_high_evidence_and_high_readiness(self):
        parsed = dict(self.parsed)
        parsed.update({"adoption_status": "ADOPT", "evidence_confidence": "MEDIUM", "production_readiness": "HIGH"})
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True):
            ok, failures = pipeline.validate_decision_intelligence_assessment(parsed, self.evidence, "一次情報", {})
        self.assertFalse(ok)
        self.assertTrue(any("ADOPT requires" in x for x in failures))

    def test_component_total_mismatch_fails(self):
        parsed = dict(self.parsed)
        parsed["adoption_score"] = 70
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True):
            ok, failures = pipeline.validate_decision_intelligence_assessment(parsed, self.evidence, "一次情報", {})
        self.assertFalse(ok)
        self.assertTrue(any("total mismatch" in x for x in failures))


class TestTechnologyUpsert(unittest.TestCase):
    def assessment(self):
        return {
            "technology_name": "Example",
            "sources": ["GitHub"], "category": "DEVTOOLS",
            "adoption_score": 70, "adoption_status": "TEST",
            "evidence_confidence": "MEDIUM", "production_readiness": "MEDIUM",
            "main_risk": "追加検証が必要", "best_for": "限定検証", "avoid_for": "無検証本番",
            "short_rationale": "一次情報で方式を確認", "reviewed_at": "2026-08-21T10:00:00+09:00",
            "evidence_urls": ["https://github.com/acme/example"], "source_summary": "summary",
            "tracking_eligibility": True, "assessment_state": "ASSESSED",
        }

    def resolution(self):
        return di.EntityResolution("github:acme/example", "RESOLVED", "https://github.com/acme/example", ("https://github.com/acme/example",), "test")

    def test_new_entity_creates_current_then_initial_history(self):
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", "tech"), patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"), \
             patch.object(di.requests, "post", side_effect=[
                 response(data={"results": []}),
                 response(data={"id": "tech-page"}),
                 response(data={"results": []}),
                 response(data={"id": "history-page"}),
             ]) as post, \
             patch.object(di.requests, "patch", return_value=response(data={"id": "tech-page"})):
            result = di.upsert_technology_intelligence(self.assessment(), self.resolution())
        self.assertTrue(result["created"])
        self.assertEqual("history-page", result["history_id"])
        self.assertEqual(4, post.call_count)

    def test_existing_change_appends_history_before_patch(self):
        existing = {"id": "tech-page", "properties": {
            di.TECH_PROP_ADOPTION_SCORE: {"number": 60},
            di.TECH_PROP_ADOPTION_STATUS: {"select": {"name": "WATCH"}},
            di.TECH_PROP_PRODUCTION_READINESS: {"select": {"name": "MEDIUM"}},
            di.TECH_PROP_EVIDENCE_CONFIDENCE: {"select": {"name": "MEDIUM"}},
            di.TECH_PROP_MAIN_RISK: {"rich_text": [{"plain_text": "old"}]},
            di.TECH_PROP_EVIDENCE_URLS: {"rich_text": []},
            di.TECH_PROP_FIRST_SEEN: {"date": {"start": "2026-08-01T00:00:00+09:00"}},
        }}
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", "tech"), patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"), \
             patch.object(di.requests, "post", side_effect=[
                 response(data={"results": [existing]}), response(data={"results": []}), response(data={"id": "history-page"}),
             ]) as post, patch.object(di.requests, "patch", return_value=response(data={"id": "tech-page"})) as patch_req:
            result = di.upsert_technology_intelligence(self.assessment(), self.resolution())
        self.assertFalse(result["created"])
        self.assertTrue(result["changed"])
        self.assertEqual("history-page", result["history_id"])
        self.assertEqual(3, post.call_count)
        payload = patch_req.call_args.kwargs["json"]["properties"]
        self.assertEqual("2026-08-01T00:00:00+09:00", payload[di.TECH_PROP_FIRST_SEEN]["date"]["start"])
        self.assertEqual(60, payload[di.TECH_PROP_PREVIOUS_SCORE]["number"])
        self.assertEqual(10, payload[di.TECH_PROP_SCORE_CHANGE]["number"])

    def test_no_meaningful_change_does_not_append_history(self):
        existing = {"id": "tech-page", "properties": {
            di.TECH_PROP_ADOPTION_SCORE: {"number": 70},
            di.TECH_PROP_ADOPTION_STATUS: {"select": {"name": "TEST"}},
            di.TECH_PROP_PRODUCTION_READINESS: {"select": {"name": "MEDIUM"}},
            di.TECH_PROP_EVIDENCE_CONFIDENCE: {"select": {"name": "MEDIUM"}},
            di.TECH_PROP_MAIN_RISK: {"rich_text": [{"plain_text": "追加検証が必要"}]},
            di.TECH_PROP_EVIDENCE_URLS: {"rich_text": [{"plain_text": "https://github.com/acme/example"}]},
            di.TECH_PROP_FIRST_SEEN: {"date": {"start": "2026-08-01T00:00:00+09:00"}},
        }}
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", "tech"), patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"), \
             patch.object(di.requests, "post", return_value=response(data={"results": [existing]})) as post, \
             patch.object(di.requests, "patch", return_value=response(data={"id": "tech-page"})):
            result = di.upsert_technology_intelligence(self.assessment(), self.resolution())
        self.assertFalse(result["changed"])
        self.assertEqual("", result["history_id"])
        self.assertEqual(1, post.call_count)

    def test_patch_failure_never_deletes_existing_record(self):
        existing = {"id": "tech-page", "properties": {
            di.TECH_PROP_ADOPTION_SCORE: {"number": 60},
            di.TECH_PROP_ADOPTION_STATUS: {"select": {"name": "WATCH"}},
            di.TECH_PROP_PRODUCTION_READINESS: {"select": {"name": "LOW"}},
            di.TECH_PROP_EVIDENCE_CONFIDENCE: {"select": {"name": "MEDIUM"}},
            di.TECH_PROP_MAIN_RISK: {"rich_text": [{"plain_text": "old"}]},
            di.TECH_PROP_EVIDENCE_URLS: {"rich_text": []},
        }}
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", "tech"), patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"), \
             patch.object(di.requests, "post", side_effect=[response(data={"results": [existing]}), response(data={"results": []}), response(data={"id": "history"})]), \
             patch.object(di.requests, "patch", return_value=response(status=500, text="fail")), \
             patch.object(di.requests, "delete") as delete:
            with self.assertRaises(RuntimeError):
                di.upsert_technology_intelligence(self.assessment(), self.resolution())
            delete.assert_not_called()

    def test_reassessment_accumulates_sources_aliases_and_evidence(self):
        existing = {"id": "tech-page", "properties": {
            di.TECH_PROP_ADOPTION_SCORE: {"number": 60},
            di.TECH_PROP_ADOPTION_STATUS: {"select": {"name": "WATCH"}},
            di.TECH_PROP_PRODUCTION_READINESS: {"select": {"name": "LOW"}},
            di.TECH_PROP_EVIDENCE_CONFIDENCE: {"select": {"name": "MEDIUM"}},
            di.TECH_PROP_MAIN_RISK: {"rich_text": [{"plain_text": "old"}]},
            di.TECH_PROP_SOURCE: {"multi_select": [{"name": "HackerNews"}]},
            di.TECH_PROP_ENTITY_ALIASES: {"rich_text": [{"plain_text": "https://example.com/old"}]},
            di.TECH_PROP_EVIDENCE_URLS: {"rich_text": [{"plain_text": "https://example.com/evidence-old"}]},
            di.TECH_PROP_FIRST_SEEN: {"date": {"start": "2026-08-01T00:00:00+09:00"}},
        }}
        assessment = self.assessment()
        assessment["sources"] = ["GitHub"]
        assessment["evidence_urls"] = ["https://example.com/evidence-new"]
        resolution = di.EntityResolution(
            "github:acme/example", "RESOLVED", "https://github.com/acme/example",
            ("https://github.com/acme/example",), "test"
        )
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", "tech"), patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"), \
             patch.object(di.requests, "post", side_effect=[response(data={"results": [existing]}), response(data={"results": []}), response(data={"id": "history"})]), \
             patch.object(di.requests, "patch", return_value=response(data={"id": "tech-page"})) as patch_req:
            di.upsert_technology_intelligence(assessment, resolution)
        props = patch_req.call_args.kwargs["json"]["properties"]
        source_names = [x["name"] for x in props[di.TECH_PROP_SOURCE]["multi_select"]]
        self.assertEqual(["HackerNews", "GitHub"], source_names)
        aliases = props[di.TECH_PROP_ENTITY_ALIASES]["rich_text"][0]["text"]["content"].splitlines()
        self.assertEqual(["https://example.com/old", "https://github.com/acme/example"], aliases)
        evidence = props[di.TECH_PROP_EVIDENCE_URLS]["rich_text"][0]["text"]["content"].splitlines()
        self.assertEqual(["https://example.com/evidence-old", "https://example.com/evidence-new"], evidence)

    def test_existing_change_reuses_same_history_event_after_patch_failure(self):
        existing = {"id": "tech-page", "properties": {
            di.TECH_PROP_ADOPTION_SCORE: {"number": 60},
            di.TECH_PROP_ADOPTION_STATUS: {"select": {"name": "WATCH"}},
            di.TECH_PROP_PRODUCTION_READINESS: {"select": {"name": "LOW"}},
            di.TECH_PROP_EVIDENCE_CONFIDENCE: {"select": {"name": "MEDIUM"}},
            di.TECH_PROP_MAIN_RISK: {"rich_text": [{"plain_text": "old"}]},
            di.TECH_PROP_EVIDENCE_URLS: {"rich_text": []},
        }}
        existing_history = {"id": "history-existing", "properties": {}}
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", "tech"), patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"), \
             patch.object(di.requests, "post", side_effect=[
                 response(data={"results": [existing]}), response(data={"results": [existing_history]}),
             ]) as post, \
             patch.object(di.requests, "patch", return_value=response(data={"id": "tech-page"})):
            result = di.upsert_technology_intelligence(self.assessment(), self.resolution())
        self.assertEqual("history-existing", result["history_id"])
        self.assertEqual(2, post.call_count)
        self.assertTrue(result["changed"])

    def test_repeated_same_transition_after_later_change_gets_new_event_id(self):
        assessment = self.assessment()
        assessment["canonical_entity_id"] = self.resolution().entity_id
        base = {
            "previous_score": 60, "score_delta": 10, "previous_status": "WATCH",
            "status_changed": True, "change_reason": "score/status changed", "evidence_added": [],
        }
        first = dict(base, previous_change_at="2026-08-01T00:00:00+09:00")
        later = dict(base, previous_change_at="2026-09-01T00:00:00+09:00")
        retry = dict(base, previous_change_at="2026-08-01T00:00:00+09:00")
        self.assertEqual(
            di._history_event_id(assessment, first, "CHANGE"),
            di._history_event_id(assessment, retry, "CHANGE"),
        )
        self.assertNotEqual(
            di._history_event_id(assessment, first, "CHANGE"),
            di._history_event_id(assessment, later, "CHANGE"),
        )

    def test_history_event_collision_fails_closed(self):
        assessment = self.assessment()
        assessment["canonical_entity_id"] = self.resolution().entity_id
        diff = {
            "previous_score": 60, "score_delta": 10, "previous_status": "WATCH",
            "status_changed": True, "change_reason": "score/status changed", "evidence_added": [],
        }
        with patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"), \
             patch.object(di.requests, "post", return_value=response(data={"results": [{"id": "a"}, {"id": "b"}]})):
            with self.assertRaises(RuntimeError):
                di._append_history("tech-page", assessment, diff, "CHANGE")

    def test_history_pending_current_recovers_initial_history_idempotently(self):
        existing = {"id": "tech-page", "properties": {
            di.TECH_PROP_ADOPTION_SCORE: {"number": 70},
            di.TECH_PROP_ADOPTION_STATUS: {"select": {"name": "TEST"}},
            di.TECH_PROP_PRODUCTION_READINESS: {"select": {"name": "MEDIUM"}},
            di.TECH_PROP_EVIDENCE_CONFIDENCE: {"select": {"name": "MEDIUM"}},
            di.TECH_PROP_MAIN_RISK: {"rich_text": [{"plain_text": "追加検証が必要"}]},
            di.TECH_PROP_EVIDENCE_URLS: {"rich_text": [{"plain_text": "https://github.com/acme/example"}]},
            di.TECH_PROP_ASSESSMENT_STATE: {"select": {"name": "HISTORY_PENDING"}},
        }}
        history = {"id": "history-initial"}
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", "tech"), patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"), \
             patch.object(di.requests, "post", side_effect=[
                 response(data={"results": [existing]}), response(data={"results": [history]}),
             ]), \
             patch.object(di.requests, "patch", return_value=response(data={"id": "tech-page"})) as patch_req:
            result = di.upsert_technology_intelligence(self.assessment(), self.resolution())
        self.assertTrue(result["history_recovered"])
        self.assertEqual("history-initial", result["history_id"])
        payload = patch_req.call_args.kwargs["json"]["properties"]
        self.assertEqual("ASSESSED", payload[di.TECH_PROP_ASSESSMENT_STATE]["select"]["name"])
        self.assertIsNone(payload[di.TECH_PROP_PREVIOUS_SCORE]["number"])
        self.assertIsNone(payload[di.TECH_PROP_SCORE_CHANGE]["number"])

    def test_history_pending_with_new_assessment_recovers_initial_then_appends_change(self):
        existing = {"id": "tech-page", "properties": {
            di.TECH_PROP_NAME: {"title": [{"plain_text": "Example"}]},
            di.TECH_PROP_ADOPTION_SCORE: {"number": 60},
            di.TECH_PROP_ADOPTION_STATUS: {"select": {"name": "WATCH"}},
            di.TECH_PROP_PRODUCTION_READINESS: {"select": {"name": "LOW"}},
            di.TECH_PROP_EVIDENCE_CONFIDENCE: {"select": {"name": "MEDIUM"}},
            di.TECH_PROP_MAIN_RISK: {"rich_text": [{"plain_text": "old risk"}]},
            di.TECH_PROP_EVIDENCE_URLS: {"rich_text": [{"plain_text": "https://github.com/acme/example"}]},
            di.TECH_PROP_LAST_REVIEWED: {"date": {"start": "2026-08-20T10:00:00+09:00"}},
            di.TECH_PROP_LAST_CHANGE_AT: {"date": {"start": "2026-08-20T10:00:00+09:00"}},
            di.TECH_PROP_ASSESSMENT_STATE: {"select": {"name": "HISTORY_PENDING"}},
        }}
        new_assessment = self.assessment()
        # New run has moved from pending initial WATCH/60 to TEST/70.
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "NOTION_TECH_DATA_SOURCE_ID", "tech"), patch.object(di, "NOTION_HISTORY_DATA_SOURCE_ID", "hist"), \
             patch.object(di.requests, "post", side_effect=[
                 response(data={"results": [existing]}),   # current entity query
                 response(data={"results": [{"id": "history-initial"}]}),  # recover INITIAL
                 response(data={"results": []}),          # CHANGE event lookup
                 response(data={"id": "history-change"}), # CHANGE append
             ]) as post, \
             patch.object(di.requests, "patch", return_value=response(data={"id": "tech-page"})) as patch_req:
            result = di.upsert_technology_intelligence(new_assessment, self.resolution())
        self.assertTrue(result["history_recovered"])
        self.assertEqual(["history-initial", "history-change"], result["history_ids"])
        self.assertEqual("history-change", result["history_id"])
        self.assertEqual(4, post.call_count)
        payload = patch_req.call_args.kwargs["json"]["properties"]
        self.assertEqual(60, payload[di.TECH_PROP_PREVIOUS_SCORE]["number"])
        self.assertEqual(10, payload[di.TECH_PROP_SCORE_CHANGE]["number"])
        self.assertEqual("ASSESSED", payload[di.TECH_PROP_ASSESSMENT_STATE]["select"]["name"])

    def test_legacy_seed_does_not_invent_adoption_fields(self):
        props = di.build_legacy_seed_properties(
            {"name": "Legacy", "source": "GitHub", "url": "https://github.com/acme/example", "screening_score": 95},
            self.resolution(), "2026-08-21T00:00:00Z",
        )
        self.assertNotIn(di.TECH_PROP_ADOPTION_SCORE, props)
        self.assertNotIn(di.TECH_PROP_ADOPTION_STATUS, props)
        self.assertEqual("LEGACY_PENDING", props[di.TECH_PROP_ASSESSMENT_STATE]["select"]["name"])


class TestMigrationTokenIsolation(unittest.TestCase):
    def test_internal_reader_headers_use_legacy_notion_api_key(self):
        with patch.object(migration, "NOTION_API_KEY", "internal-token"):
            self.assertEqual("Bearer internal-token", migration._headers()["Authorization"])

    def test_target_writer_headers_use_decision_intelligence_key(self):
        with patch.object(di, "NOTION_DECISION_INTELLIGENCE_API_KEY", "decision-token"):
            self.assertEqual("Bearer decision-token", di._headers()["Authorization"])


class TestLegacyMigrationSafety(unittest.TestCase):
    def test_exact_entity_rows_merge_without_adoption_invention(self):
        resolution_a = di.EntityResolution(
            "github:acme/example", "RESOLVED", "https://github.com/acme/example",
            ("https://github.com/acme/example", "https://example.com/old"), "test"
        )
        resolution_b = di.EntityResolution(
            "github:acme/example", "RESOLVED", "https://github.com/acme/example",
            ("https://github.com/acme/example", "https://example.com/new"), "test"
        )
        rows = [
            ({"name": "Example", "sources": ["HackerNews"], "evidence_urls": ["https://evidence/1"],
              "first_seen": "2026-08-01T00:00:00Z", "analyzed_at": "2026-08-02T00:00:00Z"}, resolution_a),
            ({"name": "Example", "sources": ["GitHub"], "evidence_urls": ["https://evidence/2"],
              "first_seen": "2026-08-03T00:00:00Z", "analyzed_at": "2026-08-04T00:00:00Z"}, resolution_b),
        ]
        merged = migration._merge_seed_rows(rows)
        self.assertEqual(1, len(merged))
        seed, resolution = merged[0]
        self.assertEqual(["HackerNews", "GitHub"], seed["sources"])
        self.assertEqual(["https://evidence/1", "https://evidence/2"], seed["evidence_urls"])
        self.assertEqual("2026-08-01T00:00:00Z", seed["first_seen"])
        self.assertIn("https://example.com/old", resolution.aliases)
        self.assertIn("https://example.com/new", resolution.aliases)
        props = di.build_legacy_seed_properties(seed, resolution, "2026-08-21T00:00:00Z")
        self.assertNotIn(di.TECH_PROP_ADOPTION_SCORE, props)
        self.assertNotIn(di.TECH_PROP_ADOPTION_STATUS, props)
        self.assertEqual("LEGACY_PENDING", props[di.TECH_PROP_ASSESSMENT_STATE]["select"]["name"])

    def test_ambiguous_rows_do_not_fuzzy_merge_by_title(self):
        a = ({"name": "Same Name", "sources": ["HackerNews"], "evidence_urls": []},
             di.EntityResolution("legacy:a", "AMBIGUOUS", "", (), "test"))
        b = ({"name": "Same Name", "sources": ["ProductHunt"], "evidence_urls": []},
             di.EntityResolution("legacy:b", "AMBIGUOUS", "", (), "test"))
        merged = migration._merge_seed_rows([a, b])
        self.assertEqual(2, len(merged))

    def test_identical_same_source_ambiguous_urls_merge_but_remain_ambiguous(self):
        base_resolution = di.EntityResolution(
            "legacy:same", "AMBIGUOUS", "https://example.com/article/?utm_source=x#frag",
            ("https://example.com/article",), "test"
        )
        a = ({"internal_page_id": "page-a", "name": "Same", "source": "HackerNews",
              "sources": ["HackerNews"], "evidence_urls": [], "first_seen": "2026-08-01T00:00:00Z"}, base_resolution)
        b = ({"internal_page_id": "page-b", "name": "Same", "source": "HackerNews",
              "sources": ["HackerNews"], "evidence_urls": [], "first_seen": "2026-08-02T00:00:00Z"}, base_resolution)
        merged = migration._merge_seed_rows([a, b])
        self.assertEqual(1, len(merged))
        seed, resolution = merged[0]
        self.assertEqual("AMBIGUOUS", resolution.status)
        self.assertTrue(resolution.entity_id.startswith("legacy:"))
        self.assertEqual("https://example.com/article", resolution.primary_url)
        self.assertEqual(2, seed["legacy_rows_merged"])
        self.assertEqual("2026-08-01T00:00:00Z", seed["first_seen"])

    def test_same_ambiguous_url_different_sources_do_not_merge(self):
        resolution = di.EntityResolution(
            "legacy:same", "AMBIGUOUS", "https://example.com/article",
            ("https://example.com/article",), "test"
        )
        a = ({"internal_page_id": "page-a", "name": "Same", "source": "HackerNews",
              "sources": ["HackerNews"], "evidence_urls": []}, resolution)
        b = ({"internal_page_id": "page-b", "name": "Same", "source": "ProductHunt",
              "sources": ["ProductHunt"], "evidence_urls": []}, resolution)
        merged = migration._merge_seed_rows([a, b])
        self.assertEqual(2, len(merged))
        self.assertNotEqual(merged[0][1].entity_id, merged[1][1].entity_id)

    def test_ambiguous_urls_with_meaningful_query_difference_do_not_merge(self):
        a_resolution = di.EntityResolution(
            "legacy:a", "AMBIGUOUS", "https://example.com/article?version=1",
            ("https://example.com/article?version=1",), "test"
        )
        b_resolution = di.EntityResolution(
            "legacy:b", "AMBIGUOUS", "https://example.com/article?version=2",
            ("https://example.com/article?version=2",), "test"
        )
        a = ({"internal_page_id": "page-a", "name": "Same", "source": "HackerNews",
              "sources": ["HackerNews"], "evidence_urls": []}, a_resolution)
        b = ({"internal_page_id": "page-b", "name": "Same", "source": "HackerNews",
              "sources": ["HackerNews"], "evidence_urls": []}, b_resolution)
        merged = migration._merge_seed_rows([a, b])
        self.assertEqual(2, len(merged))

    def test_ambiguous_exact_url_group_entity_id_is_order_independent(self):
        resolution = di.EntityResolution(
            "legacy:same", "AMBIGUOUS", "https://www.producthunt.com/r/ABC123",
            ("https://www.producthunt.com/r/ABC123",), "test"
        )
        a = ({"internal_page_id": "page-a", "name": "Same", "source": "ProductHunt",
              "sources": ["ProductHunt"], "evidence_urls": []}, resolution)
        b = ({"internal_page_id": "page-b", "name": "Same", "source": "ProductHunt",
              "sources": ["ProductHunt"], "evidence_urls": []}, resolution)
        first = migration._merge_seed_rows([a, b])
        second = migration._merge_seed_rows([b, a])
        self.assertEqual(1, len(first))
        self.assertEqual(1, len(second))
        self.assertEqual(first[0][1].entity_id, second[0][1].entity_id)

    def test_blank_ambiguous_urls_remain_page_scoped(self):
        resolution = di.EntityResolution("legacy:same", "AMBIGUOUS", "", (), "test")
        a = ({"internal_page_id": "page-a", "name": "Same", "source": "Unknown",
              "sources": ["Unknown"], "evidence_urls": []}, resolution)
        b = ({"internal_page_id": "page-b", "name": "Same", "source": "Unknown",
              "sources": ["Unknown"], "evidence_urls": []}, resolution)
        merged = migration._merge_seed_rows([a, b])
        self.assertEqual(2, len(merged))
        self.assertNotEqual(merged[0][1].entity_id, merged[1][1].entity_id)

    def test_legacy_seed_is_paused_and_not_tracking_eligible_until_reassessment(self):
        seed = {"name": "Legacy", "sources": ["HackerNews"], "evidence_urls": [], "first_seen": "2026-08-01T00:00:00Z"}
        resolution = di.EntityResolution("legacy:x", "AMBIGUOUS", "", (), "test")
        props = di.build_legacy_seed_properties(seed, resolution, "2026-08-21T00:00:00Z")
        self.assertEqual("PAUSED", props[di.TECH_PROP_TRACKING_STATUS]["select"]["name"])
        self.assertFalse(props[di.TECH_PROP_TRACKING_ELIGIBILITY]["checkbox"])
        self.assertEqual("LEGACY_PENDING", props[di.TECH_PROP_ASSESSMENT_STATE]["select"]["name"])
        self.assertNotIn(di.TECH_PROP_ADOPTION_SCORE, props)
        self.assertNotIn(di.TECH_PROP_ADOPTION_STATUS, props)


class TestProductSidePathIsolation(unittest.TestCase):
    def test_persistence_failure_is_caught_and_returned(self):
        parsed = pipeline._parse_gemini_response(valid_management_text())
        source_info = {
            "verification_context": "一次情報では方式と制約条件が説明されている。",
            "context": "一次情報では方式と制約条件が説明されている。",
            "evidence_metadata": {}, "primary_url": "https://example.com",
            "evidence_documents": [{"url": "https://example.com", "retrieved": True}],
        }
        evidence = {"state": pipeline.EVIDENCE_SUFFICIENT, "decision_scope_safe": True}
        repo = {"source": "HackerNews", "nameWithOwner": "Example", "url": "https://example.com", "publishedAt": None}
        with patch.object(di, "ENABLE_DECISION_INTELLIGENCE_DB", True), \
             patch.object(di, "upsert_technology_intelligence", side_effect=RuntimeError("Notion down")):
            result = pipeline.persist_decision_intelligence_assessment(
                repo, parsed, source_info, evidence, "2026-08-21T10:00:00+09:00"
            )
        self.assertFalse(result["saved"])
        self.assertEqual("persistence_failed", result["reason"])


if __name__ == "__main__":
    unittest.main()
