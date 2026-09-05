"""Provider-free Product Review prompt/schema/parser protocol extracted from pipeline.py (Run244)."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse

def _product_review_prompt(repo: dict, source_info: dict, current: dict) -> str:
    context = (source_info.get("context") or "")[:50000]
    # Run115: output shape/enums/ranges live in response_json_schema. Do not duplicate that
    # contract in the prompt; Google's GenAI SDK documentation explicitly warns that repeating
    # the schema in the prompt can reduce structured-output quality. Keep only decision semantics.
    return (
        "以下の一次情報だけを使い、会員向けTechnology Decision Intelligenceを評価せよ。記事は書かない。"
        "入力外の市場シェア、価格、利用実績、競合優位性を推測しない。"
        "categoryはSource種別や既存Categoryをコピーせず、一次情報で確認できる主用途・主機能から判断し、"
        "複数カテゴリが同程度または根拠が弱い場合はOTHERを選ぶ。"
        "adoption_scoreは Evidence Quality 25, Production Maturity 25, Use-case Utility / Fit 20, "
        "Reliability / Security Risk 15, Integration / Migration Feasibility 10, Ecosystem / Support Durability 5 の合計100点とし、"
        "componentsの合計と必ず一致させる。"
        "ADOPTはEvidence ConfidenceがHIGHかつProduction ReadinessがHIGHの場合に限る。"
        "main_risk / best_for / avoid_for / short_rationaleは、一次情報から判断できる範囲で具体的かつ空欄にしない。"
        "japanese_display_labelは任意の表示専用フィールド。正式な製品名・プロジェクト名・論文名を改変せず、"
        "『名称 — 日本語で何の技術か』の短い説明ラベルにする。推奨・評価・誇張・スコア・Adoption Statusを含めず、"
        "一次情報だけから安全に説明できない場合は空文字にする。Identity判定には使われない。\n"
        f"Technology: {repo.get('nameWithOwner')}\nURL: {repo.get('url')}\nCurrent: {json.dumps(current, ensure_ascii=False)}\n"
        f"Verified source context:\n{context}"
    )

def _product_review_schema_error(message: str) -> ValueError:
    return ValueError(f"Product Review schema_invalid: {message}")

def _strict_schema_int(value: object, field: str, minimum: int, maximum: int) -> int:
    # bool is a subclass of int in Python, but JSON Schema integer must not silently accept it
    # for scoring/range decisions.
    if isinstance(value, bool) or not isinstance(value, int):
        raise _product_review_schema_error(f"{field} must be integer")
    if not minimum <= value <= maximum:
        raise _product_review_schema_error(f"{field} out_of_range {value} not in {minimum}..{maximum}")
    return value

def _normalize_japanese_display_label(value: object) -> str:
    """Soft-normalize the UI-only Japanese label without failing Product Review.

    This field is deliberately excluded from assessment validity, retry triggers, entity identity,
    evidence authority, History change detection, and launch readiness.
    """
    if not isinstance(value, str):
        return ""
    label = re.sub(r"\s+", " ", value).strip()
    if not label or len(label) > 80 or "\n" in value or "\r" in value:
        return ""
    if not re.search(r"[\u3040-\u30ff\u3400-\u9fff]", label):
        return ""
    forbidden = re.compile(
        r"(?:\b(?:WATCH|TEST|ADOPT|AVOID)\b|(?:Adoption|Decision)\s*Score|\d{1,3}\s*/\s*100|"
        r"おすすめ|推奨|最強|最高|革命的|必須|今すぐ導入|採用すべき)", re.I,
    )
    if forbidden.search(label):
        return ""
    return label

def _decode_product_review_json(text: str) -> dict:
    """Parse provider JSON with deterministic, zero-API wrapper cleanup.

    Structured output should already be valid JSON. This fallback only tolerates harmless code
    fences / leading or trailing transport text; it never repairs missing fields or invents values.
    """
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        obj = json.loads(raw or "{}")
    except json.JSONDecodeError:
        start = raw.find("{")
        if start < 0:
            raise
        obj, _ = json.JSONDecoder().raw_decode(raw[start:])
    if not isinstance(obj, dict):
        raise ValueError("Product Review response_not_object")
    return obj

def _validate_product_review_payload(obj: dict, *, product_review_response_schema, portfolio_topics, adoption_score_components, decision_intelligence_module) -> dict:
    """Locally validate provider structured output before any semantic normalization.

    Provider-side JSON Schema is a transport guard, not a trust boundary.  Run115 validates
    required keys, additional keys, enums, component structure/ranges, score sum, text fields,
    and review range again in application code.  Any violation is a structured-output failure
    eligible for the single logical retry; no invalid enum is silently coerced to OTHER.
    """
    if not isinstance(obj, dict):
        raise _product_review_schema_error('response_not_object')
    required = set(product_review_response_schema['required'])
    allowed = set(product_review_response_schema['properties'])
    actual = set(obj)
    missing = sorted(required - actual)
    extra = sorted(actual - allowed)
    if missing:
        raise _product_review_schema_error('missing_fields=' + ','.join(missing))
    if extra:
        raise _product_review_schema_error('unexpected_fields=' + ','.join(extra))
    category = obj.get('category')
    if not isinstance(category, str) or category not in portfolio_topics:
        raise _product_review_schema_error(f'category invalid={category!r}')
    score = _strict_schema_int(obj.get('adoption_score'), 'adoption_score', 1, 100)
    components = obj.get('components')
    if not isinstance(components, dict):
        raise _product_review_schema_error('components must be object')
    expected_components = {label for label, _ in adoption_score_components}
    component_keys = set(components)
    if component_keys != expected_components:
        missing_components = sorted(expected_components - component_keys)
        extra_components = sorted(component_keys - expected_components)
        detail = []
        if missing_components:
            detail.append('missing=' + ','.join(missing_components))
        if extra_components:
            detail.append('extra=' + ','.join(extra_components))
        raise _product_review_schema_error('components_keys ' + ' '.join(detail))
    component_values: dict[str, int] = {}
    for label, maximum in adoption_score_components:
        component_values[label] = _strict_schema_int(components.get(label), f'components.{label}', 0, maximum)
    component_total = sum(component_values.values())
    if component_total != score:
        raise _product_review_schema_error(f'adoption_score_sum_mismatch components={component_total} score={score}')
    for field, allowed in (('adoption_status', decision_intelligence_module.ADOPTION_STATUSES), ('evidence_confidence', decision_intelligence_module.CONFIDENCE_LEVELS), ('production_readiness', decision_intelligence_module.READINESS_LEVELS)):
        value = obj.get(field)
        if not isinstance(value, str) or value not in allowed:
            raise _product_review_schema_error(f'{field} invalid={value!r}')
    for field in ('main_risk', 'best_for', 'avoid_for', 'short_rationale'):
        value = obj.get(field)
        if not isinstance(value, str) or not value.strip():
            raise _product_review_schema_error(f'{field} must be non-empty string')
    _strict_schema_int(obj.get('next_review_days'), 'next_review_days', 7, 60)
    return obj

def _parse_product_review_response(payload: object, *, adoption_score_components, validate_product_review_payload, normalize_japanese_display_label) -> dict:
    obj = payload if isinstance(payload, dict) else _decode_product_review_json(str(payload or ''))
    obj = validate_product_review_payload(obj)
    components = obj['components']
    breakdown = '\n'.join((f'{label} {components[label]}/{maximum}' for label, maximum in adoption_score_components))
    return {'category': obj['category'], 'adoption_score': obj['adoption_score'], 'adoption_score_breakdown_text': breakdown, 'adoption_status': obj['adoption_status'], 'evidence_confidence': obj['evidence_confidence'], 'production_readiness': obj['production_readiness'], 'main_risk_text': obj['main_risk'], 'best_for_text': obj['best_for'], 'avoid_for_text': obj['avoid_for'], 'short_rationale_text': obj['short_rationale'], 'japanese_display_label': normalize_japanese_display_label(obj.get('japanese_display_label')), 'source_summary_text': 'Product Review from verified primary evidence', 'next_review_days': obj['next_review_days']}

def _parse_product_review_model_response(response: object, *, parse_product_review_response) -> dict:
    provider_parsed = getattr(response, 'parsed', None)
    if isinstance(provider_parsed, dict):
        return parse_product_review_response(provider_parsed)
    model_dump = getattr(provider_parsed, 'model_dump', None)
    if callable(model_dump):
        dumped = model_dump()
        if isinstance(dumped, dict):
            return parse_product_review_response(dumped)
    return parse_product_review_response(getattr(response, 'text', ''))

def _technology_state_to_repo(state: dict, *, effective_evidence_source, github_repo_identity) -> dict:
    """Rehydrate the minimum source identity lost by the legacy Notion schema.

    Technology rows intentionally do not store sourceDetails JSON. Run113 reconstructs only
    explicit facts already present in Primary URL / Canonical Entity ID / Evidence URLs / aliases;
    it never guesses an official site from the technology name.
    """
    sources = [str(x) for x in state.get('sources') or ['GitHub'] if x]
    discovery_source = sources[0] if sources else 'GitHub'
    primary_url = str(state.get('primary_url') or '')
    entity_id = str(state.get('canonical_entity_id') or '')
    name = str(state.get('technology_name') or 'Technology')
    temp = {'source': discovery_source, 'primaryUrl': primary_url, 'url': primary_url, 'canonicalEntityId': entity_id, 'nameWithOwner': name}
    effective_source = effective_evidence_source(temp)
    if effective_source == 'GitHub':
        repo_identity = github_repo_identity(temp)
        if repo_identity:
            name = repo_identity
    details: dict[str, object] = {'discovery_sources': sources, 'related_links': list(state.get('evidence_urls') or [])}
    aliases = [str(x) for x in state.get('entity_aliases') or [] if x]
    for alias in aliases:
        host = (urlparse(alias).netloc or '').lower()
        if 'news.ycombinator.com' in host and (not details.get('hn_url')):
            details['hn_url'] = alias
        if 'producthunt.com' in host and (not details.get('producthunt_url')):
            details['producthunt_url'] = alias
    if effective_source == 'HackerNews' and primary_url and ('news.ycombinator.com' not in (urlparse(primary_url).netloc or '').lower()):
        details['external_url'] = primary_url
    if effective_source == 'ProductHunt' and primary_url and ('producthunt.com' not in (urlparse(primary_url).netloc or '').lower()):
        details['official_url'] = primary_url
    return {'source': effective_source, 'discoverySource': discovery_source, 'nameWithOwner': name, 'canonicalEntityId': entity_id, 'url': primary_url, 'primaryUrl': primary_url, 'description': state.get('source_summary') or state.get('short_rationale') or '', 'sourceContext': state.get('source_summary') or '', 'sourceContextVerified': False, 'publishedAt': None, 'stargazerCount': 0, 'sourceDetails': details}
