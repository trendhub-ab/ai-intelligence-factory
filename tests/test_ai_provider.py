import unittest
from ai_provider import GenerationRequest, GroqProvider, ProviderError, conservative_token_estimate
from groq_rate_policy import COMPOUND_MINI


def response(text='{"score":60}', finish="stop"):
    return {"choices": [{"finish_reason": finish, "message": {"content": text}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10}}


def score_schema():
    return {
        "type": "object",
        "properties": {"score": {"type": "integer", "minimum": 0, "maximum": 100}},
        "required": ["score"],
        "additionalProperties": False,
    }


class ProviderTests(unittest.TestCase):
    def test_success_and_exhaustion(self):
        calls = []
        p = GroqProvider(lambda data: (calls.append(data) or 200, {}, response()))
        result = p.generate(GenerationRequest("採点", 100))
        self.assertEqual(result.provider, "groq")
        self.assertEqual(calls[0]["model"], "openai/gpt-oss-120b")
        with self.assertRaisesRegex(ProviderError, "validation_budget_exceeded"):
            p.generate(GenerationRequest("採点", 100))
        self.assertEqual(len(calls), 1)

    def test_compound_article_lane_disables_external_tools(self):
        calls = []
        p = GroqProvider(
            lambda data: (calls.append(data) or 200, {}, response("ARTICLE")),
            model=COMPOUND_MINI.model,
            token_budget=COMPOUND_MINI.safe_tpm,
        )
        result = p.generate(GenerationRequest("記事" * 2000, 2000, reasoning_effort="medium"))
        self.assertEqual(result.model, COMPOUND_MINI.model)
        self.assertEqual(calls[0]["compound_custom"]["tools"]["enabled_tools"], [])
        self.assertNotIn("tool_choice", calls[0])
        self.assertEqual(calls[0]["citation_options"], "disabled")
        self.assertNotIn("reasoning_effort", calls[0])

    def test_compound_rejects_json_schema(self):
        p = GroqProvider(lambda _: self.fail("must not send"), model=COMPOUND_MINI.model)
        with self.assertRaisesRegex(ProviderError, "schema_not_supported"):
            p.generate(GenerationRequest("test", 100, {}))

    def test_japanese_estimator_is_token_oriented_not_utf8_bytes(self):
        estimate = conservative_token_estimate("あ" * 1000)
        self.assertGreaterEqual(estimate, 1000)
        self.assertLess(estimate, 3000)

    def test_oversized_never_sent_or_truncated(self):
        p = GroqProvider(lambda _: self.fail("must not send"))
        with self.assertRaisesRegex(ProviderError, "validation_budget_exceeded"):
            p.generate(GenerationRequest("あ" * 7000, 100))
        self.assertEqual(p.attempts, 0)

    def test_http_failure_is_not_retried(self):
        for status, kind in [(429, "rate_limit_error"), (503, "capacity_error"), (401, "authentication_error"), (413, "request_too_large"), (422, "invalid_request")]:
            p = GroqProvider(lambda _: (status, {"Retry-After": "2"}, {"secret": "hidden"}))
            with self.assertRaises(ProviderError) as cm:
                p.generate(GenerationRequest("test", 100))
            self.assertEqual(cm.exception.kind, kind)
            self.assertEqual(cm.exception.retry_after, 2)
            self.assertNotIn("hidden", str(cm.exception))
            self.assertEqual(p.attempts, 1)

    def test_timeout_keeps_reservation(self):
        def timeout(_):
            raise TimeoutError("credential must not leak")
        p = GroqProvider(timeout)
        with self.assertRaisesRegex(ProviderError, "^timeout$"):
            p.generate(GenerationRequest("test", 100))
        self.assertEqual(p.attempts, 1)
        self.assertGreater(p.reserved_tokens, 100)

    def test_invalid_outputs_fail_closed(self):
        for body in [response(finish="length"), response(""), {}, {"choices": []}]:
            p = GroqProvider(lambda _: (200, {}, body))
            with self.assertRaises(ProviderError):
                p.generate(GenerationRequest("test", 100))

    def test_schema_requires_validator_before_send(self):
        p = GroqProvider(lambda _: self.fail("must not send"))
        with self.assertRaisesRegex(ProviderError, "schema_validator_required"):
            p.generate(GenerationRequest("test", 100, {}))

    def test_strict_schema_transport_drops_local_only_size_constraints(self):
        schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "minLength": 1, "maxLength": 10},
                "reasons": {
                    "type": "array", "minItems": 1, "maxItems": 3,
                    "items": {"type": "string", "minLength": 1, "maxLength": 20},
                },
            },
            "required": ["summary", "reasons"],
            "additionalProperties": False,
        }
        p = GroqProvider(lambda _: self.fail("prepare only"), validate_schema=lambda *_: None)
        payload, _ = p.prepare(GenerationRequest("test", 100, schema))
        sent = payload["response_format"]["json_schema"]
        self.assertTrue(sent["strict"])
        serialized = str(sent["schema"])
        for key in ("minLength", "maxLength", "minItems", "maxItems"):
            self.assertNotIn(key, serialized)
        self.assertIn("minimum", str({"minimum": 0}))  # numeric range remains an allowed local/provider constraint
        self.assertEqual(schema["properties"]["summary"]["maxLength"], 10)

    def test_strict_schema_rejects_open_or_optional_object_before_send(self):
        for schema in [
            {"type": "object", "properties": {"x": {"type": "string"}}, "required": [], "additionalProperties": False},
            {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
        ]:
            p = GroqProvider(lambda _: self.fail("must not send"), validate_schema=lambda *_: None)
            with self.assertRaisesRegex(ProviderError, "strict_schema_invalid"):
                p.prepare(GenerationRequest("test", 100, schema))

    def test_schema_and_json_failures(self):
        schema = score_schema()
        def validator(value, original_schema):
            self.assertIs(original_schema, schema)
            if type(value.get("score")) is not int or not 0 <= value["score"] <= 100:
                raise ValueError("bad score")
        for text in ['{"score":60}', '{"score":101}', '{"score":"60"}', 'invalid', '{"score":NaN}']:
            p = GroqProvider(lambda _: (200, {}, response(text)), validate_schema=validator)
            if text == '{"score":60}':
                self.assertEqual(p.generate(GenerationRequest("test", 100, schema)).text, text)
            else:
                with self.assertRaisesRegex(ProviderError, "schema_error"):
                    p.generate(GenerationRequest("test", 100, schema))

    def test_multiple_calls_share_token_budget(self):
        p = GroqProvider(lambda _: (200, {}, response()), request_budget=3, token_budget=1000)
        p.generate(GenerationRequest("test", 300))
        with self.assertRaisesRegex(ProviderError, "validation_budget_exceeded"):
            p.generate(GenerationRequest("test", 600))

    def test_provider_accepts_actual_usage_above_estimate_within_safety_budget(self):
        body = response("ARTICLE")
        body["usage"] = {"prompt_tokens": 600, "completion_tokens": 200}
        p = GroqProvider(lambda _: (200, {}, body), token_budget=1000)
        result = p.generate(GenerationRequest("test", 100))
        self.assertEqual(result.prompt_tokens + result.completion_tokens, 800)
        self.assertLess(result.reserved_token_estimate, 800)
        self.assertEqual(p.reserved_tokens, 800)
        self.assertEqual(result.text, "ARTICLE")

    def test_provider_rejects_actual_usage_above_safety_budget(self):
        body = response("ARTICLE")
        body["usage"] = {"prompt_tokens": 900, "completion_tokens": 200}
        p = GroqProvider(lambda _: (200, {}, body), token_budget=1000)
        with self.assertRaisesRegex(ProviderError, "actual_usage_exceeds_safety_budget"):
            p.generate(GenerationRequest("test", 100))
        self.assertEqual(p.reserved_tokens, 1100)

    def test_refusal_and_untrusted_usage(self):
        for mutation in ["refusal", "usage"]:
            body = response()
            if mutation == "refusal":
                body["choices"][0]["message"]["refusal"] = "no"
            else:
                body["usage"]["completion_tokens"] = -1
            with self.assertRaises(ProviderError):
                GroqProvider(lambda _: (200, {}, body)).generate(GenerationRequest("test", 100))


if __name__ == "__main__":
    unittest.main()
