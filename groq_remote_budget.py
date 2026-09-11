"""GitHub-backed atomic reservation for serialized, bounded Groq experiments.

The pre-existing ledger is never initialized, deleted, or reset by this code.
GitHub's file SHA is the compare-and-swap token. A conflict aborts before Groq.
An experiment ID may be sent once, even after the rolling window expires.
"""
import base64
import json
import time
import urllib.request
from ai_provider import ProviderError

REPOSITORY = "trendhub-ab/ai-intelligence-factory"
BRANCH = "runtime/groq-validation"
PATH = ".runtime/groq_validation_ledger.json"


def reserve_state(state, experiment, tokens, now):
    if not isinstance(state, dict) or state.get("version") != 1 or not isinstance(state.get("attempts"), list):
        raise ProviderError("invalid_remote_ledger")
    if not isinstance(experiment, str) or not experiment or type(tokens) is not int or not 1 <= tokens <= 8000:
        raise ProviderError("invalid_remote_reservation")
    recent = []
    for row in state["attempts"]:
        if not isinstance(row, dict) or not isinstance(row.get("experiment"), str):
            raise ProviderError("invalid_remote_ledger")
        if type(row.get("tokens")) is not int or not 1 <= row["tokens"] <= 8000:
            raise ProviderError("invalid_remote_ledger")
        if type(row.get("stamp")) not in {int, float} or not 0 <= row["stamp"] <= now:
            raise ProviderError("invalid_remote_ledger")
        if row["experiment"] == experiment:
            raise ProviderError("experiment_already_reserved")
        if row["stamp"] > now - 86400:
            recent.append(row)
    if len(recent) >= 3 or sum(row["tokens"] for row in recent) + tokens > 24000:
        raise ProviderError("persistent_validation_budget_exceeded")
    if recent and now - max(row["stamp"] for row in recent) < 65:
        raise ProviderError("validation_pacing_required")
    return {"version": 1, "attempts": state["attempts"] + [{"experiment": experiment, "stamp": now, "tokens": tokens}]}


def reserve_remote(token, experiment, tokens, opener):
    endpoint = f"https://api.github.com/repos/{REPOSITORY}/contents/{PATH}"
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "User-Agent": "AI-Intelligence-Factory/1.0", "Content-Type": "application/json"}
    req = urllib.request.Request(endpoint + "?ref=" + BRANCH, headers=headers)
    with opener.open(req, timeout=30) as response:
        file = json.load(response)
    state = json.loads(base64.b64decode(file["content"]))
    updated = reserve_state(state, experiment, tokens, time.time())
    data = {"message": "Reserve bounded Groq experiment before provider call", "branch": BRANCH,
            "sha": file["sha"], "content": base64.b64encode(json.dumps(updated).encode()).decode()}
    req = urllib.request.Request(endpoint, headers=headers, data=json.dumps(data).encode(), method="PUT")
    with opener.open(req, timeout=30) as response:
        if response.status != 200:
            raise ProviderError("remote_reservation_failed")
