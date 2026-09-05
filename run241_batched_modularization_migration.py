import argparse, ast, pathlib

parser=argparse.ArgumentParser()
parser.add_argument('--write', action='store_true')
args=parser.parse_args()
path=pathlib.Path('pipeline.py')
s=path.read_text()
if 'from candidate_identity import canonicalize_url as _canonicalize_url_impl' in s and 'from source_roi_policy import (' in s:
    ast.parse(s)
    print(f'Run241 migration already applied: {len(s.splitlines())} lines')
    raise SystemExit(0)
if len(s.splitlines()) != 12461:
    raise RuntimeError(f'Run241 expected 12461-line Run240 preimage, got {len(s.splitlines())}')
for marker in ('def build_clean_note_manuscript(', 'def _reason_code(', 'def _parse_batch_screening_response(', 'def compute_source_roi_profile(', 'def canonicalize_url('):
    if marker not in s:
        raise RuntimeError(f'Run241 preimage marker missing: {marker}')
t=ast.parse(s); lines=s.splitlines(keepends=True)
fm={n.name:n for n in t.body if isinstance(n,ast.FunctionDef)}

remove_assign_names={
'DIVIDER_LINE','_BOLD_BOUNDARY_BRACKET_FIXES','SOURCE_RIGHTS_NOTE','ARTICLE_DISCLAIMER','_READER_SOURCE_LABELS',
'_DEDUP_IGNORED_QUERY_PREFIXES','_DEDUP_IGNORED_QUERY_KEYS',
'GATE_STATUS_NOT_RUN','GATE_STATUS_PASS','GATE_STATUS_FAIL','GATE_STATUS_WARNING','GATE_STATUS_REVIEW',
'GATE_SEVERITY_HARD','GATE_SEVERITY_REVIEW','GATE_SEVERITY_SOFT','GATE_SEVERITY_OPERATIONAL',
'GATE_DISPOSITION_PASS','GATE_DISPOSITION_PASS_WITH_WARNINGS','GATE_DISPOSITION_REVIEW','GATE_DISPOSITION_BLOCK',
'REASON_CODE_MAX_TOKENS','REASON_CODE_STRUCTURE_MISSING','REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT',
'REASON_CODE_PRIMARY_SOURCE_UNRESOLVED','REASON_CODE_TECHNICAL_CLAIMS_INSUFFICIENT','REASON_CODE_NUMERIC_CONDITIONS_INSUFFICIENT',
'REASON_CODE_FRESHNESS_REQUIRED_BUT_UNRESOLVED','REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED','REASON_CODE_EVIDENCE_GAP_DISCLOSURE_REQUIRED',
'REASON_CODE_FACT_UNSUPPORTED_CLAIM','REASON_CODE_FACT_NUMERICAL_MISMATCH','REASON_CODE_FACT_ACTOR_MISMATCH',
'REASON_CODE_FACT_UNSUPPORTED_NAMED_FACT','REASON_CODE_FACT_CONDITIONALITY_LOSS','REASON_CODE_EDITORIAL_STRUCTURE_ERROR',
'REASON_CODE_PUB_HEADLINE_OVERCLAIM','REASON_CODE_PUB_INTRO_OVERCLAIM','REASON_CODE_PUB_UNSUPPORTED_CONCLUSION',
'REASON_CODE_PUB_ACTION_EVIDENCE_MISMATCH','REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH','REASON_CODE_PUB_SOURCE_SUFFICIENCY',
'REASON_CODE_PUB_NEGATIVE_EVIDENCE_OMISSION','REASON_CODE_APPEAL_OVER_HEDGING','REASON_CODE_APPEAL_ACTION_COLLAPSE',
'REASON_CODE_APPEAL_TITLE_FLATTENING','REASON_CODE_APPEAL_DECISION_VOICE_LOSS','REASON_CODE_APPEAL_FABRICATED_EXPERIENCE',
'REASON_CODE_APPEAL_AI_STYLE_COMPOSITE','REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT','REASON_CODE_PENDING_RETRY',
'REASON_CODE_MODEL_UNAVAILABLE','REASON_CODE_DEEP_DIVE_RUN_BUDGET_EXHAUSTED','REASON_CODE_NOTION_PERSISTENCE_FAILED',
}

def assign_names(node):
    targets=[]
    if isinstance(node,ast.Assign): targets=node.targets
    elif isinstance(node,ast.AnnAssign): targets=[node.target]
    out=[]
    for target in targets:
        if isinstance(target,ast.Name): out.append(target.id)
    return out

replacements=[]
for node in t.body:
    names=assign_names(node)
    if names and any(name in remove_assign_names for name in names):
        assert set(names) <= remove_assign_names, names
        replacements.append((node.lineno-1,node.end_lineno,'',f'assign:{names}'))

repls={
'_fix_bold_boundary_brackets':'_fix_bold_boundary_brackets = _fix_bold_boundary_brackets_impl\n',
'_strip_internal_note_control_lines':'_strip_internal_note_control_lines = _strip_internal_note_control_lines_impl\n',
'normalize_markdown_for_note':'normalize_markdown_for_note = _normalize_markdown_for_note_impl\n',
'_normalize_note_title':'_normalize_note_title = _normalize_note_title_impl\n',
'build_article_attribution_id':'build_article_attribution_id = _build_article_attribution_id_impl\n',
'build_subscription_tracking_url':'''def build_subscription_tracking_url(article_id: str, landing_url: str | None = None) -> str:\n    return _build_subscription_tracking_url_impl(\n        article_id, landing_url, enabled=ENABLE_SUBSCRIPTION_ATTRIBUTION,\n        default_landing_url=SUBSCRIPTION_LANDING_URL, campaign_id=SUBSCRIPTION_CAMPAIGN_ID,\n    )\n''',
'build_subscription_cta':'''def build_subscription_cta(article_id: str, tracking_url: str = "") -> str:\n    return _build_subscription_cta_impl(article_id, tracking_url or build_subscription_tracking_url(article_id))\n''',
'_reader_plain_text':'_reader_plain_text = _reader_plain_text_impl\n',
'_compact_reader_summary':'_compact_reader_summary = _compact_reader_summary_impl\n',
'_reader_summary_complexity':'_reader_summary_complexity = _reader_summary_complexity_impl\n',
'_pick_reader_summary_candidate':'_pick_reader_summary_candidate = _pick_reader_summary_candidate_impl\n',
'_find_reader_intro_fact_sentence':'_find_reader_intro_fact_sentence = _find_reader_intro_fact_sentence_impl\n',
'_reader_decision_fallback':'_reader_decision_fallback = _reader_decision_fallback_impl\n',
'build_reader_first_summary':'''def build_reader_first_summary(parsed: dict) -> dict[str, str]:\n    return _build_reader_first_summary_impl(\n        parsed, extract_section=_extract_any_markdown_section, display_heading_aliases=_display_heading_aliases,\n        replace_public_decision_code_leaks=_replace_public_decision_code_leaks,\n    )\n''',
'_reader_published_date':'_reader_published_date = _reader_published_date_impl\n',
'build_reader_first_header':'build_reader_first_header = _build_reader_first_header_impl\n',
'_remove_markdown_sections':'_remove_markdown_sections = _remove_markdown_sections_impl\n',
'_remove_reader_redundant_provenance':'_remove_reader_redundant_provenance = _remove_reader_redundant_provenance_impl\n',
'_prepare_reader_first_body':'''def _prepare_reader_first_body(markdown_text: str, reader_summary: dict | None) -> str:\n    return _note_prepare_reader_first_body_impl(\n        markdown_text, reader_summary, display_heading_aliases=_display_heading_aliases,\n    )\n''',
'build_clean_note_manuscript':'''def build_clean_note_manuscript(note_draft: str, repo_name: str, repo_url: str,\n                                 spdx_id: str, source: str = "GitHub", evidence_urls: list[str] | None = None,\n                                 title_text: str = "", discovery_url: str = "", reader_summary: dict | None = None,\n                                 published_at: str | None = None) -> str:\n    return _build_clean_note_manuscript_impl(\n        note_draft, repo_name, repo_url, spdx_id, source, evidence_urls, title_text, discovery_url, reader_summary,\n        published_at, split_free_paid=split_free_paid, display_heading_aliases=_display_heading_aliases,\n        subscription_enabled=ENABLE_SUBSCRIPTION_ATTRIBUTION, subscription_landing_url=SUBSCRIPTION_LANDING_URL,\n        subscription_campaign_id=SUBSCRIPTION_CAMPAIGN_ID,\n    )\n''',
'canonicalize_url':'canonicalize_url = _canonicalize_url_impl\n',
'candidate_identity_urls':'''def candidate_identity_urls(repo: dict) -> set[str]:\n    return _candidate_identity_urls_impl(repo, canonicalizer=canonicalize_url)\n''',
'_reason_code':'_reason_code = _reason_code_impl\n',
'classify_gate_reason_severity':'classify_gate_reason_severity = _classify_gate_reason_severity_impl\n',
'map_gate_reasons':'map_gate_reasons = _map_gate_reasons_impl\n',
'_infer_gate_from_reason_code':'_infer_gate_from_reason_code = _infer_gate_from_reason_code_impl\n',
'normalize_gate_reason_rows':'normalize_gate_reason_rows = _normalize_gate_reason_rows_impl\n',
'gate_reason_disposition':'gate_reason_disposition = _gate_reason_disposition_impl\n',
'_reason_rows_by_severity':'_reason_rows_by_severity = _reason_rows_by_severity_impl\n',
'_quality_warning_messages':'_quality_warning_messages = _quality_warning_messages_impl\n',
'build_candidate_gate_record':'''def build_candidate_gate_record(candidate_rank: int, repo_name: str, source_url: str, decision_score: int | None,\n                                generation_status: str, fact_gate: str = GATE_STATUS_NOT_RUN,\n                                editorial_gate: str = GATE_STATUS_NOT_RUN, publication_readiness_gate: str = GATE_STATUS_NOT_RUN,\n                                human_appeal_gate: str = GATE_STATUS_NOT_RUN, reason_codes: list[dict] | None = None,\n                                final_status: str = "", article_saved: bool = False, evidence_result: dict | None = None,\n                                deep_dive_generation_called: bool = False, retry_diagnostics: dict | None = None,\n                                candidate_origin: str = "new", source: str = "Unknown", generation_request_count: int = 0) -> dict:\n    return _build_candidate_gate_record_impl(\n        candidate_rank, repo_name, source_url, decision_score, generation_status, fact_gate, editorial_gate,\n        publication_readiness_gate, human_appeal_gate, reason_codes, final_status, article_saved, evidence_result,\n        deep_dive_generation_called, retry_diagnostics, candidate_origin, source, generation_request_count,\n        analyzed_at_now_iso=_analyzed_at_now_iso,\n    )\n''',
'build_internal_article_record':'''def build_internal_article_record(repo: dict, parsed: dict | None, gate_record: dict,\n                                  source_info: dict | None, failure_reason: str) -> dict:\n    return _build_internal_article_record_impl(\n        repo, parsed, gate_record, source_info, failure_reason, analyzed_at_now_iso=_analyzed_at_now_iso,\n        extract_section=_extract_any_markdown_section, display_heading_aliases=_display_heading_aliases,\n    )\n''',
'build_screening_prompt':'''def build_screening_prompt(name, desc, stars, source: str = "GitHub") -> str:\n    return _build_screening_prompt_impl(name, desc, stars, source, engagement_labels=ENGAGEMENT_LABELS)\n''',
'round_robin_candidates':'round_robin_candidates = _round_robin_candidates_impl\n',
'_bounded_optional_score':'_bounded_optional_score = _bounded_optional_score_impl\n',
'shelf_life_label':'''def shelf_life_label(score: int | float | None) -> str:\n    return _shelf_life_label_impl(score, neutral_score=PROFIT_SCORE_NEUTRAL)\n''',
'deep_dive_priority_score':'''def deep_dive_priority_score(decision_score: int | float | None, commercial_score: int | float | None) -> float:\n    return _deep_dive_priority_score_impl(\n        decision_score, commercial_score, neutral_score=PROFIT_SCORE_NEUTRAL,\n        decision_weight=DEEP_DIVE_DECISION_WEIGHT, commercial_weight=DEEP_DIVE_COMMERCIAL_WEIGHT,\n    )\n''',
'_attach_profit_metadata':'''def _attach_profit_metadata(item: dict, commercial_score: int | None, shelf_life_score: int | None) -> dict:\n    return _attach_profit_metadata_impl(\n        item, commercial_score, shelf_life_score, neutral_score=PROFIT_SCORE_NEUTRAL,\n        decision_weight=DEEP_DIVE_DECISION_WEIGHT, commercial_weight=DEEP_DIVE_COMMERCIAL_WEIGHT,\n    )\n''',
'normalize_portfolio_topic':'''def normalize_portfolio_topic(value) -> str:\n    return _normalize_portfolio_topic_impl(value, portfolio_topics=PORTFOLIO_TOPICS)\n''',
'_attach_portfolio_topic':'''def _attach_portfolio_topic(item: dict, topic=None, raw_topic=None) -> dict:\n    return _attach_portfolio_topic_impl(item, topic, raw_topic, portfolio_topics=PORTFOLIO_TOPICS)\n''',
'_salvage_screening_json_rows':'_salvage_screening_json_rows = _salvage_screening_json_rows_impl\n',
'_parse_batch_screening_response':'''def _parse_batch_screening_response(text: str, expected_ids: set[str], include_diagnostic: bool = False):\n    return _parse_batch_screening_response_impl(\n        text, expected_ids, include_diagnostic, tracking_eligibility_min_score=TRACKING_ELIGIBILITY_MIN_SCORE,\n        portfolio_topics=PORTFOLIO_TOPICS,\n    )\n''',
'_batch_screening_prompt':'_batch_screening_prompt = _batch_screening_prompt_impl\n',
'_calibration_prompt':'_calibration_prompt = _calibration_prompt_impl\n',
'_source_roi_smoothed_rate':'_source_roi_smoothed_rate = _source_roi_smoothed_rate_impl\n',
'compute_source_roi_profile':'''def compute_source_roi_profile(state: dict | None) -> dict[str, dict]:\n    return _compute_source_roi_profile_impl(\n        state, sources=SOURCE_ROI_SOURCES, history_runs=SOURCE_ROI_HISTORY_RUNS, recency_decay=SOURCE_ROI_RECENCY_DECAY,\n        stock_weight=SOURCE_ROI_STOCK_WEIGHT, ready_weight=SOURCE_ROI_READY_WEIGHT, efficiency_weight=SOURCE_ROI_EFFICIENCY_WEIGHT,\n        min_screened=SOURCE_ROI_MIN_SCREENED, min_deep_dive_attempts=SOURCE_ROI_MIN_DEEP_DIVE_ATTEMPTS,\n        exploration_weight=SOURCE_ROI_EXPLORATION_WEIGHT, enable_learning=ENABLE_SOURCE_ROI_LEARNING,\n        min_mature_sources=SOURCE_ROI_MIN_MATURE_SOURCES, smoothed_rate=_source_roi_smoothed_rate,\n    )\n''',
'allocate_source_fetch_limits':'''def allocate_source_fetch_limits(profile: dict[str, dict] | None, total_limit: int | None = None) -> dict[str, int]:\n    return _allocate_source_fetch_limits_impl(\n        profile, total_limit, base=_source_base_fetch_limits(), enable_learning=ENABLE_SOURCE_ROI_LEARNING,\n        max_screening_candidates=MAX_SCREENING_CANDIDATES, max_fetch_by_source=SOURCE_ROI_MAX_FETCH_BY_SOURCE,\n        sources=SOURCE_ROI_SOURCES, min_fetch_per_source=SOURCE_ROI_MIN_FETCH_PER_SOURCE,\n    )\n''',
'build_source_roi_run_metrics':'''def build_source_roi_run_metrics(screened: list[dict] | None, funnel: "DeepDiveGateFunnel | None") -> dict:\n    return _build_source_roi_run_metrics_impl(\n        screened, funnel, sources=SOURCE_ROI_SOURCES, reason_code_model_unavailable=REASON_CODE_MODEL_UNAVAILABLE,\n        reason_code_budget_exhausted=REASON_CODE_DEEP_DIVE_RUN_BUDGET_EXHAUSTED, article_status_ready=ARTICLE_STATUS_READY,\n        article_status_needs_editorial_review=ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,\n        content_status_quality_failed=CONTENT_STATUS_QUALITY_FAILED, content_status_pending_retry=CONTENT_STATUS_PENDING_RETRY,\n    )\n''',
}
for name,repl in repls.items():
    n=fm.get(name)
    if n is None: raise SystemExit(f'missing function {name}')
    replacements.append((n.lineno-1,n.end_lineno,repl+'\n',f'fn:{name}'))
spans=sorted(replacements)
for a,b in zip(spans,spans[1:]):
    if a[1] > b[0]: raise SystemExit(f'overlap {a[3]} / {b[3]}')
for start,end,repl,label in sorted(replacements, reverse=True):
    lines[start:end]=[repl]
s=''.join(lines)

IMPORT_BLOCK='''\nfrom candidate_identity import canonicalize_url as _canonicalize_url_impl, candidate_identity_urls as _candidate_identity_urls_impl\nfrom note_manuscript import (\n    _compact_reader_summary as _compact_reader_summary_impl, _find_reader_intro_fact_sentence as _find_reader_intro_fact_sentence_impl,\n    _fix_bold_boundary_brackets as _fix_bold_boundary_brackets_impl, _normalize_note_title as _normalize_note_title_impl,\n    _pick_reader_summary_candidate as _pick_reader_summary_candidate_impl, _prepare_reader_first_body as _note_prepare_reader_first_body_impl,\n    _reader_decision_fallback as _reader_decision_fallback_impl, _reader_plain_text as _reader_plain_text_impl,\n    _reader_published_date as _reader_published_date_impl, _reader_summary_complexity as _reader_summary_complexity_impl,\n    _remove_markdown_sections as _remove_markdown_sections_impl, _remove_reader_redundant_provenance as _remove_reader_redundant_provenance_impl,\n    _strip_internal_note_control_lines as _strip_internal_note_control_lines_impl, build_article_attribution_id as _build_article_attribution_id_impl,\n    build_clean_note_manuscript as _build_clean_note_manuscript_impl, build_reader_first_header as _build_reader_first_header_impl,\n    build_reader_first_summary as _build_reader_first_summary_impl, build_subscription_cta as _build_subscription_cta_impl,\n    build_subscription_tracking_url as _build_subscription_tracking_url_impl, normalize_markdown_for_note as _normalize_markdown_for_note_impl,\n)\nfrom gate_reasoning import (\n    GATE_STATUS_NOT_RUN, GATE_STATUS_PASS, GATE_STATUS_FAIL, GATE_STATUS_WARNING, GATE_STATUS_REVIEW,\n    GATE_SEVERITY_HARD, GATE_SEVERITY_REVIEW, GATE_SEVERITY_SOFT, GATE_SEVERITY_OPERATIONAL,\n    GATE_DISPOSITION_PASS, GATE_DISPOSITION_PASS_WITH_WARNINGS, GATE_DISPOSITION_REVIEW, GATE_DISPOSITION_BLOCK,\n    REASON_CODE_MAX_TOKENS, REASON_CODE_STRUCTURE_MISSING, REASON_CODE_PRIMARY_EVIDENCE_INSUFFICIENT, REASON_CODE_PRIMARY_SOURCE_UNRESOLVED,\n    REASON_CODE_TECHNICAL_CLAIMS_INSUFFICIENT, REASON_CODE_NUMERIC_CONDITIONS_INSUFFICIENT, REASON_CODE_FRESHNESS_REQUIRED_BUT_UNRESOLVED,\n    REASON_CODE_HIGH_RISK_ACTION_UNSUPPORTED, REASON_CODE_EVIDENCE_GAP_DISCLOSURE_REQUIRED, REASON_CODE_FACT_UNSUPPORTED_CLAIM,\n    REASON_CODE_FACT_NUMERICAL_MISMATCH, REASON_CODE_FACT_ACTOR_MISMATCH, REASON_CODE_FACT_UNSUPPORTED_NAMED_FACT,\n    REASON_CODE_FACT_CONDITIONALITY_LOSS, REASON_CODE_EDITORIAL_STRUCTURE_ERROR, REASON_CODE_PUB_HEADLINE_OVERCLAIM,\n    REASON_CODE_PUB_INTRO_OVERCLAIM, REASON_CODE_PUB_UNSUPPORTED_CONCLUSION, REASON_CODE_PUB_ACTION_EVIDENCE_MISMATCH,\n    REASON_CODE_PUB_SCORE_NARRATIVE_MISMATCH, REASON_CODE_PUB_SOURCE_SUFFICIENCY, REASON_CODE_PUB_NEGATIVE_EVIDENCE_OMISSION,\n    REASON_CODE_APPEAL_OVER_HEDGING, REASON_CODE_APPEAL_ACTION_COLLAPSE, REASON_CODE_APPEAL_TITLE_FLATTENING,\n    REASON_CODE_APPEAL_DECISION_VOICE_LOSS, REASON_CODE_APPEAL_FABRICATED_EXPERIENCE, REASON_CODE_APPEAL_AI_STYLE_COMPOSITE,\n    REASON_CODE_APPEAL_CROSS_ARTICLE_FINGERPRINT, REASON_CODE_PENDING_RETRY, REASON_CODE_MODEL_UNAVAILABLE,\n    REASON_CODE_DEEP_DIVE_RUN_BUDGET_EXHAUSTED, REASON_CODE_NOTION_PERSISTENCE_FAILED, reason_code as _reason_code_impl,\n    classify_gate_reason_severity as _classify_gate_reason_severity_impl, map_gate_reasons as _map_gate_reasons_impl,\n    infer_gate_from_reason_code as _infer_gate_from_reason_code_impl, normalize_gate_reason_rows as _normalize_gate_reason_rows_impl,\n    gate_reason_disposition as _gate_reason_disposition_impl, reason_rows_by_severity as _reason_rows_by_severity_impl,\n    quality_warning_messages as _quality_warning_messages_impl, build_candidate_gate_record as _build_candidate_gate_record_impl,\n    build_internal_article_record as _build_internal_article_record_impl,\n)\nfrom screening_protocol import (\n    round_robin_candidates as _round_robin_candidates_impl, bounded_optional_score as _bounded_optional_score_impl,\n    shelf_life_label as _shelf_life_label_impl, deep_dive_priority_score as _deep_dive_priority_score_impl,\n    attach_profit_metadata as _attach_profit_metadata_impl, normalize_portfolio_topic as _normalize_portfolio_topic_impl,\n    attach_portfolio_topic as _attach_portfolio_topic_impl, build_screening_prompt as _build_screening_prompt_impl,\n    salvage_screening_json_rows as _salvage_screening_json_rows_impl, parse_batch_screening_response as _parse_batch_screening_response_impl,\n    batch_screening_prompt as _batch_screening_prompt_impl, calibration_prompt as _calibration_prompt_impl,\n)\nfrom source_roi_policy import (\n    source_roi_smoothed_rate as _source_roi_smoothed_rate_impl, compute_source_roi_profile as _compute_source_roi_profile_impl,\n    allocate_source_fetch_limits as _allocate_source_fetch_limits_impl, build_source_roi_run_metrics as _build_source_roi_run_metrics_impl,\n)\n'''
anchor='''from editorial_naturalness import (\n    ai_style_composite_signals as _ai_style_composite_signals_impl,\n    classify_article_claims as _classify_article_claims_impl,\n    cross_article_naturalness_signals as _cross_article_naturalness_signals_impl,\n    find_fabricated_personal_experience as _find_fabricated_personal_experience_impl,\n    human_editorial_depth_signals as _human_editorial_depth_signals_impl,\n    jaccard as _jaccard_impl,\n    rhetorical_template_phrases as _rhetorical_template_phrases_impl,\n    sentence_shingles as _sentence_shingles_impl,\n    style_sequence as _style_sequence_impl,\n)\n'''
assert anchor in s
s=s.replace(anchor,anchor+IMPORT_BLOCK,1)
ast.parse(s)
line_count=len(s.splitlines())
if line_count != 11497:
    raise RuntimeError(f'Run241 expected 11497-line postimage, got {line_count}')
for forbidden in ('def canonicalize_url(url: str) -> str:\n    """URL Dedup専用の正規化', 'def _reason_code(message: str, gate: str) -> str:\n    """既存Gateの自由文', 'def _salvage_screening_json_rows(text: str) -> list[dict]:\n    """Recover complete JSON', 'def compute_source_roi_profile(state: dict | None) -> dict[str, dict]:\n    """Compute recency-weighted'):
    if forbidden in s:
        raise RuntimeError('Run241 heavy implementation remains in pipeline')
if args.write:
    path.write_text(s)
    print(f'Run241 migration applied: 12461 -> {line_count} lines')
else:
    print(f'Run241 migration plan valid: 12461 -> {line_count} lines; use --write')
