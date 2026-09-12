"""Experimental provider boundary; not installed in Production.

Transport and schema validator are injected. No SDK imports, credentials, network,
fallback, retries or persistent state are touched by importing this module.
The caller owns persistent organization quotas before enabling live transport.
"""
from dataclasses import dataclass
import json
import math
from typing import Callable, Protocol

from groq_rate_policy import GPT_OSS_120B, policy_for_model


class ProviderError(RuntimeError):
    def __init__(
        self,
        kind: str,
        status: int | None = None,
        retry_after: float | None = None,
        *,
        diagnostic_text: str | None = None,
        diagnostic_detail: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ):
        super().__init__(kind)
        self.kind, self.status, self.retry_after = kind, status, retry_after
        self.diagnostic_text = diagnostic_text
        self.diagnostic_detail = diagnostic_detail
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    max_output_tokens: int
    schema: dict | None = None
    reasoning_effort: str = "low"
    structured_output_mode: str = "strict_schema"


@dataclass(frozen=True)
class GenerationResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    reserved_token_estimate: int = 0


class Provider(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...


def _retry_after(headers: dict) -> float | None:
    try:
        value = float(next(v for k, v in headers.items() if k.lower() == "retry-after"))
        return value if math.isfinite(value) and value >= 0 else None
    except (StopIteration, TypeError, ValueError):
        return None


def conservative_token_estimate(text: str) -> int:
    if not isinstance(text, str):
        raise ProviderError("invalid_request")
    non_ascii = sum(1 for char in text if ord(char) > 127)
    ascii_chars = len(text) - non_ascii
    return max(1, math.ceil((non_ascii + ascii_chars / 4.0) * 1.20))


def _groq_strict_schema(schema: dict) -> dict:
    if not isinstance(schema, dict):
        raise ProviderError("schema_validator_required")
    validation_only = {"minLength", "maxLength", "minItems", "maxItems"}

    def normalize(node):
        if isinstance(node, list):
            return [normalize(value) for value in node]
        if not isinstance(node, dict):
            return node
        out = {}
        for key, value in node.items():
            if key in validation_only:
                continue
            out[key] = normalize(value)
        if "enum" in out and "type" not in out:
            enum_values = out.get("enum")
            if isinstance(enum_values, list) and enum_values and all(isinstance(value, str) for value in enum_values):
                out["type"] = "string"
            else:
                raise ProviderError("strict_schema_invalid")
        if out.get("type") == "object":
            properties = out.get("properties")
            if not isinstance(properties, dict):
                raise ProviderError("strict_schema_invalid")
            required = out.get("required")
            if not isinstance(required, list) or set(required) != set(properties):
                raise ProviderError("strict_schema_invalid")
            if out.get("additionalProperties") is not False:
                raise ProviderError("strict_schema_invalid")
        return out

    return normalize(schema)


class GroqProvider:
    def __init__(self, transport: Callable, *, validate_schema: Callable | None = None,
                 request_budget: int = 1, token_budget: int | None = None,
                 model: str = GPT_OSS_120B.model):
        try:
            policy = policy_for_model(model)
        except ValueError:
            raise ProviderError("unsupported_model") from None
        if type(request_budget) is not int or not 1 <= request_budget <= 3:
            raise ProviderError("invalid_validation_budget")
        token_budget = policy.safe_tpm if token_budget is None else token_budget
        if type(token_budget) is not int or not 1 <= token_budget <= policy.official_tpm:
            raise ProviderError("invalid_validation_budget")
        self.transport, self.validate_schema = transport, validate_schema
        self.request_budget, self.token_budget = request_budget, token_budget
        self.model, self.policy = model, policy
        self.attempts = self.reserved_tokens = 0

    def prepare(self, request: GenerationRequest) -> tuple[dict, int]:
        if not isinstance(request.prompt, str) or not request.prompt.strip():
            raise ProviderError("invalid_prompt")
        if type(request.max_output_tokens) is not int or request.max_output_tokens <= 0:
            raise ProviderError("invalid_output_limit")
        if request.reasoning_effort not in {"low", "medium", "high"}:
            raise ProviderError("invalid_reasoning_effort")
        if request.structured_output_mode not in {"strict_schema", "json_object_local_strict"}:
            raise ProviderError("invalid_structured_output_mode")
        payload = {"model": self.model, "messages": [{"role": "user", "content": request.prompt}],
                   "max_completion_tokens": request.max_output_tokens, "stream": False}
        if self.model.startswith("openai/gpt-oss-"):
            payload["reasoning_effort"] = request.reasoning_effort
        if self.model.startswith("groq/compound"):
            payload["compound_custom"] = {"tools": {"enabled_tools": []}}
            payload["citation_options"] = "disabled"
        if request.schema is not None:
            if self.model.startswith("groq/compound"):
                raise ProviderError("schema_not_supported_for_model")
            if not isinstance(request.schema, dict) or self.validate_schema is None:
                raise ProviderError("schema_validator_required")
            if request.structured_output_mode == "strict_schema":
                payload["response_format"] = {"type": "json_schema", "json_schema": {
                    "name": "factory_response", "strict": True, "schema": _groq_strict_schema(request.schema)}}
            else:
                payload["response_format"] = {"type": "json_object"}
            if self.model.startswith("openai/gpt-oss-"):
                payload["reasoning_format"] = "hidden"
        elif request.structured_output_mode != "strict_schema":
            raise ProviderError("structured_output_schema_required")
        try:
            framing = dict(payload)
            framing["messages"] = [{"role": "user", "content": ""}]
            framing_tokens = conservative_token_estimate(json.dumps(framing, ensure_ascii=False, allow_nan=False)) + 128
            estimate = conservative_token_estimate(request.prompt) + framing_tokens + request.max_output_tokens
        except (TypeError, ValueError):
            raise ProviderError("invalid_request") from None
        if estimate > self.token_budget:
            raise ProviderError("validation_budget_exceeded")
        return payload, estimate

    def generate(self, request: GenerationRequest) -> GenerationResult:
        payload, estimate = self.prepare(request)
        if self.attempts >= self.request_budget or self.reserved_tokens + estimate > self.token_budget:
            raise ProviderError("validation_budget_exceeded")
        self.attempts += 1
        self.reserved_tokens += estimate
        try:
            status, headers, body = self.transport(payload)
        except ProviderError:
            raise
        except TimeoutError:
            raise ProviderError("timeout") from None
        except Exception:
            raise ProviderError("transport_error") from None
        if status != 200:
            kind = {400: "invalid_request", 401: "authentication_error", 403: "permission_error",
                    404: "model_unavailable", 413: "request_too_large", 422: "invalid_request",
                    429: "rate_limit_error"}.get(status,
                    "capacity_error" if isinstance(status, int) and status >= 500 else "http_error")
            raise ProviderError(kind, status, _retry_after(headers))
        try:
            choice = body["choices"][0]
            message = choice["message"]
            if message.get("refusal"):
                raise ProviderError("refusal")
            if choice["finish_reason"] != "stop":
                raise ProviderError("incomplete_output")
            content = message["content"]
            if not isinstance(content, str) or not content.strip():
                raise ProviderError("empty_output")
            usage = body["usage"]
            counts = [usage["prompt_tokens"], usage["completion_tokens"]]
            if any(type(n) is not int or n < 0 for n in counts):
                raise ProviderError("invalid_usage")
            actual_tokens = sum(counts)
            if actual_tokens > self.reserved_tokens:
                self.reserved_tokens = actual_tokens
            if actual_tokens > self.token_budget:
                raise ProviderError("actual_usage_exceeds_safety_budget")
            if request.schema is not None:
                try:
                    parsed = json.loads(content, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                    self.validate_schema(parsed, request.schema)
                except Exception as exc:
                    raise ProviderError(
                        "schema_error",
                        diagnostic_text=content,
                        diagnostic_detail=f"{type(exc).__name__}: {exc}",
                        prompt_tokens=counts[0],
                        completion_tokens=counts[1],
                    ) from None
            return GenerationResult(content, "groq", self.model, *counts, reserved_token_estimate=estimate)
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ProviderError("malformed_response") from None
