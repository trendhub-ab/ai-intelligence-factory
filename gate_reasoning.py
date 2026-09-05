"""Gate reason-code classification and diagnostic record shaping (Run241).

This module does not execute quality gates. It only maps already-produced gate messages into
stable reason codes/severities/dispositions and shapes audit records.
"""

GATE_STATUS_NOT_RUN = "NOT_RUN"
GATE_STATUS_PASS = "PASS"
GATE_STATUS_FAIL = "FAIL"
GATE_STATUS_WARNING = "WARNING"
GATE_STATUS_REVIEW = "REVIEW"

GATE_SEVERITY_HARD = "HARD_BLOCK"
GATE_SEVERITY_REVIEW = "REVIEW"
GATE_SEVERITY_SOFT = "SOFT_QUALITY"
GATE_SEVERITY_OPERATIONAL = "OPERATIONAL"
GATE_DISPOSITION_PASS = "PASS"
GATE_DISPOSITION_PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
GATE_DISPOSITION_REVIEW = "REVIEW"
GATE_DISPOSITION_BLOCK = "BLOCK"

REASON_CODE_MAX_TOKENS = "MAX_TOKENS"
REASON_CODE_STRUCTURE_MISSING = "STRUCTURE_MISSING"
REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT = "PRIMARY_EVIDENCE_INSUFFICIENT"
REASON_CODE_PRIMARY_SOURCE_UNRESOLVED = "PRIMARY_SOURCE_UNRESOLVED"
REASON_CODE_TECHNICAL_CLAIMS_INSUFFICIENT = "TECHNICAL_CLAIMS_INSUFFICIENT"
REASON_CODE_NUMERIC_CONDITIONS_INSUFFICIENT = "NUMERIC_CONDITIONS_INSUFFICIENT"
REASON_CODE_FRESHNESS_REQUIRED_BUT_UNRESOLVED = "FRESHNESS_REQUIRED_BUT_UNRESOLVED"
REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED = "HIGH_RISK_ACTION_UNSUPPORTED"
REASON_CODE_EVIDENCE_GAP_DISCLOSURE_REQUIRED = "EVIDENCE_GAP_DISCLOSURE_REQUIRED"
REASON_CODE_FACT_UNSUPPORTED_CLAIM = "FACT_UNSUPPORTED_CLAIM"
REASON_CODE_FACT_NUMERICAL_MISMATCH = "FACT_NUMERICAL_MISMATCH"
REASON_CODE_FACT_ACTOR_MISMATCH = "FACT_ACTOR_MISMATCH"
REASON_CODE_FACT_UNSUPPORTED_NAMED_FACT = "FACT_UNSUPPORTED_NAMED_FACT"
REASON_CODE_FACT_CONDITIONALITY_LOSS = "FACT_CONDITIONALITY_LOSS"
REASON_CODE_EDITORIAL_STRUCTURE_ERROR = "EDITORIAL_STRUCTURE_ERROR"
REASON_CODE_PUB_HEADLINE_OVERCLAIM = "PUB_HEADLINE_OVERCLAIM"
REASON_CODE_PUB_INTRO_OVERCLAIM = "PUB_INTRO_OVERCLAIM"
REASON_CODE_PUB_UNSUPPORTED_CONCLUSION = "PUB_UNSUPPORTED_CONCLUSION"
REASON_CODE_PUB_ACTION_EVIDENCE_MISMATCH = "PUB_ACTION_EVIDENCE_MISMATCH"
REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH = "PUB_SCORE_NARRATIVE_MISMATCH"
REASON_CODE_PUB_SOURCE_SUFFICIENCY = "PUB_SOURCE_SUFFICIENCY"
REASON_CODE_PUB_NEGATIVE_EVIDENCE_OMISSION = "PUB_NEGATIVE_EVIDENCE_OMISSION"
REASON_CODE_APPEAL_OVER_HEDGING = "APPEAL_OVER_HEDGING"
REASON_CODE_APPEAL_ACTION_COLLAPSE = "APPEAL_ACTION_COLLAPSE"
REASON_CODE_APPEAL_TITLE_FLATTENING = "APPEAL_TITLE_FLATTENING"
REASON_CODE_APPEAL_DECISION_VOICE_LOSS = "APPEAL_DECISION_VOICE_LOSS"
REASON_CODE_APPEAL_FABRICATED_EXPERIENCE = "APPEAL_FABRICATED_EXPERIENCE"
REASON_CODE_APPEAL_AI_STYLE_COMPOSITE = "APPEAL_AI_STYLE_COMPOSITE"
REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT = "APPEAL_CROSS_ARTICLE_FINGERPRINT"
REASON_CODE_PENDING_RETRY = "PENDING_RETRY"
REASON_CODE_MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
REASON_CODE_DEEP_DIVE_RUN_BUDGET_EXHAUSTED = "DEEP_DIVE_RUN_BUDGET_EXHAUSTED"
REASON_CODE_NOTION_PERSISTENCE_FAILED = "NOTION_PERSISTENCE_FAILED"


def reason_code(message: str, gate: str) -> str:
    text = (message or "").lower()
    if "high_risk_action_unsupported" in text:
        return REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED
    if "output_truncated" in text or "max_tokens" in text or "token_limit" in text:
        return REASON_CODE_MAX_TOKENS
    if "article_structure_incomplete" in text or "required heading missing" in text or "structure" in text:
        return REASON_CODE_STRUCTURE_MISSING
    if "primary_source_authority_insufficient" in text or "primary source" in text and "authority" in text:
        return REASON_CODE_PRIMARY_SOURCE_UNRESOLVED
    if "source_depth_insufficient" in text or "primary_evidence_insufficient" in text or "grounding failed" in text:
        return REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT
    if gate == "fact":
        if any(token in text for token in ("numeric", "number", "数値", "unit", "%")):
            return REASON_CODE_FACT_NUMERICAL_MISMATCH
        if any(token in text for token in ("actor", "author", "attribution", "publisher", "発表主体", "帰属", "entity relation")):
            return REASON_CODE_FACT_ACTOR_MISMATCH
        if "named fact" in text or "unsupported named" in text or "固有名" in text:
            return REASON_CODE_FACT_UNSUPPORTED_NAMED_FACT
        if any(token in text for token in ("limitation", "qualifier", "scope", "fresh", "final wording", "conditional")):
            return REASON_CODE_FACT_CONDITIONALITY_LOSS
        return REASON_CODE_FACT_UNSUPPORTED_CLAIM
    if gate == "editorial":
        if "unsupported personal experience" in text:
            return REASON_CODE_APPEAL_FABRICATED_EXPERIENCE
        return REASON_CODE_EDITORIAL_STRUCTURE_ERROR
    if gate == "publication":
        mapping = {
            "headline_overclaim": REASON_CODE_PUB_HEADLINE_OVERCLAIM,
            "intro_overclaim": REASON_CODE_PUB_INTRO_OVERCLAIM,
            "research_to_production_leap": REASON_CODE_PUB_UNSUPPORTED_CONCLUSION,
            "score_narrative_mismatch": REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH,
            "marketing_claim_adoption": REASON_CODE_PUB_UNSUPPORTED_CONCLUSION,
            "negative_evidence_omission": REASON_CODE_PUB_NEGATIVE_EVIDENCE_OMISSION,
            "primary_evidence_insufficient": REASON_CODE_PUB_SOURCE_SUFFICIENCY,
            "article_structure_needs_edit": REASON_CODE_STRUCTURE_MISSING,
        }
        return mapping.get(message, REASON_CODE_PUB_ACTION_EVIDENCE_MISMATCH)
    if gate == "human_appeal":
        mapping = {
            "over_hedging_without_decision": REASON_CODE_APPEAL_OVER_HEDGING,
            "action_collapsed_to_generic_monitoring": REASON_CODE_APPEAL_ACTION_COLLAPSE,
            "headline_flattened": REASON_CODE_APPEAL_TITLE_FLATTENING,
            "decision_voice_missing": REASON_CODE_APPEAL_DECISION_VOICE_LOSS,
            "fabricated_personal_experience": REASON_CODE_APPEAL_FABRICATED_EXPERIENCE,
            "ai_style_composite_high": REASON_CODE_APPEAL_AI_STYLE_COMPOSITE,
            "cross_article_fingerprint_high": REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT,
            "human_appeal_materially_degraded_after_reedit": REASON_CODE_APPEAL_DECISION_VOICE_LOSS,
        }
        return mapping.get(message, REASON_CODE_APPEAL_DECISION_VOICE_LOSS)
    return REASON_CODE_FACT_UNSUPPORTED_CLAIM


def classify_gate_reason_severity(gate: str, message: str, reason_code_value: str = "") -> str:
    text = (message or "").lower()
    code = reason_code_value or reason_code(message, gate)
    if gate in {"fact", "evidence"}:
        return GATE_SEVERITY_HARD
    if gate == "publication":
        return GATE_SEVERITY_HARD
    if gate == "editorial":
        if "unsupported personal experience" in text:
            return GATE_SEVERITY_HARD
        if "article too list-like" in text:
            return GATE_SEVERITY_REVIEW
        known_soft = (
            "mechanical ordinal structure", "repetitive ai-like sentence endings",
            "too many article headings", "repetitive fixed introduction",
            "missing observation or reservation", "mechanical three-reasons phrasing",
            "too many reader questions", "monotonous sentence endings", "japanese_polish:",
        )
        if any(token in text for token in known_soft):
            return GATE_SEVERITY_SOFT
        return GATE_SEVERITY_REVIEW
    if gate == "human_appeal":
        if code == REASON_CODE_APPEAL_FABRICATED_EXPERIENCE or "fabricated_personal_experience" in text:
            return GATE_SEVERITY_HARD
        if message in {"headline_flattened", "opening_hook_weak", "repeated_caveat_phrase"}:
            return GATE_SEVERITY_SOFT
        if message in {"ai_style_composite_high", "cross_article_fingerprint_high"} or code in {REASON_CODE_APPEAL_AI_STYLE_COMPOSITE, REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT}:
            return GATE_SEVERITY_REVIEW
        if message in {
            "action_collapsed_to_generic_monitoring", "decision_voice_missing", "no_editorial_observation",
            "over_hedging_without_decision", "human_appeal_materially_degraded_after_reedit",
        } or code == REASON_CODE_APPEAL_DECISION_VOICE_LOSS:
            return GATE_SEVERITY_REVIEW
        return GATE_SEVERITY_REVIEW
    return GATE_SEVERITY_HARD


def map_gate_reasons(gate: str, messages: list[str] | None) -> list[dict]:
    rows: list[dict] = []
    for message in (messages or []):
        code = reason_code(message, gate)
        rows.append({"reason_code": code, "message": message, "gate": gate,
                     "severity": classify_gate_reason_severity(gate, message, code)})
    return rows


def infer_gate_from_reason_code(reason_code_value: str) -> str:
    code = reason_code_value or ""
    if code.startswith("FACT_") or code in {REASON_CODE_MAX_TOKENS, REASON_CODE_STRUCTURE_MISSING}:
        return "fact"
    if code in {
        REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT, REASON_CODE_PRIMARY_SOURCE_UNRESOLVED,
        REASON_CODE_TECHNICAL_CLAIMS_INSUFFICIENT, REASON_CODE_NUMERIC_CONDITIONS_INSUFFICIENT,
        REASON_CODE_FRESHNESS_REQUIRED_BUT_UNRESOLVED, REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED,
        REASON_CODE_EVIDENCE_GAP_DISCLOSURE_REQUIRED,
    }:
        return "evidence"
    if code.startswith("PUB_"):
        return "publication"
    if code == REASON_CODE_EDITORIAL_STRUCTURE_ERROR:
        return "editorial"
    if code.startswith("APPEAL_"):
        return "human_appeal"
    if code in {REASON_CODE_PENDING_RETRY, REASON_CODE_MODEL_UNAVAILABLE,
                REASON_CODE_DEEP_DIVE_RUN_BUDGET_EXHAUSTED, REASON_CODE_NOTION_PERSISTENCE_FAILED}:
        return "operational"
    return "fact"


def normalize_gate_reason_rows(reason_rows: list[dict] | None) -> list[dict]:
    normalized: list[dict] = []
    for original in (reason_rows or []):
        row = dict(original)
        code = str(row.get("reason_code") or "")
        gate = str(row.get("gate") or infer_gate_from_reason_code(code))
        row["gate"] = gate
        if not row.get("severity"):
            row["severity"] = GATE_SEVERITY_OPERATIONAL if gate == "operational" else classify_gate_reason_severity(gate, str(row.get("message") or ""), code)
        normalized.append(row)
    return normalized


def gate_reason_disposition(reason_rows: list[dict] | None) -> str:
    rows = normalize_gate_reason_rows(reason_rows)
    severities = {row.get("severity") for row in rows}
    if GATE_SEVERITY_HARD in severities:
        return GATE_DISPOSITION_BLOCK
    if GATE_SEVERITY_REVIEW in severities:
        return GATE_DISPOSITION_REVIEW
    if GATE_SEVERITY_SOFT in severities:
        return GATE_DISPOSITION_PASS_WITH_WARNINGS
    return GATE_DISPOSITION_PASS


def reason_rows_by_severity(reason_rows: list[dict] | None, *severities: str) -> list[dict]:
    allowed = set(severities)
    return [row for row in normalize_gate_reason_rows(reason_rows) if row.get("severity") in allowed]


def quality_warning_messages(reason_rows: list[dict] | None) -> list[str]:
    return [str(row.get("message", "")) for row in normalize_gate_reason_rows(reason_rows)
            if row.get("severity") == GATE_SEVERITY_SOFT and row.get("message")]


def build_candidate_gate_record(
    candidate_rank: int, repo_name: str, source_url: str, decision_score: int | None,
    generation_status: str, fact_gate: str = GATE_STATUS_NOT_RUN,
    editorial_gate: str = GATE_STATUS_NOT_RUN, publication_readiness_gate: str = GATE_STATUS_NOT_RUN,
    human_appeal_gate: str = GATE_STATUS_NOT_RUN, reason_codes: list[dict] | None = None,
    final_status: str = "", article_saved: bool = False, evidence_result: dict | None = None,
    deep_dive_generation_called: bool = False, retry_diagnostics: dict | None = None,
    candidate_origin: str = "new", source: str = "Unknown", generation_request_count: int = 0,
    *, analyzed_at_now_iso,
) -> dict:
    reasons = normalize_gate_reason_rows(reason_codes)
    first = reasons[0] if reasons else {}
    return {
        "candidate_rank": candidate_rank, "name": repo_name, "url": source_url, "source": source,
        "generation_request_count": max(0, int(generation_request_count or 0)), "decision_score": decision_score,
        "generation_status": generation_status, "fact_gate": fact_gate, "editorial_gate": editorial_gate,
        "publication_readiness_gate": publication_readiness_gate, "human_appeal_gate": human_appeal_gate,
        "final_status": final_status, "reason_code": first.get("reason_code", ""), "reason": first.get("message", ""),
        "reason_codes": reasons, "gate_disposition": gate_reason_disposition(reasons),
        "hard_reason_count": sum(1 for row in reasons if row.get("severity") == GATE_SEVERITY_HARD),
        "review_reason_count": sum(1 for row in reasons if row.get("severity") == GATE_SEVERITY_REVIEW),
        "soft_warning_count": sum(1 for row in reasons if row.get("severity") == GATE_SEVERITY_SOFT),
        "article_saved": article_saved, "evidence_sufficiency": (evidence_result or {}).get("state", ""),
        "evidence_initial_sufficiency": (evidence_result or {}).get("initial_state", (evidence_result or {}).get("state", "")),
        "evidence_supplement_attempted": bool((evidence_result or {}).get("supplement_attempted")),
        "evidence_supplement_success": bool((evidence_result or {}).get("supplement_success")),
        "evidence_documents_checked": (evidence_result or {}).get("documents_checked", 0),
        "evidence_checks": (evidence_result or {}).get("checks", {}),
        "decision_scope_safe": (evidence_result or {}).get("decision_scope_safe"),
        "action_risk_tier": (evidence_result or {}).get("action_risk_tier", ""),
        "action_supported_at_current_tier": (evidence_result or {}).get("action_supported_at_current_tier"),
        "limitations_disclosed": (evidence_result or {}).get("limitations_disclosed"),
        "freshness_scope_limited": (evidence_result or {}).get("freshness_scope_limited"),
        "evidence_gap_disclosed": (evidence_result or {}).get("evidence_gap_disclosed"),
        "deep_dive_generation_called": deep_dive_generation_called, "retry_diagnostics": retry_diagnostics or {},
        "retry_attempted": bool((retry_diagnostics or {}).get("retry_attempted")),
        "retry_succeeded": bool((retry_diagnostics or {}).get("retry_succeeded")),
        "dynamic_retry_reason_codes": (retry_diagnostics or {}).get("trigger_reason_codes", []),
        "candidate_origin": candidate_origin, "recorded_at": analyzed_at_now_iso(),
    }


def build_internal_article_record(repo: dict, parsed: dict | None, gate_record: dict,
                                  source_info: dict | None, failure_reason: str, *,
                                  analyzed_at_now_iso, extract_section, display_heading_aliases) -> dict:
    parsed = parsed or {}
    article = parsed.get("note_draft", "")
    return {
        "pipeline_status": gate_record.get("final_status"),
        "failed_gate": next((name for name, state in (
            ("Fact", gate_record.get("fact_gate")),
            ("Publication Readiness", gate_record.get("publication_readiness_gate")),
            ("Human Appeal", gate_record.get("human_appeal_gate")),
        ) if state in {GATE_STATUS_FAIL, GATE_STATUS_REVIEW}), ""),
        "gate_history": gate_record, "failure_reason": failure_reason, "article": article,
        "title": parsed.get("title_text", ""),
        "introduction": extract_section(article, display_heading_aliases("intro")),
        "conclusion": extract_section(article, display_heading_aliases("conclusion")),
        "action": parsed.get("action_text", ""), "decision_score": parsed.get("score"),
        "why_not": parsed.get("why_not_important_text", ""),
        "primary_evidence": {
            "primary_url": (source_info or {}).get("primary_url", repo.get("url")),
            "evidence_urls": (source_info or {}).get("evidence_urls", []),
            "metadata": (source_info or {}).get("evidence_metadata", {}),
            "verification_context_length": (source_info or {}).get("verification_context_length", 0),
        },
        "candidate_rank": gate_record.get("candidate_rank"), "source_url": repo.get("url"),
        "generated_at": analyzed_at_now_iso(),
    }
