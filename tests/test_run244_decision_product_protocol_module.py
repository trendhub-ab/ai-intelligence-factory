import ast
import inspect
import unittest


class FakeDecisionIntelligence:
    ADOPTION_STATUSES = {"WATCH", "TEST", "ADOPT", "AVOID"}
    CONFIDENCE_LEVELS = {"LOW", "MEDIUM", "HIGH"}
    READINESS_LEVELS = {"LOW", "MEDIUM", "HIGH"}


class Run244DecisionProductProtocolModuleTests(unittest.TestCase):
    def setUp(self):
        import evidence_sufficiency as evidence
        import product_review_protocol as product
        import content_generation_protocol as content
        self.evidence = evidence
        self.product = product
        self.content = content
        self.components = [("Evidence", 25), ("Maturity", 25), ("Utility", 20), ("Risk", 15), ("Integration", 10), ("Durability", 5)]
        self.schema = {
            "required": [
                "category", "adoption_score", "components", "adoption_status", "evidence_confidence",
                "production_readiness", "main_risk", "best_for", "avoid_for", "short_rationale",
                "next_review_days",
            ],
            "properties": {name: {} for name in [
                "category", "adoption_score", "components", "adoption_status", "evidence_confidence",
                "production_readiness", "main_risk", "best_for", "avoid_for", "short_rationale",
                "japanese_display_label", "next_review_days",
            ]},
        }

    def _valid_payload(self):
        return {
            "category": "OTHER",
            "adoption_score": 60,
            "components": {"Evidence": 20, "Maturity": 15, "Utility": 10, "Risk": 7, "Integration": 5, "Durability": 3},
            "adoption_status": "WATCH",
            "evidence_confidence": "MEDIUM",
            "production_readiness": "MEDIUM",
            "main_risk": "一次情報で長期運用条件が未確認",
            "best_for": "限定PoCでの比較",
            "avoid_for": "即時の全社標準化",
            "short_rationale": "確認済み一次情報の範囲で限定評価",
            "japanese_display_label": "Example — 技術評価ツール",
            "next_review_days": 30,
        }

    def test_new_modules_have_no_provider_network_or_persistence_imports(self):
        allowed = {
            "evidence_sufficiency": {"__future__", "re"},
            "product_review_protocol": {"__future__", "json", "re", "urllib.parse"},
        }
        for module_name, expected in allowed.items():
            module = __import__(module_name)
            tree = ast.parse(inspect.getsource(module))
            imports = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom):
                    imports.add(node.module or "")
            self.assertTrue(imports <= expected, (module_name, imports))
            text = inspect.getsource(module).lower()
            for forbidden in ("requests", "google.genai", "notion_api", "github_api", "open("):
                self.assertNotIn(forbidden, text)

    def test_evidence_low_risk_primary_technical_is_sufficient(self):
        info = {
            "source": "GitHub",
            "primary_source_resolved": True,
            "context": "Developers describe the implementation method and architecture.",
            "evidence_metadata": {"coverage": {"method": "FOUND"}},
            "requested_action_risk_tier": "LOW",
        }
        result = self.evidence.assess_evidence_sufficiency(
            info,
            future_source_pattern=__import__("re").compile(r"future", __import__("re").I),
            evidence_trace_url_key=lambda url: url,
            evidence_sufficient="SUFFICIENT",
            evidence_supplement_required="SUPPLEMENT_REQUIRED",
            evidence_insufficient="INSUFFICIENT",
        )
        self.assertEqual(result["state"], "SUFFICIENT")
        self.assertTrue(result["decision_scope_safe"])

    def test_evidence_unresolved_primary_fails_closed(self):
        result = self.evidence.assess_evidence_sufficiency(
            {"source": "GitHub", "context": "implementation method", "primary_source_resolved": False},
            future_source_pattern=__import__("re").compile(r"future", __import__("re").I),
            evidence_trace_url_key=lambda url: url,
            evidence_sufficient="SUFFICIENT",
            evidence_supplement_required="SUPPLEMENT_REQUIRED",
            evidence_insufficient="INSUFFICIENT",
        )
        self.assertEqual(result["state"], "INSUFFICIENT")
        self.assertIn("primary_source_resolved", result["blocking_missing"])

    def test_product_prompt_is_decision_only_and_source_bounded(self):
        text = self.product._product_review_prompt(
            {"nameWithOwner": "org/repo", "url": "https://github.com/org/repo"},
            {"context": "verified primary evidence"},
            {"adoption_status": "WATCH"},
        )
        self.assertIn("一次情報だけ", text)
        self.assertIn("記事は書かない", text)
        self.assertIn("verified primary evidence", text)

    def test_product_payload_validation_preserves_score_sum_contract(self):
        payload = self._valid_payload()
        result = self.product._validate_product_review_payload(
            payload,
            product_review_response_schema=self.schema,
            portfolio_topics={"OTHER", "MODEL"},
            adoption_score_components=self.components,
            decision_intelligence_module=FakeDecisionIntelligence,
        )
        self.assertIs(result, payload)
        broken = self._valid_payload()
        broken["adoption_score"] = 61
        with self.assertRaisesRegex(ValueError, "adoption_score_sum_mismatch"):
            self.product._validate_product_review_payload(
                broken,
                product_review_response_schema=self.schema,
                portfolio_topics={"OTHER", "MODEL"},
                adoption_score_components=self.components,
                decision_intelligence_module=FakeDecisionIntelligence,
            )

    def test_product_payload_bool_never_silently_becomes_integer(self):
        payload = self._valid_payload()
        payload["next_review_days"] = True
        with self.assertRaisesRegex(ValueError, "must be integer"):
            self.product._validate_product_review_payload(
                payload,
                product_review_response_schema=self.schema,
                portfolio_topics={"OTHER"},
                adoption_score_components=self.components,
                decision_intelligence_module=FakeDecisionIntelligence,
            )

    def test_display_label_is_ui_only_conservative_normalization(self):
        self.assertEqual(self.product._normalize_japanese_display_label("Example   —  技術評価ツール"), "Example — 技術評価ツール")
        self.assertEqual(self.product._normalize_japanese_display_label("Example — 今すぐ導入すべき最強ツール"), "")
        self.assertEqual(self.product._normalize_japanese_display_label("Example only English"), "")

    def test_product_json_decoder_only_repairs_transport_wrapper(self):
        self.assertEqual(self.product._decode_product_review_json('```json\n{"x":1}\n```'), {"x": 1})
        with self.assertRaises(Exception):
            self.product._decode_product_review_json("not-json")

    def test_product_response_parser_preserves_existing_field_mapping(self):
        payload = self._valid_payload()
        result = self.product._parse_product_review_response(
            payload,
            adoption_score_components=self.components,
            validate_product_review_payload=lambda obj: obj,
            normalize_japanese_display_label=self.product._normalize_japanese_display_label,
        )
        self.assertEqual(result["adoption_score"], 60)
        self.assertEqual(result["main_risk_text"], payload["main_risk"])
        self.assertIn("Evidence 20/25", result["adoption_score_breakdown_text"])

    def test_technology_rehydrate_uses_only_explicit_identity_callbacks(self):
        state = {
            "sources": ["GitHub"],
            "primary_url": "https://github.com/org/repo",
            "canonical_entity_id": "github:org/repo",
            "technology_name": "Legacy Name",
            "evidence_urls": ["https://github.com/org/repo/blob/main/README.md"],
            "entity_aliases": [],
        }
        result = self.product._technology_state_to_repo(
            state,
            effective_evidence_source=lambda _temp: "GitHub",
            github_repo_identity=lambda _temp: "org/repo",
        )
        self.assertEqual(result["nameWithOwner"], "org/repo")
        self.assertFalse(result["sourceContextVerified"])

    def test_decision_prompt_is_canonical_content_owner(self):
        self.assertTrue(callable(self.content.build_decision_prompt))
        source = inspect.getsource(self.content.build_decision_prompt)
        self.assertIn("source_fact_discipline", source)
        self.assertIn("human_editorial_style_rules", source)


if __name__ == "__main__":
    unittest.main()
