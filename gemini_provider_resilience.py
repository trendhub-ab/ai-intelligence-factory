"""Provider-verified Gemini transient failure handling.

Run303 was created after two consecutive real Production ONE-SHOTs showed a mixed
provider state: the SDK emitted genuine HTTP 503 responses, while the same model
could also return HTTP 200 later in the same run. The historical Run172 bridge
fell back immediately after the first 503, amplifying a short provider wobble into
an apparent run-wide outage.

Run355 keeps that confirmation policy for normal generation, screening, and Product
Review, but narrows Pending Retry. Its dedicated budget is small; spending it on
same-model 503 confirmation makes cross-model fallback unreachable. Therefore a
structured 503 on a pending-retry request opens a run-local circuit immediately and
preserves remaining requests for the next model. Run371 applies this same existing
policy to the explicit read-only ``pending_retry_validation`` origin; it does not
change normal Production behavior, quota caps, or publication gates.

Run360 establishes a single retry owner. google-genai retries transient HTTP failures
(including 503) internally by default, while this module also performs bounded provider
confirmation/fallback. Layering both mechanisms can multiply one logical request into
many provider-visible HTTP attempts and makes Factory usage telemetry undercount the
real transport work. Production therefore rebuilds the Gemini client with SDK retries
disabled (one total SDK attempt). All retry/fallback decisions remain owned by the
Factory budgets and circuits below.

Run374 adds an operator safety exclusion for Pending Retry only. This is evaluated
immediately before provider dispatch so a model excluded for quota preservation can
never be reintroduced by upstream fallback-pool normalization.
"""
from __future__ import annotations

import os
import time
from typing import Any

_INSTALL_FLAG = "_aiif_provider_resilience_installed"
_SDK_SINGLE_OWNER_FLAG = "_aiif_gemini_sdk_single_retry_owner_installed"
_SDK_RETRY_ATTEMPTS = 1
_DEFAULT_503_CONFIRM_DELAY_SECONDS = 10
_MAX_503_CONFIRM_DELAY_SECONDS = 20
_PENDING_RETRY_ORIGINS = frozenset({"pending_retry", "pending_retry_validation"})


def _is_pending_retry_origin(request_origin: str) -> bool:
    return str(request_origin or "").strip() in _PENDING_RETRY_ORIGINS


def _pending_retry_excluded_models() -> frozenset[str]:
    raw = str(os.environ.get("GEMINI_PENDING_RETRY_EXCLUDED_MODELS", "") or "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _provider_status_code(exc: BaseException) -> int | None:
    values = [getattr(exc, "code", None)]
    response = getattr(exc, "response", None)
    values.append(getattr(response, "status_code", None) if response is not None else None)
    for value in values:
        try:
            if value is not None:
                return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _clear_legacy_503_state(pipeline_module: Any, model_name: str) -> None:
    counts = getattr(pipeline_module, "_aiif_transient_503_counts", None)
    if isinstance(counts, dict):
        counts.pop(model_name, None)


def _confirmation_delay(pipeline_module: Any, exc: BaseException) -> int:
    try:
        raw = int(pipeline_module._extract_retry_delay(exc, _DEFAULT_503_CONFIRM_DELAY_SECONDS))
    except Exception:
        raw = _DEFAULT_503_CONFIRM_DELAY_SECONDS
    return max(1, min(_MAX_503_CONFIRM_DELAY_SECONDS, raw))


def _mark_confirmed_503(pipeline_module: Any, model_name: str) -> None:
    pipeline_module._mark_model_unavailable(model_name, "provider_503_confirmed_pair")


def _check_deep_dive_local_budgets(pipeline_module: Any, kind: str, request_origin: str) -> None:
    if not pipeline_module.DEEP_DIVE_MODEL_BUDGET.can_request():
        raise pipeline_module.DeepDiveRunBudgetExceededError(
            f"Deep Dive run budget exhausted: used={pipeline_module.DEEP_DIVE_MODEL_BUDGET.used}, "
            f"budget={pipeline_module.DEEP_DIVE_MODEL_BUDGET.budget}, kind={kind}"
        )
    if _is_pending_retry_origin(request_origin) and not pipeline_module.PENDING_RETRY_REQUEST_BUDGET.can_request():
        raise pipeline_module.PendingRetryBudgetExceededError(
            "Pending Retry Gemini request budget exhausted: "
            f"used={pipeline_module.PENDING_RETRY_REQUEST_BUDGET.used}, "
            f"budget={pipeline_module.PENDING_RETRY_REQUEST_BUDGET.budget}"
        )


def _install_single_retry_owner_client(pipeline_module: Any) -> None:
    if bool(getattr(pipeline_module, _SDK_SINGLE_OWNER_FLAG, False)):
        return

    api_key = str(getattr(pipeline_module, "GEMINI_API_KEY", "") or "").strip()
    if not api_key:
        setattr(pipeline_module, "GEMINI_SDK_RETRY_ATTEMPTS", _SDK_RETRY_ATTEMPTS)
        setattr(pipeline_module, "GEMINI_RETRY_OWNER", "factory")
        return

    genai_module = getattr(pipeline_module, "genai", None)
    client_factory = getattr(genai_module, "Client", None) if genai_module is not None else None
    if not callable(client_factory):
        raise RuntimeError("Run360 requires google.genai.Client to enforce single retry ownership")

    try:
        single_owner_client = client_factory(
            api_key=api_key,
            http_options={"retry_options": {"attempts": _SDK_RETRY_ATTEMPTS}},
        )
    except Exception as exc:
        raise RuntimeError("Run360 failed to create Gemini client with SDK retry disabled") from exc

    pipeline_module.client = single_owner_client
    pipeline_module.GEMINI_SDK_RETRY_ATTEMPTS = _SDK_RETRY_ATTEMPTS
    pipeline_module.GEMINI_RETRY_OWNER = "factory"
    setattr(pipeline_module, _SDK_SINGLE_OWNER_FLAG, True)

    logger = getattr(pipeline_module, "logger", None)
    if logger is not None:
        logger.info(
            "[RUN360 GEMINI RETRY OWNER] owner=factory sdk_attempts=%s sdk_retries=0",
            _SDK_RETRY_ATTEMPTS,
        )


def install(pipeline_module: Any) -> Any:
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return pipeline_module

    required = (
        "_generate_via_chat", "_mark_model_unavailable", "_mark_model_exhausted",
        "_extract_retry_delay", "_is_gemini_transport_timeout", "APIError",
    )
    missing = [name for name in required if not hasattr(pipeline_module, name)]
    if missing:
        raise RuntimeError("Run303 provider resilience missing pipeline contract: " + ", ".join(missing))

    _install_single_retry_owner_client(pipeline_module)

    def call_model_pool_provider_verified(
        prompt: str, config: dict | None, kind: str, reserve: int, pool: list[str],
        deep_dive: bool = False, request_context: str = "", request_origin: str = "new",
    ):
        last_error: Exception | None = None
        excluded = _pending_retry_excluded_models() if _is_pending_retry_origin(request_origin) else frozenset()
        for model_name in pool:
            if model_name in excluded:
                pipeline_module.logger.info(
                    "[RUN374 PENDING RETRY MODEL EXCLUDED] model=%s origin=%s; provider_call=false",
                    model_name, request_origin,
                )
                continue
            if model_name in pipeline_module.SESSION_EXHAUSTED_MODELS or model_name in pipeline_module.SESSION_UNAVAILABLE_MODELS:
                continue
            for attempt in range(2):
                try:
                    if deep_dive:
                        _check_deep_dive_local_budgets(pipeline_module, kind, request_origin)
                        if attempt == 0:
                            time.sleep(max(0, pipeline_module.GEMINI_DEEP_DIVE_CALL_PACING_SECONDS))
                    timeout_seconds = pipeline_module.GEMINI_DEEP_DIVE_CALL_TIMEOUT_SECONDS if deep_dive else pipeline_module.GEMINI_SCREENING_CALL_TIMEOUT_SECONDS
                    with pipeline_module._gemini_call_timeout(timeout_seconds):
                        response = pipeline_module._generate_via_chat(
                            model_name, prompt, config=config, request_kind=kind, reserve=reserve,
                            request_context=request_context, count_as_deep_dive=deep_dive,
                            request_origin=request_origin,
                        )
                    _clear_legacy_503_state(pipeline_module, model_name)
                    return response, model_name
                except pipeline_module.APIError as exc:
                    last_error = exc
                    code = _provider_status_code(exc)
                    quota_type = pipeline_module.classify_gemini_quota_error(exc) if code == 429 else ""
                    if code == 503:
                        pipeline_module.logger.warning(
                            "[PROVIDER HTTP 503] model=%s kind=%s attempt=%s/2 verified=structured_status",
                            model_name, kind, attempt + 1,
                        )
                        if _is_pending_retry_origin(request_origin):
                            pipeline_module.logger.warning(
                                "[RUN355/371 PENDING RETRY 503 FALLBACK] model=%s kind=%s origin=%s; preserve remaining request budget for next model",
                                model_name, kind, request_origin,
                            )
                            pipeline_module._mark_model_unavailable(model_name, "provider_503_pending_retry_budget_preserved")
                            break
                        if attempt == 0:
                            delay = _confirmation_delay(pipeline_module, exc)
                            pipeline_module.logger.warning(
                                "[PROVIDER HTTP 503 RETRY] model=%s kind=%s delay=%ss; one same-model confirmation retry",
                                model_name, kind, delay,
                            )
                            time.sleep(delay)
                            continue
                        pipeline_module.logger.warning(
                            "[PROVIDER HTTP 503 CONFIRMED] model=%s kind=%s consecutive=2; run-local circuit open",
                            model_name, kind,
                        )
                        _mark_confirmed_503(pipeline_module, model_name)
                        break
                    _clear_legacy_503_state(pipeline_module, model_name)
                    if code == 429 and quota_type in {"RPD", "DAILY_TOKEN"}:
                        pipeline_module._mark_model_exhausted(model_name, quota_type)
                        break
                    if code == 404:
                        pipeline_module._mark_model_unavailable(model_name, "404")
                        break
                    if code == 429 and quota_type in {"RPM", "TPM"} and attempt == 0:
                        time.sleep(pipeline_module._extract_retry_delay(exc, 15))
                        continue
                    break
                except (pipeline_module.PendingRetryBudgetExceededError, pipeline_module.DeepDiveRunBudgetExceededError):
                    raise
                except pipeline_module.GeminiBudgetExceededError as exc:
                    last_error = exc
                    _clear_legacy_503_state(pipeline_module, model_name)
                    if "Persistent Gemini model budget exhausted" in str(exc):
                        pipeline_module._mark_model_exhausted(model_name, "persistent safety cap")
                    break
                except pipeline_module.GeminiCallTimeoutError as exc:
                    last_error = exc
                    _clear_legacy_503_state(pipeline_module, model_name)
                    pipeline_module.logger.warning(
                        "[GEMINI TRANSIENT TIMEOUT] model=%s kind=%s error=%s; distinct_from_http_503=true; falling back",
                        model_name, kind, exc,
                    )
                    break
                except Exception as exc:
                    _clear_legacy_503_state(pipeline_module, model_name)
                    if pipeline_module._is_gemini_transport_timeout(exc):
                        last_error = exc
                        pipeline_module.logger.warning(
                            "[GEMINI TRANSIENT TIMEOUT] model=%s kind=%s error=%s; distinct_from_http_503=true; falling back",
                            model_name, kind, exc,
                        )
                        break
                    raise
        raise pipeline_module.NoAvailableModelError("利用可能なGeminiモデルがありません") from last_error

    def call_product_review_pool_provider_verified(prompt: str, request_context: str, request_kind_base: str = "product_review"):
        last_error: Exception | None = None
        structured_repair = request_kind_base == "product_review_retry"
        thinking_level = "low" if structured_repair else "medium"
        max_output_tokens = 5000 if structured_repair else 8000
        for model_name in pipeline_module.DEEP_DIVE_MODEL_POOL:
            if model_name in pipeline_module.SESSION_EXHAUSTED_MODELS or model_name in pipeline_module.SESSION_UNAVAILABLE_MODELS:
                continue
            for attempt in range(2):
                if not pipeline_module.PRODUCT_REVIEW_REQUEST_BUDGET.can_request():
                    raise pipeline_module.ProductReviewBudgetExceededError(pipeline_module.PRODUCT_REVIEW_REQUEST_BUDGET.summary())
                try:
                    if attempt == 0:
                        time.sleep(max(0, pipeline_module.GEMINI_DEEP_DIVE_CALL_PACING_SECONDS))
                    response = pipeline_module._generate_via_chat(
                        model_name, prompt,
                        config={
                            "response_mime_type": "application/json",
                            "response_json_schema": pipeline_module._PRODUCT_REVIEW_RESPONSE_SCHEMA,
                            "thinking_config": {"thinking_level": thinking_level},
                            "max_output_tokens": max_output_tokens,
                        },
                        request_kind=request_kind_base, request_context=request_context,
                        count_as_deep_dive=False, request_origin="product_review",
                    )
                    _clear_legacy_503_state(pipeline_module, model_name)
                    return response, model_name
                except pipeline_module.APIError as exc:
                    last_error = exc
                    code = _provider_status_code(exc)
                    quota_type = pipeline_module.classify_gemini_quota_error(exc) if code == 429 else ""
                    if code == 503:
                        pipeline_module.logger.warning(
                            "[PROVIDER HTTP 503] model=%s kind=%s attempt=%s/2 verified=structured_status",
                            model_name, request_kind_base, attempt + 1,
                        )
                        if attempt == 0:
                            delay = _confirmation_delay(pipeline_module, exc)
                            pipeline_module.logger.warning(
                                "[PROVIDER HTTP 503 RETRY] model=%s kind=%s delay=%ss; one same-model confirmation retry",
                                model_name, request_kind_base, delay,
                            )
                            time.sleep(delay)
                            continue
                        pipeline_module.logger.warning(
                            "[PROVIDER HTTP 503 CONFIRMED] model=%s kind=%s consecutive=2; run-local circuit open",
                            model_name, request_kind_base,
                        )
                        _mark_confirmed_503(pipeline_module, model_name)
                        break
                    _clear_legacy_503_state(pipeline_module, model_name)
                    if code == 429 and quota_type in {"RPD", "DAILY_TOKEN"}:
                        pipeline_module._mark_model_exhausted(model_name, quota_type)
                        break
                    if code == 404:
                        pipeline_module._mark_model_unavailable(model_name, "404")
                        break
                    if code == 429 and quota_type in {"RPM", "TPM"} and attempt == 0:
                        time.sleep(pipeline_module._extract_retry_delay(exc, 15))
                        continue
                    break
                except pipeline_module.GeminiBudgetExceededError as exc:
                    last_error = exc
                    _clear_legacy_503_state(pipeline_module, model_name)
                    if "Persistent Gemini model budget exhausted" in str(exc):
                        pipeline_module._mark_model_exhausted(model_name, "persistent safety cap")
                    break
                except pipeline_module.GeminiCallTimeoutError as exc:
                    last_error = exc
                    _clear_legacy_503_state(pipeline_module, model_name)
                    break
                except Exception as exc:
                    _clear_legacy_503_state(pipeline_module, model_name)
                    if pipeline_module._is_gemini_transport_timeout(exc):
                        last_error = exc
                        break
                    raise
        raise pipeline_module.NoAvailableModelError("Product Reviewに利用可能なGeminiモデルがありません") from last_error

    pipeline_module._call_model_pool = call_model_pool_provider_verified
    pipeline_module._call_product_review_pool = call_product_review_pool_provider_verified
    pipeline_module.provider_status_code = _provider_status_code
    pipeline_module.GEMINI_SDK_RETRY_ATTEMPTS = _SDK_RETRY_ATTEMPTS
    pipeline_module.GEMINI_RETRY_OWNER = "factory"
    setattr(pipeline_module, _INSTALL_FLAG, True)
    return pipeline_module
