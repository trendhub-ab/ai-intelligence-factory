"""Run372 shared stability guard for non-arXiv discovery transports.

ArXiv has a provider-specific persistent controller because its official metadata API
requires explicit pacing and showed repeated 429s in Production.  The other discovery
sources fail differently, but share one safety requirement: an upstream outage must
not be amplified into repeated network calls, long Daily stalls, or a misleading
"zero candidates" success.

This module is transport-only.  It never changes candidate scoring, source authority,
Evidence/Fact/Publication gates, article text, or persistence policy.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


OVERLOAD_STATUSES = frozenset({429, 503})
TRANSIENT_STATUSES = frozenset({500, 502, 504})
BLOCKED_STATUSES = frozenset({403})
DEFAULT_CACHE_TTL_SECONDS = 15 * 60
DEFAULT_CACHE_MAX_ENTRIES = 128
DEFAULT_TRANSIENT_RETRY_DELAY_SECONDS = 1.0
_INSTALL_FLAG = "_aiif_source_stability_installed"


class SourceCircuitOpenError(RuntimeError):
    """Raised locally after a source/host circuit is already open."""


@dataclass
class _CacheRow:
    stored_at: float
    response: Any


class _StatusOverrideResponse:
    """Preserve the real response body while exposing a degraded HTTP status.

    GitHub GraphQL may return HTTP 200 with an ``errors`` payload.  The historical
    collector only checked HTTP status and could therefore report a normal zero-item
    collection.  For a no-data GraphQL error, expose 503 to the existing collector so
    it follows its already-established fault-isolation path instead.
    """

    def __init__(self, response: Any, status_code: int, reason: str):
        self._response = response
        self.status_code = int(status_code)
        self.reason = str(reason or "source degraded")
        original_text = str(getattr(response, "text", "") or "")
        self.text = (self.reason + ("; " + original_text if original_text else ""))[:4000]
        self.headers = getattr(response, "headers", {})
        self.url = getattr(response, "url", "")
        self.content = getattr(response, "content", b"")

    def json(self):
        return self._response.json()

    def raise_for_status(self):
        raise RuntimeError(f"HTTP {self.status_code}: {self.reason}")

    def __getattr__(self, name: str):
        return getattr(self._response, name)


class RequestsSourceStabilityProxy:
    """Requests-compatible proxy protecting HN, OfficialVendor, and GitHub discovery."""

    def __init__(
        self,
        delegate: Any,
        *,
        logger: Any = None,
        vendor_hosts: set[str] | None = None,
        now_fn=time.time,
        sleep_fn=time.sleep,
    ) -> None:
        self._delegate = delegate
        self.logger = logger
        self.vendor_hosts = {str(host).lower().rstrip(".") for host in (vendor_hosts or set()) if host}
        self.now_fn = now_fn
        self.sleep_fn = sleep_fn
        self.cache_ttl = DEFAULT_CACHE_TTL_SECONDS
        self.cache_max_entries = DEFAULT_CACHE_MAX_ENTRIES
        self.retry_delay = DEFAULT_TRANSIENT_RETRY_DELAY_SECONDS
        self._circuits: dict[str, dict[str, Any]] = {}
        self._cache: dict[str, _CacheRow] = {}
        self._stats = {
            "network_calls": 0,
            "cache_hits": 0,
            "circuit_skips": 0,
            "circuits_opened": 0,
            "github_graphql_degraded": 0,
        }

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)

    def _log(self, level: str, message: str, *args) -> None:
        target = getattr(self.logger, level, None) if self.logger is not None else None
        if callable(target):
            target(message, *args)

    @staticmethod
    def _host(url: str) -> str:
        return (urlparse(str(url or "")).hostname or "").lower().rstrip(".")

    def _scope(self, method: str, url: str) -> tuple[str, str] | None:
        host = self._host(url)
        path = urlparse(str(url or "")).path or ""
        if host == "hn.algolia.com":
            return "HackerNews", "source:hackernews-algolia"
        if method == "POST" and host == "api.github.com" and path.rstrip("/") == "/graphql":
            return "GitHub", "source:github-graphql"
        if host in self.vendor_hosts or host == "docs-api.cn-beijing.volces.com":
            return "OfficialVendor", f"host:{host}"
        return None

    @staticmethod
    def _stable_value(value: Any) -> str:
        if value is None:
            return ""
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        except Exception:
            return repr(value)

    def _cache_key(self, method: str, url: str, kwargs: dict[str, Any]) -> str:
        # Headers are intentionally excluded: these discovery endpoints return the same
        # public representation for our callers, while auth-bearing values must never be
        # copied into cache keys/logs.
        return "|".join(
            [
                method,
                str(url or ""),
                self._stable_value(kwargs.get("params")),
                self._stable_value(kwargs.get("json")),
            ]
        )

    def _cached(self, key: str):
        row = self._cache.get(key)
        if row is None:
            return None
        if float(self.now_fn()) - row.stored_at > self.cache_ttl:
            self._cache.pop(key, None)
            return None
        self._stats["cache_hits"] += 1
        return row.response

    def _store_cache(self, key: str, response: Any) -> None:
        if int(getattr(response, "status_code", 0) or 0) != 200:
            return
        self._cache[key] = _CacheRow(float(self.now_fn()), response)
        if len(self._cache) <= self.cache_max_entries:
            return
        oldest = sorted(self._cache.items(), key=lambda item: item[1].stored_at)
        for cache_key, _ in oldest[: len(self._cache) - self.cache_max_entries]:
            self._cache.pop(cache_key, None)

    def _open_circuit(self, source: str, scope: str, status: int | str) -> None:
        if scope in self._circuits:
            return
        self._circuits[scope] = {"source": source, "status": status, "opened_at": float(self.now_fn())}
        self._stats["circuits_opened"] += 1
        self._log(
            "warning",
            "[SOURCE STABILITY CIRCUIT OPEN] source=%s scope=%s status=%s",
            source,
            scope,
            status,
        )

    def _raise_if_open(self, source: str, scope: str) -> None:
        row = self._circuits.get(scope)
        if row is None:
            return
        self._stats["circuit_skips"] += 1
        self._log(
            "warning",
            "[SOURCE STABILITY CIRCUIT SKIP] source=%s scope=%s status=%s",
            source,
            scope,
            row.get("status"),
        )
        raise SourceCircuitOpenError(f"{source} circuit open ({row.get('status')})")

    def _network(self, method: str, url: str, kwargs: dict[str, Any]):
        fn = getattr(self._delegate, method.lower())
        self._stats["network_calls"] += 1
        return fn(url, **kwargs)

    def _request_protected(self, method: str, url: str, kwargs: dict[str, Any]):
        classification = self._scope(method, url)
        if classification is None:
            return self._network(method, url, kwargs)
        source, scope = classification
        key = self._cache_key(method, url, kwargs)
        cached = self._cached(key)
        if cached is not None:
            self._log("info", "[SOURCE STABILITY CACHE HIT] source=%s scope=%s", source, scope)
            return cached
        self._raise_if_open(source, scope)

        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                response = self._network(method, url, kwargs)
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    self.sleep_fn(self.retry_delay)
                    continue
                self._open_circuit(source, scope, type(exc).__name__)
                raise

            status = int(getattr(response, "status_code", 0) or 0)
            if status == 200:
                if source == "GitHub":
                    response = self._normalize_github_graphql(response)
                    status = int(getattr(response, "status_code", 0) or 0)
                    if status != 200:
                        self._open_circuit(source, scope, "graphql_errors")
                        return response
                self._store_cache(key, response)
                return response

            if status in OVERLOAD_STATUSES or status in BLOCKED_STATUSES:
                self._open_circuit(source, scope, status)
                return response
            if status in TRANSIENT_STATUSES and attempt == 0:
                self.sleep_fn(self.retry_delay)
                continue
            if status in TRANSIENT_STATUSES:
                self._open_circuit(source, scope, status)
            return response

        if last_exc is not None:
            raise last_exc
        raise RuntimeError(f"{source} protected request ended without a response")

    def _normalize_github_graphql(self, response: Any):
        try:
            payload = response.json()
        except Exception:
            return response
        if not isinstance(payload, dict) or not payload.get("errors"):
            return response
        search = (payload.get("data") or {}).get("search") if isinstance(payload.get("data"), dict) else None
        nodes = search.get("nodes") if isinstance(search, dict) else None
        if nodes:
            self._log(
                "warning",
                "[SOURCE STABILITY GITHUB PARTIAL] GraphQL errors present but %s nodes remain usable",
                len(nodes),
            )
            return response
        self._stats["github_graphql_degraded"] += 1
        messages = [str(row.get("message") or "") for row in payload.get("errors", []) if isinstance(row, dict)]
        reason = "GitHub GraphQL returned errors without usable search nodes"
        if messages:
            reason += ": " + " | ".join(messages)[:500]
        self._log("warning", "[SOURCE STABILITY GITHUB DEGRADED] %s", reason)
        return _StatusOverrideResponse(response, 503, reason)

    def get(self, url: str, *args, **kwargs):
        if args:
            return self._delegate.get(url, *args, **kwargs)
        return self._request_protected("GET", url, dict(kwargs))

    def post(self, url: str, *args, **kwargs):
        if args:
            return self._delegate.post(url, *args, **kwargs)
        return self._request_protected("POST", url, dict(kwargs))

    def snapshot(self) -> dict[str, Any]:
        return {
            **self._stats,
            "open_circuits": {scope: dict(row) for scope, row in self._circuits.items()},
            "cache_entries": len(self._cache),
        }


def _official_vendor_hosts() -> set[str]:
    """Resolve only the exact configured release hosts; do not broaden by domain suffix."""
    hosts: set[str] = set()
    try:
        from run269_vendor_current_state import OFFICIAL_VENDOR_REGISTRY

        for row in OFFICIAL_VENDOR_REGISTRY:
            if not isinstance(row, dict):
                continue
            for key in ("release_url", "current_state_fetch_url"):
                host = (urlparse(str(row.get(key) or "")).hostname or "").lower().rstrip(".")
                if host:
                    hosts.add(host)
    except Exception:
        # The overlay remains safe when imported by tiny/static test doubles.  In that
        # case HN/GitHub protection still works and vendor traffic simply delegates.
        pass
    return hosts


def install(pipeline_module: Any) -> Any:
    """Install the proxy early enough that later Run269 closures use it dynamically."""
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return pipeline_module
    delegate = getattr(pipeline_module, "requests", None)
    if delegate is None or not callable(getattr(delegate, "get", None)) or not callable(getattr(delegate, "post", None)):
        return pipeline_module

    proxy = RequestsSourceStabilityProxy(
        delegate,
        logger=getattr(pipeline_module, "logger", None),
        vendor_hosts=_official_vendor_hosts(),
    )
    pipeline_module.requests = proxy
    pipeline_module.SOURCE_STABILITY_CONTROLLER = proxy
    setattr(pipeline_module, _INSTALL_FLAG, True)
    logger = getattr(pipeline_module, "logger", None)
    if logger is not None:
        logger.info(
            "[SOURCE STABILITY INSTALLED] hn=source-circuit github=graphql-aware vendor_hosts=%s",
            len(proxy.vendor_hosts),
        )
    return pipeline_module
