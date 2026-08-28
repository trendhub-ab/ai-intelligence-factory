from pathlib import Path

pipeline_path = Path("pipeline.py")
source = pipeline_path.read_text(encoding="utf-8")

old_profile = '''    last_error = None
    for model_name in DEEP_DIVE_MODEL_POOL:
'''
new_profile = '''    last_error = None
    # Run149: preserve full Product Review reasoning quality on the normal path.
    # Only the one logical structured-output repair request uses low thinking so a
    # malformed/truncated JSON response can be repaired within the existing budget.
    structured_repair = request_kind_base == "product_review_retry"
    thinking_level = "low" if structured_repair else "medium"
    max_output_tokens = 5000 if structured_repair else 8000
    for model_name in DEEP_DIVE_MODEL_POOL:
'''
if old_profile not in source:
    raise SystemExit("Run149 profile insertion anchor not found")
source = source.replace(old_profile, new_profile, 1)

old_config = '''                        # Gemini 3.6 Flash defaults to medium thinking. Thinking tokens count
                        # against max_output_tokens, so the former 2200 cap could exhaust the
                        # generation budget before the schema-constrained JSON body closed.
                        # Product Review is structured classification/extraction; low thinking
                        # preserves reasoning while reserving enough budget for complete JSON.
                        "thinking_config": {"thinking_level": "low"},
                        "max_output_tokens": 5000,
'''
new_config = '''                        # Normal Product Review keeps medium thinking for decision quality.
                        # Only a schema-repair request switches to low thinking. Both paths retain
                        # enough generation budget for the schema-constrained JSON body to close.
                        "thinking_config": {"thinking_level": thinking_level},
                        "max_output_tokens": max_output_tokens,
'''
if old_config not in source:
    raise SystemExit("Run149 config replacement anchor not found")
source = source.replace(old_config, new_config, 1)
pipeline_path.write_text(source, encoding="utf-8")

run148 = Path("tests/test_run148_product_review_output_budget.py")
run148.write_text('''import unittest\nfrom pathlib import Path\n\n\nclass Run148ProductReviewOutputBudgetTests(unittest.TestCase):\n    @classmethod\n    def setUpClass(cls):\n        cls.source = Path("pipeline.py").read_text(encoding="utf-8")\n\n    def test_old_2200_output_cap_never_returns(self):\n        anchor = '"response_json_schema": _PRODUCT_REVIEW_RESPONSE_SCHEMA'\n        start = self.source.index(anchor)\n        block = self.source[start:start + 1200]\n        self.assertNotIn('"max_output_tokens": 2200', block)\n\n    def test_product_review_keeps_explicit_thinking_and_output_profile(self):\n        anchor = '"response_json_schema": _PRODUCT_REVIEW_RESPONSE_SCHEMA'\n        start = self.source.index(anchor)\n        block = self.source[start:start + 1200]\n        self.assertIn('"thinking_config": {"thinking_level": thinking_level}', block)\n        self.assertIn('"max_output_tokens": max_output_tokens', block)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding="utf-8")

run149 = Path("tests/test_run149_product_review_quality_first.py")
run149.write_text('''import inspect\nimport unittest\nfrom unittest.mock import MagicMock, patch\n\nimport pipeline\n\n\nclass Run149ProductReviewQualityFirstTests(unittest.TestCase):\n    def _capture_config(self, request_kind_base):\n        budget = MagicMock()\n        budget.can_request.return_value = True\n        budget.summary.return_value = "ok"\n        with patch.object(pipeline, "PRODUCT_REVIEW_REQUEST_BUDGET", budget), \\\n             patch.object(pipeline, "DEEP_DIVE_MODEL_POOL", ["gemini-3.6-flash"]), \\\n             patch.object(pipeline, "SESSION_EXHAUSTED_MODELS", set()), \\\n             patch.object(pipeline, "SESSION_UNAVAILABLE_MODELS", set()), \\\n             patch.object(pipeline, "GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", 0), \\\n             patch.object(pipeline, "_generate_via_chat", return_value=object()) as generate:\n            pipeline._call_product_review_pool(\n                "prompt", "context", request_kind_base=request_kind_base\n            )\n        return generate.call_args.kwargs["config"]\n\n    def test_primary_review_preserves_medium_thinking_quality(self):\n        config = self._capture_config("product_review")\n        self.assertEqual(config["thinking_config"], {"thinking_level": "medium"})\n        self.assertEqual(config["max_output_tokens"], 8000)\n\n    def test_structured_retry_uses_low_thinking_recovery_profile(self):\n        config = self._capture_config("product_review_retry")\n        self.assertEqual(config["thinking_config"], {"thinking_level": "low"})\n        self.assertEqual(config["max_output_tokens"], 5000)\n\n    def test_profile_depends_on_logical_request_not_transport_attempt(self):\n        source = inspect.getsource(pipeline._call_product_review_pool)\n        self.assertIn('structured_repair = request_kind_base == "product_review_retry"', source)\n        self.assertIn('thinking_level = "low" if structured_repair else "medium"', source)\n        self.assertIn('max_output_tokens = 5000 if structured_repair else 8000', source)\n\n\nif __name__ == "__main__":\n    unittest.main()\n''', encoding="utf-8")

print("Run149 patch applied")
