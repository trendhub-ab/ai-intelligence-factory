"""Experimental provider boundary; not installed in Production.

Transport and schema validator are injected. No SDK imports, credentials, network,
fallback, retries or persistent state are touched by importing this module.
The caller owns persistent organization quotas before enabling live transport.
"""
from dataclasses import dataclass
import json
import math
from typing import Callable, Protocol


class ProviderError(RuntimeError):
    def __init__(self, kind: str, status: int | None = None, retry_after: float | None = None):
        super().__init__(kind)  # Never include response bodies, prompts or keys.
        self.kind, self.status, self.retry_after = kind, status, retry_after


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    max_output_tokens: int
    schema: dict | None = None
    reasoning_effort: str = "low"


@dataclass(frozen=True)
class GenerationResult:
    text: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int


class Provider(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...


def _retry_after(headers: dict) -> float | None:
    try:
        value = float(next(v for k, v in headers.items() if k.lower() == "retry-after"))
        return value if math.isfinite(value) and value >= 0 else None
    except (StopIteration, TypeError, ValueError):
        return None


def conservative_token_estimate(text: str) -> int:
    """Estimate input tokens conservatively without coupling Production to a tokenizer.

    UTF-8 byte length is not a token count and severely over-reserves Japanese text.
    Count each non-ASCII code point as one token, ASCII at four chars/token, then add
    20% headroom. This is deliberately conservative for the Factory's Japanese prompts;
    live provider usage is still checked after every response and rate-limit headers are
    the authority for current account capacity.
    """
    if not isinstance(text, str):
        raise ProviderError("invalid_request")
    non_ascii = sum(1 for char in text if ord(char) > 127)
    ascii_chars = len(text) - non_ascii
    return max(1, math.ceil((non_ascii + ascii_chars / 4.0) * 1.20))


class GroqProvider:
    """Bounded validation adapter. One instance is a run, NOT a daily quota ledger.

    transport(payload) returns (HTTP status, headers, decoded JSON body).
    Input estimation uses a conservative language-aware token approximation plus
    framing/schema overhead, not UTF-8 bytes. Oversized prompts are rejected, never cut.
    A schema request requires an independent validator that raises on invalid data.
    """
    model = "openai/gpt-oss-120b"

    def __init__(self, transport: Callable, *, validate_schema: Callable | None = None,
                 request_budget: int = 1, token_budget: int = 8000):
        if type(request_budget) is not int or not 1 <= request_budget <= 3:
            raise ProviderError("invalid_validation_budget")
        if type(token_budget) is not int or not 1 <= token_budget <= 8000:
            raise ProviderError("invalid_validation_budget")
        self.transport, self.validate_schema = transport, validate_schema
        self.request_budget, self.token_budget = request_budget, token_budget
        self.attempts = self.reserved_tokens = 0

    def prepare(self, request: GenerationRequest) -> tuple[dict, int]:
        if not isinstance(request.prompt, str) or not request.prompt.strip():
            raise ProviderError("invalid_prompt")
        if type(request.max_output_tokens) is not int or request.max_output_tokens <= 0:
            raise ProviderError("invalid_output_limit")
        if request.reasoning_effort not in {"low", "medium", "high"}:
            raise ProviderError("invalid_reasoning_effort")
        payload = {"model": self.model, "messages": [{"role": "user", "content": request.prompt}],
                   "max_completion_tokens": request.max_output_tokens,
                   "reasoning_effort": request.reasoning_effort, "stream": False}
        if request.schema is not None:
            if not isinstance(request.schema, dict) or self.validate_schema is None:
                raise ProviderError("schema_validator_required")
            payload["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "factory_response", "strict": True, "schema": request.schema}}
        try:
            framing = dict(payload)
            framing["messages"] = [{"role": "user", "content": ""}]
            framing_tokens = conservative_token_estimate(
                json.dumps(framing, ensure_ascii=False, allow_nan=False)
            ) + 128
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
        self.reserved_tokens += estimate  # Keep reservation even on unknown timeout.
        try:
            status, headers, body = self.transport(payload)
        except TimeoutError:
            raise ProviderError("timeout") from None
        except Exception:
            raise ProviderError("transport_error") from None
        if status != 200:
            kind = {400: "invalid_request", 401: "authentication_error", 403: "permission_error",
                    404: "model_unavailable", 429: "rate_limit_error"}.get(status,
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
            if sum(counts) > estimate:
                self.reserved_tokens += sum(counts) - estimate
                raise ProviderError("token_estimate_exceeded")
            if request.schema is not None:
                try:
                    parsed = json.loads(content, parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                    self.validate_schema(parsed, request.schema)
                except Exception:
                    raise ProviderError("schema_error") from None
            return GenerationResult(content, "groq", self.model, *counts)
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ProviderError("malformed_response") from None
