"""Encrypted, optional cross-run eyecatch copy cache on the public runtime-state branch.

Never upload unpublished title/summary/article/copy in plaintext.  The encrypted
record and its HMAC-obscured path can be published without revealing the copy.
Only an explicitly provisioned Fernet secret activates the remote channel.
This is an optimization, never an alternative to the publication quality gate.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)
SCHEMA_VERSION = 1
RUNTIME_BRANCH = "runtime-state"
PATH_PREFIX = ".runtime/eyecatch_copy_v1"
_REPO_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class EyecatchCopyStore:
    def __init__(self, *, env: dict | None = None, http: Any = None):
        config = os.environ if env is None else env
        self.repo = str(config.get("GITHUB_REPOSITORY") or "").strip()
        self.branch = str(config.get("AIIF_RUNTIME_STATE_BRANCH") or RUNTIME_BRANCH).strip()
        self.token = str(
            config.get("AIIF_RUNTIME_STATE_GITHUB_TOKEN") or config.get("GH_PAT") or ""
        ).strip()
        self.key = str(config.get("AIIF_EYECATCH_COPY_FERNET_KEY") or "").strip()
        self._cipher = None
        if (
            self.key
            and self.token
            and _REPO_PATTERN.fullmatch(self.repo)
            and self.branch == RUNTIME_BRANCH
            and str(config.get("SYNTHETIC_REGRESSION_MODE") or "").lower()
            not in {"1", "true", "yes", "on"}
        ):
            try:
                from cryptography.fernet import Fernet
                self._cipher = Fernet(self.key.encode("ascii"))
            except (ImportError, ValueError, TypeError, UnicodeError):
                logger.warning("[EYECATCH COPY STATE] encryption unavailable; remote cache disabled")
        self.http = http
        if self._cipher is not None and self.http is None:
            import requests
            self.http = requests

    @property
    def enabled(self) -> bool:
        return self._cipher is not None and self.http is not None

    @staticmethod
    def source_digest(title: str, summary: str, article_text: str = "") -> str:
        canonical = json.dumps(
            [SCHEMA_VERSION, title, summary, article_text],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _path(self, digest: str) -> str:
        # Fernet key is secret and stable across runs. No article identifiers in URLs.
        opaque = hmac.new(self.key.encode("ascii"), digest.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{PATH_PREFIX}/{opaque[:2]}/{opaque}.json"

    def _url(self, digest: str) -> str:
        return f"https://api.github.com/repos/{self.repo}/contents/{self._path(digest)}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _read(self, digest: str) -> tuple[dict | None, str | None, int]:
        res = self.http.get(
            self._url(digest), headers=self._headers(), params={"ref": RUNTIME_BRANCH}, timeout=15
        )
        status = int(res.status_code)
        if status == 404:
            return None, None, status
        if status != 200:
            logger.warning("[EYECATCH COPY STATE] read unavailable, status=%s", status)
            return None, None, status
        try:
            payload = res.json()
            encoded = str(payload["content"]).replace("\n", "")
            ciphertext = base64.b64decode(encoded, validate=True)
            clear = self._cipher.decrypt(ciphertext)
            stored = json.loads(clear)
            if (
                not isinstance(stored, dict)
                or stored.get("schema_version") != SCHEMA_VERSION
                or stored.get("source_digest") != digest
                or not isinstance(stored.get("plan"), dict)
            ):
                raise ValueError("cache identity or shape mismatch")
            sha = str(payload.get("sha") or "")
            return stored["plan"], sha, status
        except (ValueError, TypeError, KeyError, UnicodeError, Exception) as exc:
            # Deliberately do not log decrypted content, title, or exception payload.
            logger.warning("[EYECATCH COPY STATE] encrypted record invalid (%s)", type(exc).__name__)
            return None, None, status

    def load(self, title: str, summary: str, article_text: str = "") -> dict | None:
        if not self.enabled:
            return None
        try:
            plan, _, _ = self._read(self.source_digest(title, summary, article_text))
            return plan
        except Exception as exc:
            logger.warning("[EYECATCH COPY STATE] read failed (%s)", type(exc).__name__)
            return None

    def save(self, title: str, summary: str, plan: dict, article_text: str = "") -> bool:
        if not self.enabled:
            return False
        digest = self.source_digest(title, summary, article_text)
        try:
            existing, sha, status = self._read(digest)
            if existing is not None:
                # First successfully committed copy wins for this exact input.
                return True
            # Never turn read failures, corruption, or permissions into blind overwrites.
            if status != 404:
                return False
            clear = json.dumps(
                {"schema_version": SCHEMA_VERSION, "source_digest": digest, "plan": plan},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            sealed = self._cipher.encrypt(clear)
            payload = {
                "branch": RUNTIME_BRANCH,
                "message": "chore(runtime): persist encrypted eyecatch copy",
                "content": base64.b64encode(sealed).decode("ascii"),
            }
            result = self.http.put(self._url(digest), headers=self._headers(), json=payload, timeout=20)
            if int(result.status_code) in {200, 201}:
                return True
            if int(result.status_code) == 409:
                # Competing run may have created the same key. Never overwrite.
                winner, _, winner_status = self._read(digest)
                return winner_status == 200 and winner is not None
            logger.warning("[EYECATCH COPY STATE] write unavailable, status=%s", result.status_code)
            return False
        except Exception as exc:
            logger.warning("[EYECATCH COPY STATE] write failed (%s)", type(exc).__name__)
            return False
