"""Pure pending-writer policy for the Hybrid Groq -> Gemini runtime.

A Gemini availability outage must not discard completed Groq preprocessing or stop the
whole Daily run. This module is deliberately provider/network/persistence free. It only
creates and validates bounded PENDING_WRITER records that a later run may retry.

Only provider availability failures (HTTP 503/404) are deferrable. Quality failures,
client errors, auth errors and malformed output are never converted into availability
retries. That prevents hidden retry loops from consuming the free tier.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json

PENDING_WRITER = "PENDING_WRITER"
WRITER_READY = "WRITER_READY"
WRITER_EXPIRED = "WRITER_EXPIRED"
WRITER_MAX_RETRY_CYCLES = 3
WRITER_COOLDOWN_HOURS = 4
WRITER_TTL_HOURS = 48
DEFERRABLE_HTTP_STATUS = frozenset({503, 404})


class PendingWriterError(RuntimeError):
    pass


def _utc(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise PendingWriterError("pending_writer_now_must_be_timezone_aware")
    return value.astimezone(timezone.utc)


def _stable_payload_hash(fixture: dict) -> str:
    immutable = {
        "candidate_id": fixture.get("candidate_id"),
        "plan_provider": fixture.get("plan_provider"),
        "plan_source": fixture.get("plan_source"),
        "writer_models": fixture.get("writer_models"),
        "writer_prompt": fixture.get("writer_prompt"),
    }
    raw = json.dumps(immutable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _attempts_are_availability_only(provider_report: dict) -> bool:
    attempts = provider_report.get("attempts")
    if not isinstance(attempts, list) or not 1 <= len(attempts) <= 2:
        return False
    for row in attempts:
        if not isinstance(row, dict) or row.get("status") != "error":
            return False
        try:
            status = int(row.get("http_status"))
        except (TypeError, ValueError):
            return False
        if status not in DEFERRABLE_HTTP_STATUS:
            return False
    return True


def build_pending_writer_record(
    fixture: dict,
    provider_report: dict,
    *,
    previous: dict | None = None,
    now: datetime | None = None,
) -> dict:
    """Create the next bounded availability retry record, or fail closed.

    One retry cycle corresponds to one Hybrid writer run (max two Gemini calls: 3.7 then
    3.8). A successful provider response or any non-availability failure cannot enter
    this queue.
    """
    if not isinstance(fixture, dict) or not fixture.get("candidate_id"):
        raise PendingWriterError("pending_writer_fixture_invalid")
    if fixture.get("business_writes") != 0 or fixture.get("persist_results") is not False:
        raise PendingWriterError("pending_writer_fixture_not_read_only")
    if not _attempts_are_availability_only(provider_report):
        raise PendingWriterError("pending_writer_nonavailability_failure")
    if provider_report.get("text"):
        raise PendingWriterError("pending_writer_success_cannot_defer")

    current = _utc(now)
    previous_cycles = 0
    created_at = current
    if previous is not None:
        validate_pending_writer_record(previous, now=current, allow_not_ready=True)
        if previous.get("candidate_id") != fixture.get("candidate_id"):
            raise PendingWriterError("pending_writer_candidate_mismatch")
        if previous.get("payload_hash") != _stable_payload_hash(fixture):
            raise PendingWriterError("pending_writer_payload_changed")
        previous_cycles = int(previous.get("retry_cycles") or 0)
        created_at = datetime.fromisoformat(str(previous["created_at"]).replace("Z", "+00:00")).astimezone(timezone.utc)

    retry_cycles = previous_cycles + 1
    if retry_cycles > WRITER_MAX_RETRY_CYCLES:
        raise PendingWriterError("pending_writer_retry_budget_exhausted")
    expires_at = created_at + timedelta(hours=WRITER_TTL_HOURS)
    if current >= expires_at:
        raise PendingWriterError("pending_writer_expired")

    return {
        "version": 1,
        "status": PENDING_WRITER,
        "candidate_id": fixture["candidate_id"],
        "payload_hash": _stable_payload_hash(fixture),
        "created_at": created_at.isoformat(),
        "updated_at": current.isoformat(),
        "retry_after": (current + timedelta(hours=WRITER_COOLDOWN_HOURS)).isoformat(),
        "expires_at": expires_at.isoformat(),
        "retry_cycles": retry_cycles,
        "max_retry_cycles": WRITER_MAX_RETRY_CYCLES,
        "last_attempts": list(provider_report["attempts"]),
        "reason": "gemini_writer_temporarily_unavailable",
        "business_writes": 0,
        "persist_results": False,
    }


def validate_pending_writer_record(
    record: dict,
    *,
    now: datetime | None = None,
    allow_not_ready: bool = False,
) -> str:
    if not isinstance(record, dict) or record.get("version") != 1:
        raise PendingWriterError("pending_writer_record_invalid")
    if record.get("status") != PENDING_WRITER or not record.get("candidate_id"):
        raise PendingWriterError("pending_writer_record_invalid")
    if record.get("business_writes") != 0 or record.get("persist_results") is not False:
        raise PendingWriterError("pending_writer_record_not_read_only")
    try:
        cycles = int(record.get("retry_cycles"))
        maximum = int(record.get("max_retry_cycles"))
        retry_after = datetime.fromisoformat(str(record["retry_after"]).replace("Z", "+00:00")).astimezone(timezone.utc)
        expires_at = datetime.fromisoformat(str(record["expires_at"]).replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        raise PendingWriterError("pending_writer_record_invalid") from None
    if not 1 <= cycles <= WRITER_MAX_RETRY_CYCLES or maximum != WRITER_MAX_RETRY_CYCLES:
        raise PendingWriterError("pending_writer_retry_budget_invalid")
    current = _utc(now)
    if current >= expires_at:
        return WRITER_EXPIRED
    if current < retry_after:
        if allow_not_ready:
            return PENDING_WRITER
        raise PendingWriterError("pending_writer_cooldown_active")
    return WRITER_READY
