import ast
import types
import unittest
from pathlib import Path
from unittest.mock import patch


class Run244DecisionProductProtocolIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import pipeline
        import evidence_sufficiency
        import product_review_protocol
        import content_generation_protocol
        cls.pipeline = pipeline
        cls.evidence = evidence_sufficiency
        cls.product = product_review_protocol
        cls.content = content_generation_protocol

    def _pipeline_payload(self):
        p = self.pipeline
        components = {label: max(0, maximum // 2) for label, maximum in p._ADOPTION_SCORE_COMPONENTS}
        return {
            "category": "OTHER" if "OTHER" in p.PORTFOLIO_TOPICS else sorted(p.PORTFOLIO_TOPICS)[0],
            "adoption_score": sum(components.values()),
            "components": components,
            "adoption_status": "WATCH",
            "evidence_confidence": "MEDIUM",
            "production_readiness": "MEDIUM",
            "main_risk": "一次情報で長期運用条件が未確認",
            "best_for": "限定PoC",
            "avoid_for": "即時の全面標準化",
            "short_rationale": "一次情報で確認できる範囲の評価",
            "japanese_display_label": "Example — 技術評価ツール",
            "next_review_days": 30,
        }

    def test_evidence_wrapper_matches_canonical_with_live_dependencies(self):
        p = self.pipeline
        info = {
            "source": "GitHub", "primary_source_resolved": True,
            "context": "Developers document the implementation method and limitations.",
            "evidence_metadata": {"coverage": {"method": "FOUND", "limitations": "FOUND"}},
            "requested_action_risk_tier": "MEDIUM",
        }
        expected = self.evidence.assess_evidence_sufficiency(
            info,
            future_source_pattern=p._FUTURE_SOURCE_PATTERN,
            evidence_trace_url_key=p._evidence_trace_url_key,
            evidence_sufficient=p.EVIDENCE_SUFFICIENT,
            evidence_supplement_required=p.EVIDENCE_SUPPLEMENT_REQUIRED,
            evidence_insufficient=p.EVIDENCE_INSUFFICIENT,
        )
        self.assertEqual(p.assess_evidence_sufficiency(info), expected)

    def test_decision_prompt_wrapper_matches_canonical_live_binding(self):
        p = self.pipeline
        kwargs = dict(
            name="org/repo", url="https://github.com/org/repo", stars=123, desc="tooling",
            quality_feedback="", source="GitHub", source_context="verified implementation method",
            grounding_status_hint=p.GROUNDING_METADATA_ONLY,
            evidence_metadata={}, freshness={}, previous_article="", evidence_result={},
        )
        expected = self.content.build_decision_prompt(
            **kwargs,
            engagement_labels=p.ENGAGEMENT_LABELS,
            max_evidence_total_chars=p.MAX_EVIDENCE_TOTAL_CHARS,
            truncate_source_context=p._truncate_source_context,
            source_fact_discipline=p._source_fact_discipline,
            human_editorial_style_rules=p._human_editorial_style_rules,
            article_display_variant=p._article_display_variant,
            section_split_token=p.SECTION_SPLIT_TOKEN,
            datetime_cls=p.datetime,
            jst=p.JST,
        )
        self.assertEqual(p.build_decision_prompt(**kwargs), expected)

    def test_product_validation_wrapper_matches_canonical(self):
        p = self.pipeline
        payload = self._pipeline_payload()
        expected = self.product._validate_product_review_payload(
            payload,
            product_review_response_schema=p._PRODUCT_REVIEW_RESPONSE_SCHEMA,
            portfolio_topics=p.PORTFOLIO_TOPICS,
            adoption_score_components=p._ADOPTION_SCORE_COMPONENTS,
            decision_intelligence_module=p.decision_intelligence,
        )
        self.assertEqual(p._validate_product_review_payload(dict(payload)), expected)

    def test_product_parser_wrapper_and_provider_object_path_match(self):
        p = self.pipeline
        payload = self._pipeline_payload()
        direct = p._parse_product_review_response(dict(payload))
        response = types.SimpleNamespace(parsed=dict(payload), text="")
        via_model = p._parse_product_review_model_response(response)
        self.assertEqual(via_model, direct)
        self.assertEqual(via_model["adoption_score"], payload["adoption_score"])

    def test_technology_state_wrapper_reads_live_pipeline_helpers(self):
        p = self.pipeline
        state = {
            "sources": ["GitHub"], "primary_url": "https://github.com/org/repo",
            "canonical_entity_id": "github:org/repo", "technology_name": "Legacy",
            "evidence_urls": [], "entity_aliases": [],
        }
        with patch.object(p, "_effective_evidence_source", return_value="GitHub"), patch.object(p, "_github_repo_identity", return_value="patched/repo"):
            result = p._technology_state_to_repo(state)
        self.assertEqual(result["nameWithOwner"], "patched/repo")

    def test_pipeline_physically_relinquishes_heavy_run244_bodies(self):
        source = Path("pipeline.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        nodes = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        self.assertLess(len(source.splitlines()), 10500)
        for name in ("assess_evidence_sufficiency", "build_decision_prompt", "_validate_product_review_payload", "_parse_product_review_response", "_parse_product_review_model_response", "_technology_state_to_repo"):
            node = nodes[name]
            self.assertLessEqual(node.end_lineno - node.lineno + 1, 25, name)
        for name in ("_product_review_prompt", "_strict_schema_int", "_normalize_japanese_display_label", "_decode_product_review_json"):
            self.assertNotIn(name, nodes, name)

    def test_side_effectful_owners_remain_in_pipeline(self):
        source = Path("pipeline.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        for required in ("generate_intelligence_report", "_call_product_review_pool", "select_product_review_candidates", "run_product_reviews", "validate_fact_gate", "prepare_source_context"):
            self.assertIn(required, names)


if __name__ == "__main__":
    unittest.main()
