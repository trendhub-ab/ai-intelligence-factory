"""Runtime-state persistence for Hybrid PENDING_WRITER records.

Operational state is stored on the existing isolated runtime-state branch, never on
protected Production main and never in Notion/note. Network access is lazy and injectable
so all regression tests remain offline.
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from typing import Any

from hybrid_writer_deferred import validate_pending_writer_record
from run203_runtime_state_channel import resolve_runtime_state_branch

_STATE_ROOT = ".runtime/hybrid_pending_writers"
_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
_CAS_ATTEMPTS = 3


class PendingWriterStateError(RuntimeError):
    pass


def pending_writer_state_path(candidate_id: str) -> str:
    value = str(candidate_id or "").strip()
    if not _ID_RE.fullmatch(value):
        raise PendingWriterStateError("pending_writer_candidate_id_invalid")
    return f"{_STATE_ROOT}/{value}.json"


def _runtime_identity() -> tuple[str, str, str]:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GH_PAT", "").strip()
    branch = resolve_runtime_state_branch()
    if not repo or "/" not in repo:
        raise PendingWriterStateError("pending_writer_repository_missing")
    if not token:
        raise PendingWriterStateError("pending_writer_token_missing")
    if not branch or branch in {"main", "master"}:
        raise PendingWriterStateError("pending_writer_runtime_branch_invalid")
    return repo, token, branch


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _http_client():
    import requests
    return requests


def load_pending_writer_state(candidate_id: str, *, http: Any = None) -> dict | None:
    repo, token, branch = _runtime_identity()
    client = http or _http_client()
    path = pending_writer_state_path(candidate_id)
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    res = client.get(url, headers=_headers(token), params={"ref": branch}, timeout=15)
    if res.status_code == 404:
        return None
    if res.status_code != 200:
        raise PendingWriterStateError(f"pending_writer_state_read_http_{res.status_code}")
    try:
        raw = base64.b64decode(res.json()["content"]).decode("utf-8")
        record = json.loads(raw)
    except Exception:
        raise PendingWriterStateError("pending_writer_state_decode_failed") from None
    validate_pending_writer_record(record, allow_not_ready=True)
    record["_content_sha"] = str(res.json().get("sha") or "")
    return record


def save_pending_writer_state(record: dict, *, http: Any = None) -> dict:
    validate_pending_writer_record(record, allow_not_ready=True)
    repo, token, branch = _runtime_identity()
    client = http or _http_client()
    candidate_id = str(record["candidate_id"])
    path = pending_writer_state_path(candidate_id)
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    clean = {k: v for k, v in record.items() if not str(k).startswith("_")}
    encoded = base64.b64encode((json.dumps(clean, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).decode("ascii")

    last_status = None
    for attempt in range(_CAS_ATTEMPTS):
        current = client.get(url, headers=_headers(token), params={"ref": branch}, timeout=15)
        if current.status_code not in {200, 404}:
            raise PendingWriterStateError(f"pending_writer_state_read_http_{current.status_code}")
        payload = {
            "message": f"chore(runtime): defer Hybrid writer {candidate_id}",
            "content": encoded,
            "branch": branch,
        }
        if current.status_code == 200:
            sha = current.json().get("sha")
            if sha:
                payload["sha"] = sha
        put = client.put(url, headers=_headers(token), json=payload, timeout=20)
        last_status = put.status_code
        if put.status_code in {200, 201}:
            return {"repo": repo, "branch": branch, "path": path, "candidate_id": candidate_id}
        if put.status_code not in {409, 422} or attempt >= _CAS_ATTEMPTS - 1:
            raise PendingWriterStateError(f"pending_writer_state_write_http_{put.status_code}")
        time.sleep(0.15)
    raise PendingWriterStateError(f"pending_writer_state_write_http_{last_status}")


def delete_pending_writer_state(candidate_id: str, *, http: Any = None) -> bool:
    repo, token, branch = _runtime_identity()
    client = http or _http_client()
    path = pending_writer_state_path(candidate_id)
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    current = client.get(url, headers=_headers(token), params={"ref": branch}, timeout=15)
    if current.status_code == 404:
        return False
    if current.status_code != 200 or not current.json().get("sha"):
        raise PendingWriterStateError(f"pending_writer_state_delete_read_http_{current.status_code}")
    res = client.delete(
        url,
        headers=_headers(token),
        json={
            "message": f"chore(runtime): clear Hybrid writer {candidate_id}",
            "sha": current.json()["sha"],
            "branch": branch,
        },
        timeout=20,
    )
    if res.status_code != 200:
        raise PendingWriterStateError(f"pending_writer_state_delete_http_{res.status_code}")
    return True
