"""Expiry-bound operational model exclusion; no quota or permanent pool changes."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone

ENV = "AIIF_GEMINI36_BLOCK_UNTIL"
EXCLUDED_MODELS_ENV = "AIIF_GEMINI_TEMP_EXCLUDED_MODELS"


def active(now=None):
    value = os.environ.get(ENV, "").strip()
    if not value:
        return False
    try:
        deadline = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if deadline.tzinfo is None:
            raise ValueError("timezone required")
    except ValueError as exc:
        raise RuntimeError(f"Invalid {ENV}; refusing provider execution") from exc
    return (now or datetime.now(timezone.utc)) < deadline


def excluded(model, now=None):
    name = str(model or "").strip().lower().removeprefix("models/")
    configured = {x.strip().lower().removeprefix("models/") for x in os.environ.get(EXCLUDED_MODELS_ENV, "").split(",") if x.strip()}
    if any(name == item or name.startswith(item + "-") or name.startswith(item + "/") for item in configured):
        return True
    return active(now) and bool(re.match(r"^gemini-3\.6(?:$|[-/])", name))


def allowed_pool(pool, now=None):
    # Validate the configuration even when an empty pool is supplied.
    active(now)
    return [model for model in pool if not excluded(model, now)]


def assert_allowed(model):
    if excluded(model):
        raise RuntimeError(f"{model} temporarily excluded before quota reservation and SDK send")
