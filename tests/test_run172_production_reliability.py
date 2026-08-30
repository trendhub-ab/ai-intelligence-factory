import contextlib
import inspect
import types
import unittest
from unittest.mock import MagicMock

import reader_value_review_bridge
import run172_production_reliability as run172


class FakeAPIError(Exception):
    def __init__(self, code):
        super().__init__(f"HTTP {code}")
        self.code = code


class FakeBudget:
    def can_request(self):
        return True

    def summary(self):
        return "ok"


def fake_pipeline(**overrides):
    ns = types.SimpleNamespace(
        build_notion_properties=lambda *a, **k: {},
        prepare_source_context=lambda repo: {
            "context": "generic documentation",
            "verification_context": "generic documentation",
            "primary_url": repo.get("primaryUrl", ""),
            "primary_source_resolved": True,
            "primary_fetch_failed": False,
            "checked_urls": set(),
            "deep_source_urls": [],
            "supplement_candidates": [],
            "evidence_supplement_attempted": False,
        },
        assess_evidence_sufficiency=lambda info: {
            "state": "SUFFICIENT",
            "sufficiency": "SUFFICIENT",
            "decision_scope_safe": True,
            "blocking_missing": [],
        },
        _parse_gemini_response=lambda text: {},
        build_decision_prompt=lambda *a, **k: str(k.get("source_context") or ""),
        build_dynamic_retry_instruction=lambda rows: ("base repair", {"article"}),
        human_appeal_materially_degraded=lambda before, after: False,
        publication_probability_score=lambda item: 50,
        PROP_EYECATCH="アイキャッチ",
        _normalize_decision=lambda x: x.strip().upper(),
        VERIFICATION_CONTEXT_MAX_CHARS=180000,
        EVIDENCE_SUPPLEMENT_REQUIRED="SUPPLEMENT_REQUIRED",
        EVIDENCE_INSUFFICIENT="INSUFFICIENT",
        GH_PAT="",
        requests=types.SimpleNamespace(get=MagicMock()),
        logger=MagicMock(),
        SESSION_EXHAUSTED_MODELS=set(),
        SESSION_UNAVAILABLE_MODELS=set(),
        GEMINI_DEEP_DIVE_CALL_PACING_SECONDS=0,
        GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS=1,
        GEMINI_SCREENING_CALL_TIMEOUT_SECONDS=1,
        _gemini_call_timeout=lambda seconds: contextlib.nullcontext(),
        _generate_via_chat=lambda *a, **k: "ok",
        APIError=FakeAPIError,
        classify_gemini_quota_error=lambda exc: "",
        _mark_model_exhausted=lambda model, why: ns.SESSION_EXHAUSTED_MODELS.add(model),
        _mark_model_unavailable=lambda model, why: ns.SESSION_UNAVAILABLE_MODELS.add(model),
        _extract_retry_delay=lambda exc, default: 0,
        GeminiBudgetExceededError=type("GeminiBudgetExceededError", (Exception,), {}),
        GeminiCallTimeoutError=type("GeminiCallTimeoutError", (Exception,), {}),
        _is_gemini_transport_timeout=lambda exc: False,
        NoAvailableModelError=type("NoAvailableModelError", (Exception,), {}),
        PRODUCT_REVIEW_REQUEST_BUDGET=FakeBudget(),
        ProductReviewBudgetExceededError=type("ProductReviewBudgetExceededError", (Exception,), {}),
        DEEP_DIVE_MODEL_POOL=["m1", "m2"],
        _PRODUCT_REVIEW_RESPONSE_SCHEMA={"type": "object"},
        SECTION_SPLIT_TOKEN="===NOTE_DRAFT_START===",
    )
    for key, value in overrides.items():
        setattr(ns, key, value)
    return ns


class Run172ProductionReliabilityTests(unittest.TestCase):
    def test_notion_filename_is_deterministic_and_below_hard_limit(self):
        title = "Difference-in-Differences on a Censored Rating Scale Can Manufacture an Effect: Evidence from a Pre-Registered LLM-Judge Audit"
        a = run172.safe_notion_file_name(title)
        b = run172.safe_notion_file_name(title)
        self.assertEqual(a, b)
        self.assertLessEqual(len(a), 96)
        self.assertTrue(a.endswith(".png"))
        self.assertRegex(a, r"__[0-9a-f]{10}\.png$")

    def test_notion_property_wrapper_reproduces_and_fixes_run106_130_char_failure(self):
        long_name = "x" * 126 + ".png"
        url = "https://raw.example/eyecatch.png"
        p = fake_pipeline(
            build_notion_properties=lambda *a, **k: {
                "アイキャッチ": {"files": [{"name": long_name, "external": {"url": url}}]}
            }
        )
        run172.install(p)
        props = p.build_notion_properties()
        item = props["アイキャッチ"]["files"][0]
        self.assertLessEqual(len(item["name"]), 100)
        self.assertEqual(url, item["external"]["url"])

    def test_core_claim_gate_catches_run106_codex_headline_against_generic_docs(self):
        title = "Codex on AWS bedrock bug causing 10x charges"
        gaps = run172._material_claim_gaps(title, "Codex CLI documentation and configuration reference")
        self.assertTrue(any(x.startswith("material_numeric:10x") for x in gaps), gaps)
        self.assertTrue(any(x.startswith("event_claim:") for x in gaps), gaps)

    def test_exact_issue_without_10x_does_not_launder_unsupported_10x_claim(self):
        title = "Codex on AWS bedrock bug causing 10x charges"
        issue = (
            "Native Codex CLI requests to Amazon Bedrock produced materially higher cost. "
            "Estimated total cost was $1,386.46 and cache writes were about 85% of estimated spend. "
            "These are usage-derived estimates, not finalized AWS invoice amounts."
        )
        gaps = run172._material_claim_gaps(title, issue)
        self.assertTrue(any(x.startswith("material_numeric:10x") for x in gaps), gaps)

    def test_non_material_editorial_number_is_not_false_positive(self):
        self.assertEqual([], run172._material_claim_gaps(
            "3 ways to make RAG easier to understand",
            "This document explains RAG and retrieval augmented generation.",
        ))

    def test_github_issue_body_is_added_as_report_evidence_not_confirmation(self):
        issue_url = "https://github.com/openai/codex/issues/37674"
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "title": "Native Bedrock Codex lacks explicit cache controls",
            "body": "Amazon Bedrock usage produced materially higher cost. These are usage-derived estimates.",
            "state": "closed",
            "user": {"login": "reporter"},
        }
        p = fake_pipeline()
        p.requests.get.return_value = response
        run172.install(p)
        info = p.prepare_source_context({
            "nameWithOwner": "Codex on AWS bedrock bug causing 10x charges",
            "primaryUrl": issue_url,
            "url": issue_url,
        })
        self.assertIn("GITHUB ISSUE REPORT", info["verification_context"])
        self.assertIn("NOT MAINTAINER CONFIRMATION", info["verification_context"])
        self.assertIn("Amazon Bedrock", info["verification_context"])
        self.assertEqual(issue_url, info["primary_url"])
        self.assertTrue(info["primary_source_resolved"])
        self.assertIn(issue_url, info["checked_urls"])

    def test_core_claim_wrapper_blocks_before_gemini_when_claim_is_not_covered(self):
        p = fake_pipeline()
        run172.install(p)
        result = p.assess_evidence_sufficiency({
            "_run172_candidate_title": "Codex on AWS bedrock bug causing 10x charges",
            "verification_context": "Codex CLI docs",
            "context": "Codex CLI docs",
            "supplement_candidates": [],
            "evidence_supplement_attempted": True,
        })
        self.assertEqual("INSUFFICIENT", result["state"])
        self.assertFalse(result["decision_scope_safe"])
        self.assertIn("core_claim_coverage", result["blocking_missing"])
        self.assertEqual(result["state"], result["sufficiency"])

    def test_management_recovery_never_reads_article_body(self):
        raw = """・Source Summary: verified source\n・Decision: WAIT\n===NOTE_DRAFT_START===\n# Article\nAction: WRONG ARTICLE TEXT\nDecision Reason: WRONG ARTICLE TEXT\n"""
        recovered = run172._extract_management_lines(raw)
        self.assertEqual("verified source", recovered["source_summary_text"])
        self.assertEqual("WAIT", recovered["decision_text"])
        self.assertNotIn("action_text", recovered)
        self.assertNotIn("decision_reason_text", recovered)

    def test_parser_recovers_only_missing_management_fields(self):
        p = fake_pipeline(_parse_gemini_response=lambda text: {"decision_text": "WAIT", "action_text": "existing"})
        run172.install(p)
        parsed = p._parse_gemini_response(
            "・Source Summary: verified\n・Decision Reason: evidence is limited\n・Action: replacement\n===NOTE_DRAFT_START===\nArticle"
        )
        self.assertEqual("WAIT", parsed["decision_text"])
        self.assertEqual("existing", parsed["action_text"])
        self.assertEqual("verified", parsed["source_summary_text"])
        self.assertEqual("evidence is limited", parsed["decision_reason_text"])

    def test_patch_retry_contract_forbids_full_rewrite_and_new_facts(self):
        p = fake_pipeline()
        run172.install(p)
        instruction, _ = p.build_dynamic_retry_instruction([{"reason_code": "FACT_UNSUPPORTED_CLAIM"}])
        self.assertIn("前回稿は全面再生成の素材ではなく正本", instruction)
        self.assertIn("新しい数値・固有名詞・保証表現・外部知識を追加しない", instruction)

    def test_broad_rewrite_guard_detects_full_recomposition_but_not_local_edit(self):
        base = ("根拠のある説明です。次に試す条件を確認します。" * 80)
        local = base.replace("条件", "前提", 1)
        foreign = ("まったく異なる話題を長く説明します。別の構成です。" * 80)
        p = fake_pipeline()
        run172.install(p)
        self.assertFalse(p.human_appeal_materially_degraded({"note_draft": base}, {"note_draft": local}))
        self.assertTrue(p.human_appeal_materially_degraded({"note_draft": base}, {"note_draft": foreign}))

    def test_503_fails_over_after_one_attempt_and_preserves_logical_kind(self):
        calls = []
        p = fake_pipeline()

        def generate(model, prompt, **kwargs):
            calls.append((model, kwargs.get("request_kind")))
            if model == "m1":
                raise FakeAPIError(503)
            return "ok"

        p._generate_via_chat = generate
        run172.install(p)
        response, model = p._call_model_pool(
            "prompt", None, "quality_retry", 0, ["m1", "m2"], deep_dive=False,
            request_context="case", request_origin="new",
        )
        self.assertEqual("ok", response)
        self.assertEqual("m2", model)
        self.assertEqual([("m1", "quality_retry"), ("m2", "quality_retry")], calls)
        self.assertIn("m1", p.SESSION_UNAVAILABLE_MODELS)

    def test_rpm_429_keeps_one_same_model_transport_retry(self):
        calls = []
        p = fake_pipeline()
        p.classify_gemini_quota_error = lambda exc: "RPM"

        def generate(model, prompt, **kwargs):
            calls.append(model)
            if len(calls) == 1:
                raise FakeAPIError(429)
            return "ok"

        p._generate_via_chat = generate
        run172.install(p)
        response, model = p._call_model_pool("prompt", None, "deep_dive", 0, ["m1"], deep_dive=False)
        self.assertEqual("ok", response)
        self.assertEqual("m1", model)
        self.assertEqual(["m1", "m1"], calls)

    def test_product_review_503_also_fails_over_once(self):
        calls = []
        p = fake_pipeline()

        def generate(model, prompt, **kwargs):
            calls.append((model, kwargs.get("request_kind")))
            if model == "m1":
                raise FakeAPIError(503)
            return "ok"

        p._generate_via_chat = generate
        run172.install(p)
        response, model = p._call_product_review_pool("prompt", "case")
        self.assertEqual("ok", response)
        self.assertEqual("m2", model)
        self.assertEqual([("m1", "product_review"), ("m2", "product_review")], calls)

    def test_publication_probability_only_changes_reliability_surface_not_decision_scores(self):
        p = fake_pipeline(publication_probability_score=lambda item: 50)
        run172.install(p)
        issue_item = {
            "source": "HackerNews",
            "nameWithOwner": "Codex on AWS bedrock bug causing 10x charges",
            "primaryUrl": "https://github.com/openai/codex/issues/37674",
        }
        plain_item = {
            "source": "HackerNews",
            "nameWithOwner": "A calm explanation of RAG",
            "primaryUrl": "https://example.com/rag",
        }
        self.assertEqual(62, p.publication_probability_score(issue_item))
        self.assertEqual(50, p.publication_probability_score(plain_item))

    def test_production_bridge_activates_run172_before_pipeline_main(self):
        source = inspect.getsource(reader_value_review_bridge.main)
        self.assertIn("run172_production_reliability.install(pipeline)", source)
        self.assertLess(
            source.index("run172_production_reliability.install(pipeline)"),
            source.index("install(pipeline)"),
        )


if __name__ == "__main__":
    unittest.main()
