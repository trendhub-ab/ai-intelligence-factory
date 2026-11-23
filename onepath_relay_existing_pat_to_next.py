#!/usr/bin/env python3
"""Explicit owner-Issue one-shot: copy existing OLD GH_PAT into NEXT GitHub Secret.

Do not emit the token, URLs bearing credentials, response bodies, key or
encrypted value to logs. GitHub's public key encrypts the PAT via NaCl sealed
box before it is sent to the API; no plaintext PAT is committed or uploaded.
This expands the scope in which the EXISTING owner PAT is available; the
operator must approve the actual one-shot Issue separately from merging code.

Do not run model/VM/Notion/note. Fail closed for any ambiguous write.
"""
from __future__ import annotations
import base64
import binascii
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

OLD = "trendhub-ab/ai-intelligence-factory"
NEXT = "trendhub-ab/ai-intelligence-factory-next"
OWNER = "trendhub-ab"
TITLE = "AIIF OLD: APPROVE ONEPATH RELAY EXISTING PAT TO NEXT"
BODY = "OWNER_APPROVES_ENCRYPTED_EXISTING_GH_PAT_RELAY_V1"
TARGET = f"/repos/{NEXT}/actions/secrets/GH_PAT"
GITHUB_PUBLIC_KEY = f"/repos/{NEXT}/actions/secrets/public-key"
BASE = "https://api.github.com"


class RelayStopped(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def require_owner(event: dict, env: dict) -> None:
    issue, repo, sender = event.get("issue"), event.get("repository"), event.get("sender")
    if (type(issue) is not dict or type(issue.get("user")) is not dict
            or type(repo) is not dict or type(sender) is not dict
            or event.get("action") != "opened"
            or issue.get("title") != TITLE
            or issue.get("body") != BODY
            or issue["user"].get("login") != OWNER
            or sender.get("login") != OWNER
            or repo.get("full_name") != OLD
            or repo.get("private") is not False
            or env.get("GITHUB_REPOSITORY") != OLD
            or env.get("GITHUB_ACTOR") != OWNER
            or env.get("GITHUB_EVENT_NAME") != "issues"
            or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("GITHUB_RUN_ATTEMPT") != "1"
            or type(env.get("GITHUB_RUN_ID")) is not str
            or not re.fullmatch(r"[0-9]{6,20}", env["GITHUB_RUN_ID"])
            or env.get("OLD_OWNER_PAT_PRESENT") != "true"):
        raise RelayStopped("RELAY_OWNER_GATE_FAILED")


def sealed_pat(pat: str, public_b64: str) -> str:
    """Encrypt into a GitHub-native sealed-box; never log or return plaintext."""
    if type(pat) is not str or len(pat) < 16 or "\n" in pat or "\r" in pat:
        raise RelayStopped("RELAY_PAT_INVALID")
    try:
        from nacl.public import PublicKey, SealedBox
        pub = base64.b64decode(public_b64, validate=True)
        if len(pub) != 32:
            raise ValueError("invalid pub length")
        cipher = SealedBox(PublicKey(pub)).encrypt(pat.encode("utf-8"))
        return base64.b64encode(cipher).decode("ascii")
    except (ValueError, binascii.Error, TypeError):
        raise RelayStopped("RELAY_ENCRYPTION_FAILED") from None


def _send(method: str, path: str, pat: str, payload: dict | None = None) -> tuple[int, dict]:
    if (method, path) not in {
        ("GET", TARGET), ("GET", GITHUB_PUBLIC_KEY), ("PUT", TARGET)
    } or (method == "PUT") != (type(payload) is dict):
        raise RelayStopped("RELAY_API_FORBIDDEN")
    if method == "PUT" and (
        set(payload) != {"encrypted_value", "key_id"} or
        any(type(x) is not str or not x for x in payload.values())
    ):
        raise RelayStopped("RELAY_API_PAYLOAD_INVALID")
    req = Request(
        BASE + path,
        method=method,
        data=(json.dumps(payload, separators=(",", ":")).encode("utf-8") if payload else None),
        headers={
            "Authorization": "Bearer " + pat,
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AIIF-OnePath-Owner-Pat-Relay",
        },
    )
    try:
        with build_opener(_NoRedirect()).open(req, timeout=20) as response:
            status = response.status
            body = response.read(100_001)
        if len(body) > 100_000:
            raise RelayStopped("RELAY_RESPONSE_OVERSIZE")
        parsed = json.loads(body) if body else {}
        if type(parsed) is not dict:
            raise RelayStopped("RELAY_RESPONSE_INVALID")
        return status, parsed
    except HTTPError as e:
        # Only exact 404 on target-secret GET is an absence proof.
        if method == "GET" and path == TARGET and e.code == 404:
            return 404, {}
        raise RelayStopped("RELAY_HTTP_REJECTED") from None
    except (URLError, TimeoutError, OSError, ValueError, UnicodeError):
        raise RelayStopped("RELAY_HTTP_UNKNOWN_STOP") from None


def transfer_once(event: dict, env: dict, transport=_send) -> dict:
    require_owner(event, env)
    pat = env.get("OLD_OWNER_PAT", "")
    if type(pat) is not str or len(pat) < 16 or "\n" in pat or "\r" in pat:
        raise RelayStopped("RELAY_PAT_MISSING")
    status, _ = transport("GET", TARGET, pat)
    if status != 404:
        raise RelayStopped("RELAY_TARGET_SECRET_ALREADY_EXISTS_OR_UNCERTAIN")
    status, key = transport("GET", GITHUB_PUBLIC_KEY, pat)
    if status != 200 or type(key.get("key")) is not str or type(key.get("key_id")) is not str:
        raise RelayStopped("RELAY_PUBLIC_KEY_NOT_VERIFIED")
    payload = {"key_id": key["key_id"], "encrypted_value": sealed_pat(pat, key["key"])}
    status, _ = transport("PUT", TARGET, pat, payload)
    if status not in (201, 204):
        raise RelayStopped("RELAY_WRITE_UNKNOWN_STOP")
    status, metadata = transport("GET", TARGET, pat)
    if status != 200 or metadata.get("name") != "GH_PAT":
        raise RelayStopped("RELAY_READBACK_UNKNOWN_STOP")
    return {
        "status": "NEXT_GH_PAT_METADATA_VERIFIED",
        "old_pat_plaintext_printed": False,
        "secret_write_attempts": 1,
        "model_calls": 0,
        "vm_starts": 0,
        "notion_writes": 0,
        "note_writes": 0,
        "auto_schedule_enabled": False,
    }


def main() -> int:
    try:
        path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
        if not path.is_file() or path.stat().st_size > 100_000:
            raise RelayStopped("RELAY_EVENT_UNAVAILABLE")
        event = json.loads(path.read_text(encoding="utf-8"))
        result = transfer_once(event, dict(os.environ))
        print(json.dumps(result, sort_keys=True))
        return 0
    except (RelayStopped, OSError, ValueError, TypeError, KeyError) as exc:
        code = str(exc)
        if re.fullmatch(r"RELAY_[A-Z0-9_]+", code) is None:
            code = "RELAY_UNKNOWN_STOP"
        print(json.dumps({"status": "RELAY_STOP", "reason": code}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
