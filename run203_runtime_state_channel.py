"""Run203: isolate mutable production state from protected main.

Production code is immutable on ``main`` and must continue to move only through PRs.
Machine-generated operational state (Gemini quota counter, deferred queue, source ROI,
observed history, eyecatches and attribution manifests) is mutable by design, so it is
written to a dedicated unprotected runtime-state branch instead.

The preflight intentionally performs a tiny idempotent state write with the same GH_PAT
used by the pipeline. This fails before any Gemini request if the runtime state channel
is missing, protected, or no longer writable.

Run368 hardens the same state channel against one transient GitHub Contents API failure
observed in Production: HTTP 409 ``Timed out validating rule, please try again``. Only
that repository-rule timeout receives a bounded retry. Auth/permission and ordinary
4xx failures remain fail-closed, and Observed-history exhaustion keeps its Telegram
warning instead of being silently treated as success.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, MutableMapping

DEFAULT_RUNTIME_STATE_BRANCH = "runtime-state"
RUNTIME_STATE_HEALTH_PATH = ".runtime/runtime_state_health.json"
_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
_PRODUCTION_BRANCH_NAMES = {"main", "master"}
_RUNTIME_RULE_TIMEOUT_ATTEMPTS = 3
_RUNTIME_RULE_TIMEOUT_DELAYS = (1.0, 2.0)


def _http_client():
    """Load requests only when network preflight actually runs.

    Repository falsification imports this module in a deliberately dependency-light,
    zero-network job. Production already installs requirements.txt before preflight.
    """
    import requests
    return requests


def _is_transient_rule_validation_timeout(response: Any) -> bool:
    """Recognize only the transient GitHub repository-rule timeout seen in Run48."""
    if int(getattr(response, "status_code", 0) or 0) != 409:
        return False
    text = str(getattr(response, "text", "") or "").lower()
    return "timed out validating rule" in text or (
        "repository rule" in text and "timed out" in text and "try again" in text
    )


def _put_with_runtime_rule_retry(http: Any, api_url: str, *, headers: dict, payload: dict,
                                 timeout: int, logger: Any = None, sleep_fn=time.sleep):
    """Retry only transient repository-rule validation timeouts, at most three PUTs."""
    last = None
    for attempt in range(1, _RUNTIME_RULE_TIMEOUT_ATTEMPTS + 1):
        last = http.put(api_url, headers=headers, json=payload, timeout=timeout)
        if int(getattr(last, "status_code", 0) or 0) in {200, 201}:
            return last
        if not _is_transient_rule_validation_timeout(last):
            return last
        if attempt >= _RUNTIME_RULE_TIMEOUT_ATTEMPTS:
            return last
        delay = _RUNTIME_RULE_TIMEOUT_DELAYS[min(attempt - 1, len(_RUNTIME_RULE_TIMEOUT_DELAYS) - 1)]
        if logger is not None:
            logger.warning(
                "[RUNTIME STATE TRANSIENT 409 RETRY] attempt=%s/%s delay=%ss path=%s",
                attempt,
                _RUNTIME_RULE_TIMEOUT_ATTEMPTS,
                delay,
                api_url,
            )
        sleep_fn(delay)
    return last


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


def persist_github_actions_env(branch: str) -> None:
    """Persist state isolation for later steps in the same GitHub Actions job.

    ``production_pipeline.py`` and the separate Product Review step are different
    processes. Appending to ``GITHUB_ENV`` ensures the latter inherits the corrected
    branch even if the historical workflow YAML still says ``main``.
    """
    path = (os.environ.get("GITHUB_ENV") or "").strip()
    if not path or not branch:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"AIIF_RUNTIME_STATE_BRANCH={branch}\n")
        handle.write(f"GEMINI_COUNTER_BRANCH={branch}\n")
        handle.write(f"EYECATCH_GITHUB_BRANCH={branch}\n")


def _install_observed_history_retry(pipeline_module: Any) -> None:
    """Replace only Observed-history persistence with bounded transient-409 recovery."""
    marker = "_run368_observed_history_retry_installed"
    if bool(getattr(pipeline_module, marker, False)):
        return
    original = getattr(pipeline_module, "upload_observed_history_to_github", None)
    if not callable(original):
        return

    def upload_observed_history_with_retry(local_path: str, dest_filename: str) -> str | None:
        repo = str(getattr(pipeline_module, "EYECATCH_GITHUB_REPO", "") or "")
        branch = str(getattr(pipeline_module, "EYECATCH_GITHUB_BRANCH", "") or "")
        target_dir = str(getattr(pipeline_module, "OBSERVED_HISTORY_GITHUB_DIR", "observed_history") or "observed_history")
        token = str(getattr(pipeline_module, "GH_PAT", "") or "")
        logger = getattr(pipeline_module, "logger", None)
        alert = getattr(pipeline_module, "send_telegram_alert", None)
        http = getattr(pipeline_module, "requests", None)
        if not repo or http is None:
            return original(local_path, dest_filename)

        dest_path = f"{target_dir}/{dest_filename}"
        api_url = f"https://api.github.com/repos/{repo}/contents/{dest_path}"
        try:
            with open(local_path, "rb") as handle:
                content_b64 = base64.b64encode(handle.read()).decode("utf-8")
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
            current = http.get(api_url, headers=headers, params={"ref": branch}, timeout=15)
            payload = {
                "message": f"chore: save observed history {dest_filename}",
                "content": content_b64,
                "branch": branch,
            }
            if current.status_code == 200:
                sha = current.json().get("sha")
                if sha:
                    payload["sha"] = sha

            put_res = _put_with_runtime_rule_retry(
                http,
                api_url,
                headers=headers,
                payload=payload,
                timeout=30,
                logger=logger,
            )
            if int(getattr(put_res, "status_code", 0) or 0) not in {200, 201}:
                if logger is not None:
                    logger.error("[OBSERVED UPLOAD FAILED] %s: %s", dest_filename, str(getattr(put_res, "text", ""))[:300])
                if callable(alert):
                    alert(f"⚠️ Observed履歴のGitHub保存に失敗しました: {dest_filename}")
                return None
            return f"https://raw.githubusercontent.com/{repo}/{branch}/{dest_path}"
        except Exception as exc:
            if logger is not None:
                logger.error("[OBSERVED UPLOAD EXCEPTION] %s", exc)
            if callable(alert):
                alert(f"⚠️ Observed履歴のGitHub保存で例外が発生しました: {dest_filename}")
            return None

    pipeline_module.upload_observed_history_to_github = upload_observed_history_with_retry
    setattr(pipeline_module, marker, True)


def install(pipeline_module: Any) -> Any:
    """Redirect every existing mutable GitHub state writer to the runtime-state branch."""
    branch = apply_runtime_state_env()
    if not branch:
        return pipeline_module
    persist_github_actions_env(branch)

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

    _install_observed_history_retry(pipeline_module)
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

    http = _http_client()
    headers = _headers(token)
    branch_url = f"https://api.github.com/repos/{repo}/branches/{branch}"
    branch_res = http.get(branch_url, headers=headers, timeout=15)
    if branch_res.status_code != 200:
        raise RuntimeError(
            f"Runtime-state branch is not readable: HTTP {branch_res.status_code} {branch_res.text[:200]}"
        )

    api_url = f"https://api.github.com/repos/{repo}/contents/{RUNTIME_STATE_HEALTH_PATH}"
    current = http.get(api_url, headers=headers, params={"ref": branch}, timeout=15)
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

    put_res = _put_with_runtime_rule_retry(http, api_url, headers=headers, payload=payload, timeout=20)
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
