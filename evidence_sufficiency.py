"""Deterministic Evidence-to-Decision sufficiency policy extracted from pipeline.py (Run244)."""

from __future__ import annotations

import re

def assess_evidence_sufficiency(source_info: dict, *, future_source_pattern, evidence_trace_url_key, evidence_sufficient, evidence_supplement_required, evidence_insufficient) -> dict:
    """Evidence-to-Decision Sufficiencyを判定する。

    網羅性そのものではなく、取得済みの一次情報の範囲で結論とActionを安全な
    強度に制約した記事を作れるかを判定する。制約・鮮度が未確認でも、低リスク
    Actionと明示的な留保で安全に扱える研究紹介まで機械的に落とさない。
    """
    context = source_info.get('verification_context') or source_info.get('context', '') or ''
    coverage = (source_info.get('evidence_metadata') or {}).get('coverage', {})
    found = lambda key: coverage.get(key) == 'FOUND'
    numbers_present = bool(re.search('(?:\\d+(?:\\.\\d+)?\\s*(?:%|x|倍|ms|sec(?:ond)?s?|GB|MB|FPS))', context, re.I))
    time_sensitive = bool(future_source_pattern.search(context))
    current_state_claim = bool(re.search('(?:価格|料金|現在|現行|提供中|法令|制度)|\\b(?:availability|pricing|current|today|GA|generally available)\\b', context, re.I))
    research_scope = source_info.get('source') == 'ArXiv' or bool(re.search('(?:paper|arxiv|benchmark|論文|研究|実験|提出時点)', context, re.I))
    requested_tier = str(source_info.get('requested_action_risk_tier', 'LOW')).upper()
    action_risk_tier = requested_tier if requested_tier in {'LOW', 'MEDIUM', 'HIGH'} else 'LOW'
    checks = {'primary_source_resolved': bool(source_info.get('primary_source_resolved')), 'technical_claims_available': found('method') or bool(re.search('\\b(?:method|approach|architecture|algorithm|implementation)\\b|モデル|手法|方式|実装', context, re.I)), 'limitations_or_constraints_available': found('limitations') or bool(re.search('\\b(?:limitation|limitations|constraint|constraints|caveat)\\b|not validated|制約|限界|課題|未検証', context, re.I)), 'conditions_for_numbers_available': not numbers_present or any((found(key) for key in ('hardware', 'runtime', 'benchmark', 'dataset'))), 'actor_attribution_available': bool(re.search('\\b(?:author|authors|developer|developers|researcher|researchers)\\b|著者|開発者|研究者', context, re.I)) or bool((source_info.get('source_details') or {}).get('authors')), 'action_support_available': False, 'comparison_support_available_if_comparison_is_needed': True, 'freshness_status_available_if_time_sensitive': not (time_sensitive or current_state_claim) or bool(source_info.get('freshness_status_available'))}
    low_risk_supported = checks['primary_source_resolved'] and checks['technical_claims_available']
    medium_risk_supported = low_risk_supported and checks['limitations_or_constraints_available']
    high_risk_supported = medium_risk_supported and checks['conditions_for_numbers_available'] and checks['freshness_status_available_if_time_sensitive']
    action_supported_requested_tier = {'LOW': low_risk_supported, 'MEDIUM': medium_risk_supported, 'HIGH': high_risk_supported}[action_risk_tier]
    checks['action_support_available'] = action_supported_requested_tier
    comparison_needed = bool(re.search('(?:compare|comparison|versus|vs\\.?|比較|従来方式|代替)', context, re.I))
    if comparison_needed:
        checks['comparison_support_available_if_comparison_is_needed'] = bool(re.search('(?:compare|comparison|versus|vs\\.?|比較)', context, re.I))
    hard_missing = [key for key in ('primary_source_resolved', 'technical_claims_available') if not checks[key]]
    if source_info.get('numeric_claims_required') and (not checks['conditions_for_numbers_available']):
        hard_missing.append('conditions_for_numbers_available')
    if source_info.get('actor_attribution_required') and (not checks['actor_attribution_available']):
        hard_missing.append('actor_attribution_available')
    conditional_missing = [key for key in ('limitations_or_constraints_available', 'action_support_available', 'comparison_support_available_if_comparison_is_needed', 'freshness_status_available_if_time_sensitive') if not checks[key]]
    blocking_missing = list(hard_missing)
    if current_state_claim and (not research_scope) and (not checks['freshness_status_available_if_time_sensitive']):
        blocking_missing.append('freshness_status_available_if_time_sensitive')
    checked_evidence_keys = source_info.get('checked_urls', set())
    candidates_available = any((evidence_trace_url_key(row.get('url', '')) not in checked_evidence_keys for row in source_info.get('supplement_candidates', []) if row.get('url')))
    supplement_already_attempted = bool(source_info.get('evidence_supplement_attempted'))
    action_risk_downgraded_from = ''
    if blocking_missing:
        state = evidence_supplement_required if candidates_available else evidence_insufficient
    elif action_risk_tier in {'MEDIUM', 'HIGH'} and (not action_supported_requested_tier):
        if candidates_available and (not supplement_already_attempted):
            state = evidence_supplement_required
        elif low_risk_supported:
            action_risk_downgraded_from = action_risk_tier
            action_risk_tier = 'LOW'
            checks['action_support_available'] = True
            state = evidence_sufficient
        else:
            blocking_missing.append('high_risk_action_unsupported' if requested_tier == 'HIGH' else 'medium_risk_action_unsupported')
            state = evidence_insufficient
    elif conditional_missing and candidates_available and (not supplement_already_attempted):
        state = evidence_supplement_required
    else:
        state = evidence_sufficient
    limitations_disclosed = not checks['limitations_or_constraints_available']
    research_future_only = research_scope and bool(re.search('\\bfuture\\s+work\\b|今後の研究|将来(?:の)?研究', context, re.I))
    freshness_scope_limited = research_future_only or (research_scope and time_sensitive and (not checks['freshness_status_available_if_time_sensitive']))
    evidence_gap_disclosed = bool(conditional_missing)
    decision_scope_safe = state == evidence_sufficient or (state == evidence_supplement_required and (not blocking_missing))
    return {'state': state, 'checks': checks, 'core_missing': hard_missing, 'optional_missing': conditional_missing, 'blocking_missing': blocking_missing, 'documents_checked': len(source_info.get('evidence_documents', [])), 'decision_scope_safe': decision_scope_safe, 'action_risk_tier': action_risk_tier, 'action_supported_at_current_tier': checks['action_support_available'], 'action_risk_downgraded_from': action_risk_downgraded_from, 'limitations_disclosed': limitations_disclosed, 'freshness_scope_limited': freshness_scope_limited, 'evidence_gap_disclosed': evidence_gap_disclosed, 'research_scope': research_scope, 'current_state_claim': current_state_claim, 'numeric_claims_allowed': checks['conditions_for_numbers_available'], 'actor_attribution_allowed': checks['actor_attribution_available']}
