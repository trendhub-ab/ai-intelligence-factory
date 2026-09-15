"""Shared arXiv API stability transport for Production.

Run371 addresses a real Production failure pattern observed in ONE-SHOT Run #58:
``export.arxiv.org`` returned 429/timeout responses, while the legacy helper retried
three times in Main, Evidence Health, and the separate Product Review process. That
multiplied provider pressure and consumed minutes without improving freshness.

This layer changes transport behavior only. It does not alter candidate scoring,
Evidence/Fact/Publication gates, article content, or Product Review policy.

Contracts:
- pace arXiv metadata API network requests at >=4 seconds by default;
- cache successful metadata responses for 24 hours on ``runtime-state``;
- bound the entire persisted cache state so GitHub Contents state cannot grow without
  limit as successful arXiv responses accumulate;
- share the last-request timestamp and overload circuit across processes in the same
  GitHub Actions run;
- one 429 or 503 opens the metadata circuit for the rest of that Actions run;
- fresh cache hits are still allowed while the circuit is open;
- non-overload transport/5xx failures receive at most one bounded retry;
- persistence failure is fail-open for the Factory, but never causes extra arXiv
  retries by itself.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

STATE_PATH = ".runtime/arxiv_stability_state.json"
SCHEMA_VERSION = 1
DEFAULT_MIN_INTERVAL_SECONDS = 4.0
DEFAULT_CACHE_TTL_SECONDS = 24 * 60 * 60
DEFAULT_CACHE_MAX_ENTRIES = 40
DEFAULT_CACHE_BODY_MAX_BYTES = 250_000
DEFAULT_CACHE_STATE_MAX_BYTES = 700_000
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
DEFAULT_TRANSIENT_RETRY_DELAY_SECONDS = 10.0
OVERLOAD_STATUSES = frozenset({429, 503})
_INSTALL_FLAG = "_aiif_arxiv_stability_installed"


def _env_float(name: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(maximum, value))


def _cache_key(url: str, params: dict | None) -> str:
    payload = json.dumps(
        {"url": str(url or ""), "params": dict(params or {})},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _required_delay(last_request_epoch: float, now_epoch: float, min_interval_seconds: float) -> float:
    if last_request_epoch <= 0:
        return 0.0
    return max(0.0, float(min_interval_seconds) - max(0.0, float(now_epoch) - float(last_request_epoch)))


def _circuit_open_for_run(state: dict, run_id: str) -> bool:
    return bool(run_id and str(state.get("circuit_run_id") or "") == str(run_id))


class _CachedResponse:
    def __init__(self, body: bytes, url: str):
        self.status_code = 200
        self.content = bytes(body)
        self.text = self.content.decode("utf-8", errors="replace")
        self.url = str(url or "")
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None


class ArxivStabilityController:
    def __init__(
        self,
        *,
        http: Any,
        logger: Any = None,
        repo: str = "",
        token: str = "",
        runtime_branch: str = "",
        run_id: str = "",
        put_with_retry: Callable[..., Any] | None = None,
        now_fn: Callable[[], float] = time.time,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.http = http
        self.logger = logger
        self.repo = str(repo or "").strip()
        self.token = str(token or "").strip()
        self.runtime_branch = str(runtime_branch or "").strip()
        self.run_id = str(run_id or "").strip()
        self.put_with_retry = put_with_retry
        self.now_fn = now_fn
        self.sleep_fn = sleep_fn
        self.min_interval = _env_float(
            "AIIF_ARXIV_MIN_INTERVAL_SECONDS", DEFAULT_MIN_INTERVAL_SECONDS, 3.0, 60.0
        )
        self.cache_ttl = _env_int(
            "AIIF_ARXIV_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS, 60, 7 * 24 * 60 * 60
        )
        self.cache_max_entries = _env_int(
            "AIIF_ARXIV_CACHE_MAX_ENTRIES", DEFAULT_CACHE_MAX_ENTRIES, 4, 100
        )
        self.cache_body_max_bytes = _env_int(
            "AIIF_ARXIV_CACHE_BODY_MAX_BYTES", DEFAULT_CACHE_BODY_MAX_BYTES, 10_000, 900_000
        )
        self.cache_state_max_bytes = _env_int(
            "AIIF_ARXIV_CACHE_STATE_MAX_BYTES", DEFAULT_CACHE_STATE_MAX_BYTES, 100_000, 900_000
        )
        self.timeout = _env_int(
            "AIIF_ARXIV_REQUEST_TIMEOUT_SECONDS", DEFAULT_REQUEST_TIMEOUT_SECONDS, 5, 60
        )
        self.retry_delay = _env_float(
            "AIIF_ARXIV_TRANSIENT_RETRY_DELAY_SECONDS",
            DEFAULT_TRANSIENT_RETRY_DELAY_SECONDS,
            4.0,
            60.0,
        )
        self._lock = threading.Lock()
        self._state = self._empty_state()
        self._state_loaded = False
        self._local_last_request_epoch = 0.0

    @staticmethod
    def _empty_state() -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "updated_at": "",
            "last_request_at_epoch": 0.0,
            "last_status": 0,
            "last_error_type": "",
            "circuit_run_id": "",
            "circuit_status": 0,
            "circuit_opened_at": "",
            "entries": {},
        }

    @property
    def persistence_enabled(self) -> bool:
        return bool(
            self.repo
            and "/" in self.repo
            and self.token
            and self.runtime_branch
            and self.runtime_branch not in {"main", "master"}
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _api_url(self) -> str:
        return f"https://api.github.com/repos/{self.repo}/contents/{STATE_PATH}"

    def _log(self, level: str, message: str, *args) -> None:
        target = getattr(self.logger, level, None) if self.logger is not None else None
        if callable(target):
            target(message, *args)

    def _decode_remote_state(self, response: Any) -> dict:
        try:
            payload = response.json()
            encoded = str(payload.get("content") or "").replace("\n", "")
            if not encoded:
                return self._empty_state()
            decoded = base64.b64decode(encoded).decode("utf-8")
            state = json.loads(decoded)
            if int(state.get("schema_version") or 0) != SCHEMA_VERSION:
                return self._empty_state()
            if not isinstance(state.get("entries"), dict):
                state["entries"] = {}
            return state
        except Exception as exc:
            self._log("warning", "[ARXIV STABILITY STATE DEGRADED] decode failed: %s", exc)
            return self._empty_state()

    def _load_remote_state(self, *, force: bool = False) -> dict:
        if self._state_loaded and not force:
            return self._state
        if not self.persistence_enabled:
            self._state_loaded = True
            return self._state
        try:
            response = self.http.get(
                self._api_url(),
                headers=self._headers(),
                params={"ref": self.runtime_branch},
                timeout=15,
            )
            if int(getattr(response, "status_code", 0) or 0) == 200:
                self._state = self._decode_remote_state(response)
            elif int(getattr(response, "status_code", 0) or 0) == 404:
                self._state = self._empty_state()
            else:
                self._log(
                    "warning",
                    "[ARXIV STABILITY STATE DEGRADED] read HTTP %s; using process-local state",
                    getattr(response, "status_code", 0),
                )
        except Exception as exc:
            self._log("warning", "[ARXIV STABILITY STATE DEGRADED] read failed: %s", exc)
        self._state_loaded = True
        self._prune_entries()
        return self._state

    def _state_size_bytes(self) -> int:
        return len(
            json.dumps(
                self._state,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )

    def _prune_entries(self) -> None:
        entries = self._state.setdefault("entries", {})
        if not isinstance(entries, dict):
            self._state["entries"] = {}
            return
        now = float(self.now_fn())
        valid: list[tuple[str, dict]] = []
        for key, row in entries.items():
            if not isinstance(row, dict):
                continue
            fetched = float(row.get("fetched_at_epoch") or 0.0)
            if fetched <= 0 or now - fetched > self.cache_ttl:
                continue
            valid.append((str(key), row))
        valid.sort(key=lambda item: float(item[1].get("fetched_at_epoch") or 0.0), reverse=True)
        candidates = valid[: self.cache_max_entries]
        selected: dict[str, dict] = {}
        dropped_for_size = 0
        for key, row in candidates:
            selected[key] = row
            self._state["entries"] = selected
            if self._state_size_bytes() > self.cache_state_max_bytes:
                selected.pop(key, None)
                dropped_for_size += 1
                break
        # Once the next-newest entry does not fit, every older entry is lower priority.
        # Count and discard the remainder rather than allowing future state growth to
        # depend on entry ordering or GitHub Contents payload limits.
        if dropped_for_size:
            dropped_for_size += max(0, len(candidates) - len(selected) - 1)
        self._state["entries"] = dict(selected)
        if dropped_for_size:
            self._log(
                "info",
                "[ARXIV STABILITY CACHE PRUNE] dropped=%s state_bytes=%s max=%s",
                dropped_for_size,
                self._state_size_bytes(),
                self.cache_state_max_bytes,
            )

    def _save_remote_state(self) -> None:
        self._state["schema_version"] = SCHEMA_VERSION
        self._state["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._prune_entries()
        if not self.persistence_enabled:
            return
        try:
            api_url = self._api_url()
            headers = self._headers()
            current = self.http.get(
                api_url,
                headers=headers,
                params={"ref": self.runtime_branch},
                timeout=15,
            )
            payload: dict[str, Any] = {
                "message": "chore(runtime): update arXiv stability state",
                "content": base64.b64encode(
                    (json.dumps(self._state, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
                ).decode("ascii"),
                "branch": self.runtime_branch,
            }
            if int(getattr(current, "status_code", 0) or 0) == 200:
                sha = current.json().get("sha")
                if sha:
                    payload["sha"] = sha
            if callable(self.put_with_retry):
                written = self.put_with_retry(
                    self.http,
                    api_url,
                    headers=headers,
                    payload=payload,
                    timeout=20,
                    logger=self.logger,
                    sleep_fn=self.sleep_fn,
                )
            else:
                written = self.http.put(api_url, headers=headers, json=payload, timeout=20)
            if int(getattr(written, "status_code", 0) or 0) not in {200, 201}:
                self._log(
                    "warning",
                    "[ARXIV STABILITY STATE DEGRADED] write HTTP %s; transport remains fail-open",
                    getattr(written, "status_code", 0),
                )
        except Exception as exc:
            self._log("warning", "[ARXIV STABILITY STATE DEGRADED] write failed: %s", exc)

    def _cached(self, url: str, params: dict | None) -> _CachedResponse | None:
        state = self._load_remote_state()
        row = state.get("entries", {}).get(_cache_key(url, params))
        if not isinstance(row, dict):
            return None
        fetched = float(row.get("fetched_at_epoch") or 0.0)
        if fetched <= 0 or float(self.now_fn()) - fetched > self.cache_ttl:
            return None
        try:
            body = base64.b64decode(str(row.get("body_b64") or ""))
        except Exception:
            return None
        if not body:
            return None
        age = max(0.0, float(self.now_fn()) - fetched)
        self._log("info", "[ARXIV STABILITY CACHE HIT] age=%.1fs key=%s", age, _cache_key(url, params)[:12])
        return _CachedResponse(body, url)

    def _cache_success(self, url: str, params: dict | None, body: bytes) -> None:
        if not body or len(body) > self.cache_body_max_bytes:
            if body:
                self._log(
                    "info",
                    "[ARXIV STABILITY CACHE BYPASS] body_bytes=%s max=%s",
                    len(body),
                    self.cache_body_max_bytes,
                )
            return
        self._state.setdefault("entries", {})[_cache_key(url, params)] = {
            "fetched_at_epoch": float(self.now_fn()),
            "body_b64": base64.b64encode(body).decode("ascii"),
        }
        self._save_remote_state()

    def _reserve_request_slot(self) -> None:
        # Refresh before every network miss so a later Product Review process sees the
        # latest Main/Evidence-Health reservation instead of relying on stale startup state.
        self._load_remote_state(force=True)
        last_remote = float(self._state.get("last_request_at_epoch") or 0.0)
        last_seen = max(last_remote, self._local_last_request_epoch)
        now = float(self.now_fn())
        delay = _required_delay(last_seen, now, self.min_interval)
        if delay > 0:
            self._log("info", "[ARXIV STABILITY PACE] sleep=%.2fs", delay)
            self.sleep_fn(delay)
            now = float(self.now_fn())
        self._local_last_request_epoch = now
        self._state["last_request_at_epoch"] = now
        # Persist before the network call. This lets later processes observe the slot
        # even when the current arXiv request hangs or times out.
        self._save_remote_state()

    def _open_circuit(self, status: int) -> None:
        self._state["circuit_run_id"] = self.run_id or "process-local"
        self._state["circuit_status"] = int(status)
        self._state["circuit_opened_at"] = datetime.now(timezone.utc).isoformat()
        self._state["last_status"] = int(status)
        self._save_remote_state()
        self._log(
            "warning",
            "[ARXIV STABILITY CIRCUIT OPEN] status=%s run_id=%s; further metadata calls deferred",
            status,
            self.run_id or "process-local",
        )

    def _circuit_is_open(self) -> bool:
        self._load_remote_state(force=True)
        if self.run_id:
            return _circuit_open_for_run(self._state, self.run_id)
        return str(self._state.get("circuit_run_id") or "") == "process-local"

    def fetch(self, url: str, params: dict | None):
        with self._lock:
            cached = self._cached(url, params)
            if cached is not None:
                return cached

            if self._circuit_is_open():
                self._log(
                    "warning",
                    "[ARXIV STABILITY CIRCUIT SKIP] status=%s key=%s",
                    self._state.get("circuit_status", 0),
                    _cache_key(url, params)[:12],
                )
                return None

            last_error: Exception | None = None
            for attempt in range(2):
                self._reserve_request_slot()
                try:
                    response = self.http.get(url, params=params, timeout=self.timeout)
                except Exception as exc:
                    last_error = exc
                    self._state["last_error_type"] = type(exc).__name__[:80]
                    self._save_remote_state()
                    self._log(
                        "warning",
                        "[ARXIV STABILITY TRANSIENT] attempt=%s/2 error=%s",
                        attempt + 1,
                        exc,
                    )
                    if attempt == 0:
                        self.sleep_fn(max(self.min_interval, self.retry_delay))
                        continue
                    return None

                status = int(getattr(response, "status_code", 0) or 0)
                self._state["last_status"] = status
                self._state["last_error_type"] = ""
                if status == 200:
                    body = bytes(getattr(response, "content", b"") or b"")
                    self._cache_success(url, params, body)
                    self._log(
                        "info",
                        "[ARXIV STABILITY NETWORK] status=200 bytes=%s key=%s",
                        len(body),
                        _cache_key(url, params)[:12],
                    )
                    return response

                if status in OVERLOAD_STATUSES:
                    self._open_circuit(status)
                    return None

                if status >= 500 and attempt == 0:
                    self._log(
                        "warning",
                        "[ARXIV STABILITY TRANSIENT] status=%s attempt=1/2",
                        status,
                    )
                    self.sleep_fn(max(self.min_interval, self.retry_delay))
                    continue

                self._save_remote_state()
                self._log(
                    "warning",
                    "[ARXIV STABILITY FETCH FAILED] status=%s attempts=%s",
                    status,
                    attempt + 1,
                )
                return None

            if last_error is not None:
                self._log("warning", "[ARXIV STABILITY FETCH FAILED] error=%s", last_error)
            return None


def install(
    pipeline_module: Any,
    *,
    runtime_branch: str = "",
    put_with_retry: Callable[..., Any] | None = None,
) -> Any:
    """Replace the legacy arXiv retry helper with one shared bounded transport."""
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return pipeline_module
    original = getattr(pipeline_module, "_fetch_arxiv_with_retry", None)
    http = getattr(pipeline_module, "requests", None)
    if not callable(original) or http is None:
        return pipeline_module

    controller = ArxivStabilityController(
        http=http,
        logger=getattr(pipeline_module, "logger", None),
        repo=os.environ.get("GITHUB_REPOSITORY", ""),
        token=str(getattr(pipeline_module, "GH_PAT", "") or os.environ.get("GH_PAT", "")),
        runtime_branch=str(runtime_branch or os.environ.get("AIIF_RUNTIME_STATE_BRANCH", "")),
        run_id=os.environ.get("GITHUB_RUN_ID", ""),
        put_with_retry=put_with_retry,
    )
    pipeline_module._fetch_arxiv_with_retry = controller.fetch
    pipeline_module.ARXIV_STABILITY_MIN_INTERVAL_SECONDS = controller.min_interval
    pipeline_module.ARXIV_STABILITY_CACHE_TTL_SECONDS = controller.cache_ttl
    pipeline_module.ARXIV_STABILITY_CACHE_STATE_MAX_BYTES = controller.cache_state_max_bytes
    pipeline_module.ARXIV_STABILITY_STATE_PATH = STATE_PATH
    pipeline_module._ARXIV_STABILITY_CONTROLLER = controller
    setattr(pipeline_module, _INSTALL_FLAG, True)
    if getattr(pipeline_module, "logger", None) is not None:
        pipeline_module.logger.info(
            "[ARXIV STABILITY INSTALLED] interval=%.1fs cache_ttl=%ss state_max=%sB state_branch=%s",
            controller.min_interval,
            controller.cache_ttl,
            controller.cache_state_max_bytes,
            controller.runtime_branch or "process-local",
        )
    return pipeline_module
