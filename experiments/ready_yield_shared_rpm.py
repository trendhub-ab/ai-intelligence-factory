"""CAS-backed RPM reservations for a bounded, fixed-Evidence experiment."""
from __future__ import annotations

import math
import base64
import json
import requests


class RPMConflict(RuntimeError):
    """Another run updated the reservation ledger first."""


class RPMUnavailable(RuntimeError):
    """The reservation ledger cannot establish a safe send slot."""


class GitHubRPMStore:
    """One operational ledger on runtime-state; never write the main branch."""
    PATH = ".runtime/ready_yield_rpm.json"

    def __init__(self, repository: str, token: str, *, branch: str):
        if branch != "runtime-state" or not token or repository.count("/") != 1:
            raise RPMUnavailable("RPM store requires runtime-state, repository, and token")
        self.url = f"https://api.github.com/repos/{repository}/contents/{self.PATH}"
        self.branch = branch
        self.headers = {"Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28"}

    def read(self) -> tuple[dict, str | None]:
        try:
            response = requests.get(self.url, headers=self.headers,
                                    params={"ref": self.branch}, timeout=12)
            if response.status_code == 404:
                return {}, None
            if response.status_code != 200:
                raise RPMUnavailable(f"RPM state read failed: HTTP {response.status_code}")
            payload = response.json()
            state = json.loads(base64.b64decode(payload["content"]).decode("utf-8"))
            if not isinstance(state, dict) or not payload.get("sha"):
                raise RPMUnavailable("Invalid RPM state or blob SHA")
            return state, payload["sha"]
        except RPMUnavailable:
            raise
        except Exception as exc:
            raise RPMUnavailable(f"RPM state read unavailable: {type(exc).__name__}") from exc

    def write(self, state: dict, sha: str | None) -> None:
        payload = {
            "branch": self.branch,
            "message": "chore: reserve bounded experiment RPM slot",
            "content": base64.b64encode(json.dumps(state, sort_keys=True).encode()).decode(),
        }
        if sha:
            payload["sha"] = sha
        try:
            response = requests.put(self.url, headers=self.headers, json=payload, timeout=15)
        except Exception as exc:
            raise RPMUnavailable(f"RPM state write unavailable: {type(exc).__name__}") from exc
        if response.status_code in (409, 422):
            raise RPMConflict("RPM state changed concurrently")
        if response.status_code not in (200, 201):
            raise RPMUnavailable(f"RPM state write failed: HTTP {response.status_code}")


class SharedRPM:
    ALLOWED_MODELS = frozenset(("gemini-3.6-flash", "gemini-3.5-flash"))

    def __init__(self, store, project_scope: str):
        self.store = store
        self.project_scope = str(project_scope or "").strip()

    def reserve(self, model: str, now: float) -> float:
        """Return seconds to wait, or 0 after an atomic pre-send reservation."""
        if not self.project_scope or model not in self.ALLOWED_MODELS:
            raise RPMUnavailable("Missing project scope or unverified model RPM")
        if not math.isfinite(now) or now < 0:
            raise RPMUnavailable("Invalid wall clock")
        for _ in range(3):
            data, sha = self.store.read()
            if not isinstance(data, dict):
                raise RPMUnavailable("Unparseable RPM state")
            if data and data.get("scope") != self.project_scope:
                raise RPMUnavailable("RPM project scope mismatch")
            attempts = data.get("attempts", [])
            if not isinstance(attempts, list):
                raise RPMUnavailable("Unparseable RPM attempt ledger")
            clean = []
            for row in attempts:
                if not isinstance(row, dict) or row.get("model") not in self.ALLOWED_MODELS:
                    raise RPMUnavailable("Invalid RPM attempt record")
                timestamp = row.get("at")
                if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) \
                        or not math.isfinite(timestamp) or timestamp > now:
                    raise RPMUnavailable("Invalid or future RPM timestamp")
                if now - timestamp < 60:
                    clean.append({"model": row["model"], "at": timestamp})
            delay = max((row["at"] + 25 - now for row in clean), default=0)
            by_model = [row for row in clean if row["model"] == model]
            if len(by_model) >= 3:
                delay = max(delay, min(row["at"] for row in by_model) + 60 - now)
            if delay > 0:
                return delay
            updated = {"scope": self.project_scope,
                       "attempts": clean + [{"model": model, "at": now}]}
            try:
                self.store.write(updated, sha)
                return 0
            except RPMConflict:
                continue
        raise RPMUnavailable("RPM reservation contention did not settle")
