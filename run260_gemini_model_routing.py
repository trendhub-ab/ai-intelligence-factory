"""Run260/261/278/369: bounded, health-aware Gemini article routing.

Business goal
-------------
Maximize Ready yield without weakening Fact/Evidence/Publication/Reader gates and
without increasing the existing Deep Dive request ceiling.

Run369 replaces static "newest model first" routing with Provider Health Routing for
article generation and model-based quality repair. The normal cold-start order is
3.6 -> 3.5 -> 3.7 -> 3.8. After real provider attempts exist, the four article models
are re-ordered by smoothed success rate using attempts from the last 24 hours; when
that window is sparse, the most recent N attempts are used as a backstop. Successful
models move up and 503/timeout/error outcomes move models down. Existing run-local
unavailable/exhausted circuits, persistent RPD budgets, retry ceilings, and every
publication gate remain authoritative.

Health history is operational state only. It stores no prompt/article text and is
best-effort persisted on the existing runtime-state branch. Failure to read/write the
health file never blocks article generation. Quality repair remains bounded to two
distinct models so health routing cannot increase provider-visible fan-out.
"""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

_INSTALLED_ATTR = "_run260_gemini_model_routing_installed"
_ORIGINAL_CALL_ATTR = "_run260_original_call_model_pool"
_ORIGINAL_DEEP_DIVE_ATTR = "_run261_original_call_deep_dive_pool"

# Revenue-first cold start: use the models that have been materially more available in
# recent Production before spending attempts on the newer/high-contention models.
PRIMARY_MODEL = "gemini-3.6-flash"
QUALITY_MODEL = "gemini-3.5-flash"
FALLBACK_MODELS = ("gemini-3.7-flash", "gemini-3.8-flash")
DEFAULT_DEEP_DIVE_POOL = (PRIMARY_MODEL, QUALITY_MODEL, *FALLBACK_MODELS)
DEFAULT_QUALITY_POOL = DEFAULT_DEEP_DIVE_POOL
ARTICLE_MODELS = frozenset(DEFAULT_DEEP_DIVE_POOL)
DEFAULT_FLASH_SAFETY_BUDGET = 18
QUALITY_RETRY_MAX_DISTINCT_MODELS = 2

PROVIDER_HEALTH_STATE_PATH = ".runtime/gemini_provider_health.json"
PROVIDER_HEALTH_SCHEMA_VERSION = 1
PROVIDER_HEALTH_LOOKBACK_HOURS = 24
PROVIDER_HEALTH_RECENT_ATTEMPTS = 20
PROVIDER_HEALTH_MAX_HISTORY = 200


def _dedupe(models: Iterable[str]) -> list[str]:
    out: list[str] = []
    for raw in models:
        model = str(raw or "").strip()
        if model and model not in out:
            out.append(model)
    return out


def _configured_deep_dive_pool(pipeline_module: Any) -> list[str]:
    """Use explicit Production config as an allowlist, with all known article models available."""
    configured = _dedupe(getattr(pipeline_module, "DEEP_DIVE_MODEL_POOL", []) or [])
    # The historical code defaulted to a single 3.6 model when no workflow env existed.
    # Treat that singleton as implicit default, not an operator attempt to disable fallback.
    if configured == ["gemini-3.6-flash"]:
        return list(DEFAULT_DEEP_DIVE_POOL)
    return configured or list(DEFAULT_DEEP_DIVE_POOL)


def _is_quality_repair_kind(kind: str) -> bool:
    value = str(kind or "").strip().lower()
    return value == "quality_retry" or any(
        token in value for token in ("quality_repair", "quality_rescue", "recompose", "reader_repair")
    )


def _replace_pool_argument(args: tuple, kwargs: dict, new_pool: list[str]) -> tuple[tuple, dict]:
    if "pool" in kwargs:
        updated = dict(kwargs)
        updated["pool"] = new_pool
        return args, updated
    if len(args) >= 5:
        values = list(args)
        values[4] = new_pool
        return tuple(values), kwargs
    updated = dict(kwargs)
    updated["pool"] = new_pool
    return args, updated


def _request_kind(args: tuple, kwargs: dict) -> str:
    if "kind" in kwargs:
        return str(kwargs.get("kind") or "")
    return str(args[2] if len(args) >= 3 else "")


def _request_pool(args: tuple, kwargs: dict, fallback: list[str]) -> list[str]:
    if "pool" in kwargs:
        return _dedupe(kwargs.get("pool") or fallback)
    if len(args) >= 5:
        return _dedupe(args[4] or fallback)
    return list(fallback)


def _is_deep_dive_call(args: tuple, kwargs: dict, kind: str) -> bool:
    if _is_quality_repair_kind(kind):
        return True
    if "deep_dive" in kwargs:
        return bool(kwargs.get("deep_dive"))
    return bool(args[5]) if len(args) >= 6 else False


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_health_record(row: Any) -> dict | None:
    if not isinstance(row, dict):
        return None
    model = str(row.get("model") or "").strip()
    outcome = str(row.get("outcome") or "").strip().lower()
    timestamp = _parse_timestamp(row.get("timestamp"))
    if model not in ARTICLE_MODELS or outcome not in {"success", "error"} or timestamp is None:
        return None
    return {
        "timestamp": timestamp.isoformat(),
        "model": model,
        "kind": str(row.get("kind") or "other")[:64],
        "outcome": outcome,
        "error_type": str(row.get("error_type") or "")[:96],
    }


def _health_window(history: Iterable[dict], now: datetime | None = None) -> list[dict]:
    """Use all valid attempts in 24h; if sparse, backfill to recent N attempts."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    lookback_hours = _env_int(
        "GEMINI_PROVIDER_HEALTH_LOOKBACK_HOURS", PROVIDER_HEALTH_LOOKBACK_HOURS, 1, 168
    )
    recent_n = _env_int(
        "GEMINI_PROVIDER_HEALTH_RECENT_ATTEMPTS", PROVIDER_HEALTH_RECENT_ATTEMPTS, 4, 100
    )
    valid: list[tuple[datetime, dict]] = []
    for raw in history:
        row = _normalize_health_record(raw)
        if row is None:
            continue
        ts = _parse_timestamp(row["timestamp"])
        if ts is not None:
            valid.append((ts, row))
    valid.sort(key=lambda item: item[0], reverse=True)
    cutoff = now - timedelta(hours=lookback_hours)
    in_window = [row for ts, row in valid if ts >= cutoff]
    if len(in_window) >= recent_n:
        return in_window
    selected = list(in_window)
    selected_ids = {(row["timestamp"], row["model"], row["kind"], row["outcome"], row["error_type"]) for row in selected}
    for _, row in valid:
        identity = (row["timestamp"], row["model"], row["kind"], row["outcome"], row["error_type"])
        if identity in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(identity)
        if len(selected) >= recent_n:
            break
    return selected


def _model_health_stats(models: Iterable[str], history: Iterable[dict], now: datetime | None = None) -> dict[str, dict]:
    window = _health_window(history, now=now)
    stats: dict[str, dict] = {}
    for model in _dedupe(models):
        rows = [row for row in window if row.get("model") == model]
        attempts = len(rows)
        successes = sum(1 for row in rows if row.get("outcome") == "success")
        errors = attempts - successes
        # Beta(1,1) smoothing avoids one lucky request dominating a model with several
        # real observations while still moving a repeatedly failing model below peers.
        score = (successes + 1.0) / (attempts + 2.0)
        stats[model] = {
            "attempts": attempts,
            "success": successes,
            "error": errors,
            "score": score,
        }
    return stats


def _health_ranked_pool(pool: Iterable[str], history: Iterable[dict], now: datetime | None = None) -> list[str]:
    existing = _dedupe(pool)
    baseline = {model: index for index, model in enumerate(DEFAULT_DEEP_DIVE_POOL)}
    stats = _model_health_stats(existing, history, now=now)
    article = [model for model in existing if model in ARTICLE_MODELS]
    non_article = [model for model in existing if model not in ARTICLE_MODELS]
    article.sort(
        key=lambda model: (
            -float(stats.get(model, {}).get("score", 0.5)),
            -int(stats.get(model, {}).get("attempts", 0)),
            baseline.get(model, len(baseline)),
        )
    )
    return article + non_article


def _bounded_quality_pool(pool: Iterable[str], history: Iterable[dict] = ()) -> list[str]:
    return _health_ranked_pool(pool, history)[:QUALITY_RETRY_MAX_DISTINCT_MODELS]


def _health_state_location(pipeline_module: Any) -> tuple[str, str, str, Any] | None:
    repo = str(os.environ.get("GITHUB_REPOSITORY") or getattr(pipeline_module, "EYECATCH_GITHUB_REPO", "") or "").strip()
    token = str(os.environ.get("GH_PAT") or getattr(pipeline_module, "GH_PAT", "") or "").strip()
    branch = str(
        os.environ.get("AIIF_RUNTIME_STATE_BRANCH")
        or getattr(pipeline_module, "EYECATCH_GITHUB_BRANCH", "")
        or ""
    ).strip()
    http = getattr(pipeline_module, "requests", None)
    if not repo or "/" not in repo or not token or not branch or branch in {"main", "master"} or http is None:
        return None
    return repo, token, branch, http


def _health_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _load_provider_health_history(pipeline_module: Any) -> tuple[list[dict], str]:
    override = getattr(pipeline_module, "PROVIDER_HEALTH_HISTORY_OVERRIDE", None)
    if isinstance(override, list):
        return [row for row in (_normalize_health_record(x) for x in override) if row is not None], ""
    location = _health_state_location(pipeline_module)
    if location is None:
        return [], ""
    repo, token, branch, http = location
    logger = getattr(pipeline_module, "logger", None)
    api_url = f"https://api.github.com/repos/{repo}/contents/{PROVIDER_HEALTH_STATE_PATH}"
    try:
        response = http.get(api_url, headers=_health_headers(token), params={"ref": branch}, timeout=15)
        if int(getattr(response, "status_code", 0) or 0) == 404:
            return [], ""
        if int(getattr(response, "status_code", 0) or 0) != 200:
            if logger is not None:
                logger.warning("[PROVIDER HEALTH READ DEGRADED] HTTP %s", getattr(response, "status_code", "?"))
            return [], ""
        payload = response.json()
        encoded = str(payload.get("content") or "").replace("\n", "")
        decoded = json.loads(base64.b64decode(encoded).decode("utf-8")) if encoded else {}
        raw_history = decoded.get("attempts") if isinstance(decoded, dict) else []
        history = [row for row in (_normalize_health_record(x) for x in (raw_history or [])) if row is not None]
        return history[-PROVIDER_HEALTH_MAX_HISTORY:], str(payload.get("sha") or "")
    except Exception as exc:
        if logger is not None:
            logger.warning("[PROVIDER HEALTH READ DEGRADED] %s", exc)
        return [], ""


def _persist_provider_health_history(pipeline_module: Any) -> None:
    location = _health_state_location(pipeline_module)
    if location is None:
        return
    repo, token, branch, http = location
    logger = getattr(pipeline_module, "logger", None)
    history = list(getattr(pipeline_module, "_provider_health_history", []) or [])[-PROVIDER_HEALTH_MAX_HISTORY:]
    payload_data = {
        "schema_version": PROVIDER_HEALTH_SCHEMA_VERSION,
        "purpose": "Gemini article-model availability routing; no prompt/article content",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "attempts": history,
    }
    encoded = base64.b64encode((json.dumps(payload_data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).decode("ascii")
    api_url = f"https://api.github.com/repos/{repo}/contents/{PROVIDER_HEALTH_STATE_PATH}"
    request_payload = {
        "message": "chore(runtime): update Gemini provider health",
        "content": encoded,
        "branch": branch,
    }
    state_sha = str(getattr(pipeline_module, "_provider_health_state_sha", "") or "")
    if state_sha:
        request_payload["sha"] = state_sha
    try:
        response = http.put(api_url, headers=_health_headers(token), json=request_payload, timeout=20)
        if int(getattr(response, "status_code", 0) or 0) in {200, 201}:
            try:
                content = response.json().get("content") or {}
                new_sha = str(content.get("sha") or "")
                if new_sha:
                    pipeline_module._provider_health_state_sha = new_sha
            except Exception:
                pass
            return
        if logger is not None:
            logger.warning("[PROVIDER HEALTH WRITE DEGRADED] HTTP %s", getattr(response, "status_code", "?"))
    except Exception as exc:
        if logger is not None:
            logger.warning("[PROVIDER HEALTH WRITE DEGRADED] %s", exc)


def _new_audit_rows(pipeline_module: Any, start_index: int) -> list[dict]:
    audit = getattr(pipeline_module, "GEMINI_USAGE_AUDIT", None)
    records = getattr(audit, "records", None)
    if not isinstance(records, list):
        return []
    out: list[dict] = []
    for raw in records[start_index:]:
        row = _normalize_health_record(raw)
        if row is not None:
            out.append(row)
    return out


def _audit_length(pipeline_module: Any) -> int:
    audit = getattr(pipeline_module, "GEMINI_USAGE_AUDIT", None)
    records = getattr(audit, "records", None)
    return len(records) if isinstance(records, list) else 0


def _log_route(pipeline_module: Any, kind: str, pool: list[str]) -> None:
    logger = getattr(pipeline_module, "logger", None)
    if logger is None:
        return
    history = list(getattr(pipeline_module, "_provider_health_history", []) or [])
    stats = _model_health_stats(pool, history)
    summary = ", ".join(
        f"{model}:{stats.get(model, {}).get('success', 0)}/{stats.get(model, {}).get('attempts', 0)}"
        for model in pool if model in ARTICLE_MODELS
    )
    logger.info("[PROVIDER HEALTH ROUTING] kind=%s order=%s health=%s", kind, ">".join(pool), summary or "cold-start")


def install(pipeline_module: Any) -> Any:
    """Install revenue-first, health-aware article routing without changing any gate budget."""
    if bool(getattr(pipeline_module, _INSTALLED_ATTR, False)):
        return pipeline_module
    original = getattr(pipeline_module, "_call_model_pool", None)
    original_deep_dive = getattr(pipeline_module, "_call_deep_dive_pool", None)
    if not callable(original):
        raise RuntimeError("pipeline._call_model_pool is required for Run260")
    if not callable(original_deep_dive):
        raise RuntimeError("pipeline._call_deep_dive_pool is required for Run261")

    configured_pool = _configured_deep_dive_pool(pipeline_module)
    # Historical Run260 always made all four article models available. Preserve that
    # compatibility while changing only their routing order.
    production_pool = _dedupe(list(DEFAULT_DEEP_DIVE_POOL) + configured_pool)
    pipeline_module.DEEP_DIVE_MODEL_POOL = production_pool
    pipeline_module.DEEP_DIVE_MODEL_CANDIDATES = list(production_pool)

    # Preserve the existing Run260 safety-budget behavior exactly: the operator may
    # lower the 3.8 ceiling, never raise it, and the same bounded value applies to 3.7.
    try:
        requested_budget = int(os.environ.get("GEMINI_38_FLASH_DAILY_BUDGET", str(DEFAULT_FLASH_SAFETY_BUDGET)))
    except (TypeError, ValueError):
        requested_budget = DEFAULT_FLASH_SAFETY_BUDGET
    quality_budget = max(0, min(DEFAULT_FLASH_SAFETY_BUDGET, requested_budget))
    model_budgets = getattr(pipeline_module, "MODEL_DAILY_BUDGETS", None)
    if isinstance(model_budgets, dict):
        model_budgets["gemini-3.8-flash"] = quality_budget
        model_budgets["gemini-3.7-flash"] = quality_budget
    persistent = getattr(pipeline_module, "PERSISTENT_GEMINI_COUNTER", None)
    if persistent is not None and isinstance(getattr(persistent, "model_budgets", None), dict):
        persistent.model_budgets["gemini-3.8-flash"] = quality_budget
        persistent.model_budgets["gemini-3.7-flash"] = quality_budget

    history, state_sha = _load_provider_health_history(pipeline_module)
    pipeline_module._provider_health_history = list(history)
    pipeline_module._provider_health_state_sha = state_sha
    setattr(pipeline_module, _ORIGINAL_CALL_ATTR, original)
    setattr(pipeline_module, _ORIGINAL_DEEP_DIVE_ATTR, original_deep_dive)

    def call_model_pool_run260(*args, **kwargs):
        kind = _request_kind(args, kwargs)
        current_pool = _request_pool(args, kwargs, production_pool)
        if not _is_deep_dive_call(args, kwargs, kind):
            return original(*args, **kwargs)
        history_now = list(getattr(pipeline_module, "_provider_health_history", []) or [])
        routed_pool = _health_ranked_pool(current_pool, history_now)
        if _is_quality_repair_kind(kind):
            routed_pool = routed_pool[:QUALITY_RETRY_MAX_DISTINCT_MODELS]
        _log_route(pipeline_module, kind, routed_pool)
        args2, kwargs2 = _replace_pool_argument(args, kwargs, routed_pool)
        audit_start = _audit_length(pipeline_module)
        try:
            return original(*args2, **kwargs2)
        finally:
            new_rows = _new_audit_rows(pipeline_module, audit_start)
            if new_rows:
                merged = list(getattr(pipeline_module, "_provider_health_history", []) or []) + new_rows
                pipeline_module._provider_health_history = merged[-PROVIDER_HEALTH_MAX_HISTORY:]
                _persist_provider_health_history(pipeline_module)

    pipeline_module._call_model_pool = call_model_pool_run260

    def call_deep_dive_pool_run261(
        prompt: str,
        config: dict | None = None,
        kind: str = "deep_dive",
        request_context: str = "",
        request_origin: str = "new",
    ):
        """Keep the live quality-repair path bounded while letting health choose the two models."""
        if not _is_quality_repair_kind(kind):
            return original_deep_dive(
                prompt,
                config,
                kind,
                request_context=request_context,
                request_origin=request_origin,
            )
        history_now = list(getattr(pipeline_module, "_provider_health_history", []) or [])
        quality_pool = _bounded_quality_pool(
            getattr(pipeline_module, "DEEP_DIVE_MODEL_POOL", production_pool), history_now
        )
        return pipeline_module._call_model_pool(
            prompt,
            config,
            kind,
            0,
            quality_pool,
            deep_dive=True,
            request_context=request_context,
            request_origin=request_origin,
        )

    pipeline_module._call_deep_dive_pool = call_deep_dive_pool_run261
    pipeline_module.QUALITY_RETRY_MAX_DISTINCT_MODELS = QUALITY_RETRY_MAX_DISTINCT_MODELS
    pipeline_module.PROVIDER_HEALTH_ROUTING_ENABLED = True
    pipeline_module.PROVIDER_HEALTH_STATE_PATH = PROVIDER_HEALTH_STATE_PATH
    setattr(pipeline_module, _INSTALLED_ATTR, True)
    return pipeline_module
