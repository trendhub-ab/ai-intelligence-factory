"""Run203: isolate mutable production state from protected main.

Production code is immutable on ``main`` and must continue to move only through PRs.
Machine-generated operational state (Gemini quota counter, deferred queue, source ROI,
observed history, eyecatches and attribution manifests) is mutable by design, so it is
written to a dedicated unprotected runtime-state branch instead.

The preflight intentionally performs a tiny idempotent state write with the same GH_PAT
used by the pipeline. This fails before any Gemini request if the runtime state channel
is missing, protected, or no longer writable.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, MutableMapping

import requests

DEFAULT_RUNTIME_STATE_BRANCH = "runtime-state"
RUNTIME_STATE_HEALTH_PATH = ".runtime/runtime_state_health.json"
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_PRODUCTION_BRANCH_NAMES = {"main", "master"}


def resolve_runtime_state_branch() -> str:
    """Resolve the mutable-state branch without trusting legacy ``main`` settings.

    Run201 protected the default branch after older workflows had already hard-coded
    ``GEMINI_COUNTER_BRANCH=main``. Treat those legacy values as stale configuration in
    GitHub Actions and migrate them to ``runtime-state`` rather than weakening main.
    An explicit ``AIIF_RUNTIME_STATE_BRANCH=main`` remains a hard failure.
    """
    explicit = (os.environ.get("AIIF_RUNTIME_STATE_BRANCH") or "").strip()
    legacy = (
        os.environ.get("GEMINI_COUNTER_BRANCH")
        or os.environ.get("EYECATCH_GITHUB_BRANCH")
        or ""
    ).strip()
    in_actions = os.environ.get("GITHUB_ACTIONS", "").lower() == "true"
    synthetic = os.environ.get("SYNTHETIC_REGRESSION_MODE", "").lower() in {"1", "true", "yes", "on"}

    if explicit:
        branch = explicit
    elif legacy and legacy not in _PRODUCTION_BRANCH_NAMES:
        branch = legacy
    elif in_actions and not synthetic:
        branch = DEFAULT_RUNTIME_STATE_BRANCH
    else:
        # Local/synthetic imports remain side-effect free. Production GitHub Actions
        # always resolve a concrete isolated state branch.
        return ""

    if branch in _PRODUCTION_BRANCH_NAMES:
        raise RuntimeError("AIIF runtime state must never target the protected production branch")
    if branch.startswith("refs/") or not _BRANCH_RE.fullmatch(branch):
        raise RuntimeError(f"Invalid AIIF runtime state branch: {branch!r}")
    return branch


def apply_runtime_state_env(env: MutableMapping[str, str] | None = None) -> str:
    """Stamp child-process env so direct ``pipeline.py`` invocations use state isolation."""
    target = env if env is not None else os.environ
    branch = resolve_runtime_state_branch()
    if not branch:
        return ""
    target["AIIF_RUNTIME_STATE_BRANCH"] = branch
    target["GEMINI_COUNTER_BRANCH"] = branch
    target["EYECATCH_GITHUB_BRANCH"] = branch
    return branch


def install(pipeline_module: Any) -> Any:
    """Redirect every existing mutable GitHub state writer to the runtime-state branch."""
    branch = apply_runtime_state_env()
    if not branch:
        return pipeline_module

    # Existing state writers in pipeline.py share EYECATCH_GITHUB_BRANCH for their
    # Contents API target. Redirecting this runtime variable covers eyecatches,
    # observed history, deferred queue, source ROI and subscription attribution.
    pipeline_module.EYECATCH_GITHUB_BRANCH = branch
    pipeline_module.GEMINI_COUNTER_BRANCH = branch

    # The persistent counter object is constructed when pipeline.py is imported, so
    # update the already-created object as well. This is the key fix for the Run202
    # symptom where reservation failed with main-protection HTTP 409 before any API call.
    counter = getattr(pipeline_module, "PERSISTENT_GEMINI_COUNTER", None)
    if counter is not None:
        counter.branch = branch
    return pipeline_module


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def preflight_runtime_state_channel() -> dict[str, str]:
    """Prove the state branch is writable before the first Gemini reservation."""
    branch = resolve_runtime_state_branch()
    if not branch:
        raise RuntimeError("Runtime-state preflight requires an explicit production branch")

    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GH_PAT", "").strip()
    if not repo or "/" not in repo:
        raise RuntimeError("GITHUB_REPOSITORY is required for runtime-state preflight")
    if not token:
        raise RuntimeError("GH_PAT is required for runtime-state preflight")

    headers = _headers(token)
    branch_url = f"https://api.github.com/repos/{repo}/branches/{branch}"
    branch_res = requests.get(branch_url, headers=headers, timeout=15)
    if branch_res.status_code != 200:
        raise RuntimeError(
            f"Runtime-state branch is not readable: HTTP {branch_res.status_code} {branch_res.text[:200]}"
        )

    api_url = f"https://api.github.com/repos/{repo}/contents/{RUNTIME_STATE_HEALTH_PATH}"
    current = requests.get(api_url, headers=headers, params={"ref": branch}, timeout=15)
    if current.status_code not in {200, 404}:
        raise RuntimeError(
            f"Runtime-state health read failed: HTTP {current.status_code} {current.text[:200]}"
        )

    payload_data = {
        "schema_version": 1,
        "purpose": "prove mutable runtime state is isolated from protected main",
        "branch": branch,
        "run_id": os.environ.get("GITHUB_RUN_ID", ""),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    content = base64.b64encode(
        (json.dumps(payload_data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    ).decode("ascii")
    payload: dict[str, str] = {
        "message": "chore(runtime): verify writable state channel",
        "content": content,
        "branch": branch,
    }
    if current.status_code == 200:
        sha = current.json().get("sha")
        if sha:
            payload["sha"] = sha

    put_res = requests.put(api_url, headers=headers, json=payload, timeout=20)
    if put_res.status_code not in {200, 201}:
        raise RuntimeError(
            f"Runtime-state write preflight failed: HTTP {put_res.status_code} {put_res.text[:300]}"
        )

    return {"repo": repo, "branch": branch, "path": RUNTIME_STATE_HEALTH_PATH}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if not args.preflight:
        parser.error("--preflight is required")
    result = preflight_runtime_state_channel()
    print(
        "[RUN203 RUNTIME STATE PREFLIGHT] "
        f"repo={result['repo']} branch={result['branch']} path={result['path']}"
    )


if __name__ == "__main__":
    main()
