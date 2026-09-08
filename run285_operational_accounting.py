"""Run285 zero-API operational accounting and evidence observability.

Run284 Production recovery proved that two operational summaries could hide useful state:
- Note Ready classified an allowed-source Ready row with missing queue fields by silently
  continuing, so the category totals did not explain every source Ready row.
- Current-policy Ready recovery could persist Pending Retry / Editorial Review / Quality Failed
  while its historical ``generated`` counter stayed zero because the generator intentionally
  returned a falsy value on non-accepted outcomes.

This module does not alter publication gates, evidence sufficiency, model routing, retry budgets,
article bytes, or persistence decisions.  It only provides deterministic accounting helpers and
an idempotent wrapper that logs the source context already fetched by the existing recovery path.
The wrapper performs no HTTP/provider/model call of its own.
"""
from __future__ import annotations

from typing import Any

_INSTALL_FLAG = "_run285_recovery_evidence_audit_installed"


def classify_note_ready_source_row(
    raw_source: str,
    state: dict[str, Any] | None,
    allowed_sources: set[str] | frozenset[str] | tuple[str, ...],
) -> str:
    """Return one mutually exclusive pre-publication classification for a Ready source row."""
    if str(raw_source or "").strip() not in set(allowed_sources):
        return "unsupported_source"
    if state is None:
        return "invalid_source_state"
    return "state_available"


def normalize_persisted_article_status(status: str | None) -> str:
    """Normalize a persisted Article Status for stable operational counters only."""
    value = str(status or "").strip()
    return value or "UNKNOWN"


def increment_status_count(counts: dict[str, int], status: str | None) -> str:
    key = normalize_persisted_article_status(status)
    counts[key] = int(counts.get(key, 0)) + 1
    return key


def install_recovery_evidence_audit(pipeline_module: Any) -> Any:
    """Log already-resolved evidence context without changing acquisition or gate behavior.

    ``prepare_source_context`` is invoked by the existing generator.  This wrapper simply observes
    its returned mapping. It neither invokes that function early nor repeats it, so network/model
    request counts are unchanged.
    """
    if bool(getattr(pipeline_module, _INSTALL_FLAG, False)):
        return pipeline_module
    original = getattr(pipeline_module, "prepare_source_context", None)
    if not callable(original):
        setattr(pipeline_module, _INSTALL_FLAG, True)
        return pipeline_module

    def prepare_source_context_with_audit(repo: dict):
        source_info = original(repo)
        info = source_info if isinstance(source_info, dict) else {}
        documents = info.get("evidence_documents") or []
        primary_url = str(
            info.get("primary_url")
            or info.get("primaryUrl")
            or (repo or {}).get("primaryUrl")
            or (repo or {}).get("url")
            or ""
        )
        logger = getattr(pipeline_module, "logger", None)
        if logger is not None and hasattr(logger, "info"):
            logger.info(
                "[RUN285 EVIDENCE AUDIT] source=%s primary_url=%s context_chars=%s verification_chars=%s evidence_documents=%s method=%s primary_material_retrieved=%s",
                info.get("source") or (repo or {}).get("source") or "",
                primary_url,
                int(info.get("context_length") or len(str(info.get("context") or ""))),
                int(info.get("verification_context_length") or len(str(info.get("verification_context") or ""))),
                len(documents) if isinstance(documents, (list, tuple)) else 0,
                info.get("grounding_method") or info.get("method") or info.get("grounding_status") or "",
                bool(info.get("primary_material_retrieved")),
            )
        return source_info

    pipeline_module.prepare_source_context = prepare_source_context_with_audit
    setattr(pipeline_module, _INSTALL_FLAG, True)
    return pipeline_module
