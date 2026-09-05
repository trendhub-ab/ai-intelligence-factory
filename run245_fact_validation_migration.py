from __future__ import annotations
import argparse, ast, hashlib
from pathlib import Path

P=Path('pipeline.py'); F=Path('fact_validation_signals.py'); B=Path('source_boundary_validation.py')
LINES=10434; SHA='9ef54a6e2c0c204e39202babdadfd7bcb486b96f1136b392f7f95b0189af8889'
FACT=['_normalize_numeric_evidence_text','_numeric_claim_condition_tags','_numeric_condition_compatible','_is_protocol_cardinality_expression','_find_unsupported_numeric_claims','_claim_is_negated','_find_hype_claims','_evidence_has_substantive_coverage','_find_false_negative_evidence_claims','_find_unsupported_competitor_claims','_relation_family_for_predicate','_clean_relation_entity','_looks_like_relation_entity','_extract_explicit_relation_claim','_evidence_supports_relation','_find_entity_relation_violations']
BOUND=['_expand_evidence_aliases','_find_source_boundary_violations']
SIZES={'_normalize_numeric_evidence_text':31,'_numeric_claim_condition_tags':20,'_numeric_condition_compatible':9,'_is_protocol_cardinality_expression':39,'_find_unsupported_numeric_claims':69,'_claim_is_negated':20,'_find_hype_claims':36,'_evidence_has_substantive_coverage':24,'_find_false_negative_evidence_claims':19,'_find_unsupported_competitor_claims':21,'_relation_family_for_predicate':5,'_clean_relation_entity':7,'_looks_like_relation_entity':11,'_extract_explicit_relation_claim':68,'_evidence_supports_relation':10,'_find_entity_relation_violations':20,'_expand_evidence_aliases':22,'_find_source_boundary_violations':110}
ANCHOR='''from product_review_protocol import (\n    _product_review_prompt as _product_review_prompt_impl,\n    _product_review_schema_error as _product_review_schema_error_impl,\n    _strict_schema_int as _strict_schema_int_impl,\n    _validate_product_review_payload as _validate_product_review_payload_impl,\n    _normalize_japanese_display_label as _normalize_japanese_display_label_impl,\n    _decode_product_review_json as _decode_product_review_json_impl,\n    _parse_product_review_response as _parse_product_review_response_impl,\n    _parse_product_review_model_response as _parse_product_review_model_response_impl,\n    _technology_state_to_repo as _technology_state_to_repo_impl,\n)\n'''
IMPORT='''import fact_validation_signals as _fact_validation_signals_module\nfrom fact_validation_signals import (\n    _normalize_numeric_evidence_text as _normalize_numeric_evidence_text_impl, _numeric_claim_condition_tags as _numeric_claim_condition_tags_impl,\n    _numeric_condition_compatible as _numeric_condition_compatible_impl, _is_protocol_cardinality_expression as _is_protocol_cardinality_expression_impl,\n    _find_unsupported_numeric_claims as _find_unsupported_numeric_claims_impl, _claim_is_negated as _claim_is_negated_impl,\n    _find_hype_claims as _find_hype_claims_impl, _evidence_has_substantive_coverage as _evidence_has_substantive_coverage_impl,\n    _find_false_negative_evidence_claims as _find_false_negative_evidence_claims_impl, _find_unsupported_competitor_claims as _find_unsupported_competitor_claims_impl,\n    _relation_family_for_predicate as _relation_family_for_predicate_impl, _clean_relation_entity as _clean_relation_entity_impl,\n    _looks_like_relation_entity as _looks_like_relation_entity_impl, _extract_explicit_relation_claim as _extract_explicit_relation_claim_impl,\n    _evidence_supports_relation as _evidence_supports_relation_impl, _find_entity_relation_violations as _find_entity_relation_violations_impl,\n)\nimport source_boundary_validation as _source_boundary_validation_module\nfrom source_boundary_validation import _expand_evidence_aliases as _expand_evidence_aliases_impl, _find_source_boundary_violations as _find_source_boundary_violations_impl\n'''

def nodes(s): return {n.name:n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef)}
def src(s,n):
 L=s.splitlines(); return '\n'.join(L[n.lineno-1:n.end_lineno])

def wrapper(name):
 sig={
'_normalize_numeric_evidence_text':'text: str','_numeric_claim_condition_tags':'text: str','_numeric_condition_compatible':'claim_window: str, evidence_window: str','_is_protocol_cardinality_expression':'text: str, start: int, end: int, token: str','_find_unsupported_numeric_claims':'draft: str, source_context: str, evidence_metadata: dict | None = None','_claim_is_negated':'text: str, start: int, end: int','_find_hype_claims':'draft: str, source_context: str = "", evidence_metadata: dict | None = None','_evidence_has_substantive_coverage':'key: str, source_context: str, evidence_metadata: dict | None = None','_find_false_negative_evidence_claims':'draft: str, evidence_metadata: dict, source_context: str = ""','_find_unsupported_competitor_claims':'parsed: dict, source_context: str','_relation_family_for_predicate':'predicate: str','_clean_relation_entity':'value: str','_looks_like_relation_entity':'value: str','_extract_explicit_relation_claim':'sentence: str','_evidence_supports_relation':'actor: str, obj: str, family_patterns: tuple[str, ...], source_context: str','_find_entity_relation_violations':'draft: str, source_context: str','_expand_evidence_aliases':'source_context: str','_find_source_boundary_violations':'draft: str, source_context: str, repo_name: str = ""'}[name]
 args={
'_normalize_numeric_evidence_text':'text','_numeric_claim_condition_tags':'text','_numeric_condition_compatible':'claim_window, evidence_window','_is_protocol_cardinality_expression':'text, start, end, token','_find_unsupported_numeric_claims':'draft, source_context, evidence_metadata','_claim_is_negated':'text, start, end','_find_hype_claims':'draft, source_context, evidence_metadata','_evidence_has_substantive_coverage':'key, source_context, evidence_metadata','_find_false_negative_evidence_claims':'draft, evidence_metadata, source_context','_find_unsupported_competitor_claims':'parsed, source_context','_relation_family_for_predicate':'predicate','_clean_relation_entity':'value','_looks_like_relation_entity':'value','_extract_explicit_relation_claim':'sentence','_evidence_supports_relation':'actor, obj, family_patterns, source_context','_find_entity_relation_violations':'draft, source_context','_expand_evidence_aliases':'source_context','_find_source_boundary_violations':'draft, source_context, repo_name'}[name]
 bind='_bind_run245_boundary_runtime()' if name in BOUND else '_bind_run245_fact_runtime()'
 impl=name+'_impl'
 return f'def {name}({sig}):\n    {bind}\n    return {impl}({args})'

BIND='''def _bind_run245_fact_runtime() -> None:\n    _fact_validation_signals_module.bind_runtime(\n        _SENSITIVE_NUMERIC_PATTERNS=_SENSITIVE_NUMERIC_PATTERNS, _VAGUE_QUANTIFIED_PATTERNS=_VAGUE_QUANTIFIED_PATTERNS,\n        _HYPE_PATTERNS=_HYPE_PATTERNS, _RELATION_FAMILIES=_RELATION_FAMILIES,\n        _normalized_evidence_text=_normalized_evidence_text, _normalized_named_fact=_normalized_named_fact,\n    )\n\ndef _bind_run245_boundary_runtime() -> None:\n    _source_boundary_validation_module.bind_runtime(\n        _EVIDENCE_ALIAS_GROUPS=_EVIDENCE_ALIAS_GROUPS, _normalized_evidence_text=_normalized_evidence_text,\n        _normalized_named_fact=_normalized_named_fact, classify_action_risk_tier=classify_action_risk_tier,\n    )\n'''

def transform(s):
 if IMPORT.strip() in s:
  n=nodes(s)
  if all(k in n and n[k].end_lineno-n[k].lineno+1<=4 for k in SIZES): return s,'',''
 if len(s.splitlines())!=LINES or hashlib.sha256(s.encode()).hexdigest()!=SHA: raise RuntimeError('Run245 exact preimage mismatch')
 if s.count(ANCHOR)!=1: raise RuntimeError('Run245 import anchor mismatch')
 n=nodes(s)
 for k,v in SIZES.items():
  if k not in n or n[k].end_lineno-n[k].lineno+1!=v: raise RuntimeError(f'Run245 target mismatch: {k}')
 fact='from __future__ import annotations\nimport json, re, unicodedata\n\n_RUNTIME_KEYS=set()\ndef bind_runtime(**deps):\n    globals().update(deps); _RUNTIME_KEYS.update(deps)\n\n'+'\n\n'.join(src(s,n[k]) for k in FACT)+'\n'
 bound='from __future__ import annotations\nimport re\n\n_RUNTIME_KEYS=set()\ndef bind_runtime(**deps):\n    globals().update(deps); _RUNTIME_KEYS.update(deps)\n\n'+'\n\n'.join(src(s,n[k]) for k in BOUND)+'\n'
 L=s.splitlines()
 for k in sorted(SIZES,key=lambda x:n[x].lineno,reverse=True): L[n[k].lineno-1:n[k].end_lineno]=wrapper(k).splitlines()
 out='\n'.join(L)+'\n'; out=out.replace(ANCHOR,ANCHOR+IMPORT+BIND,1)
 ast.parse(out); ast.parse(fact); ast.parse(bound)
 return out,fact,bound

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--write',action='store_true'); a=ap.parse_args(); s=P.read_text(); out,f,b=transform(s)
 print('RUN245_CHANGED='+str(out!=s).lower()); print('RUN245_PIPELINE_LINES_BEFORE='+str(len(s.splitlines()))); print('RUN245_PIPELINE_LINES_AFTER='+str(len(out.splitlines())))
 if a.write and out!=s: P.write_text(out); F.write_text(f); B.write_text(b)
 if a.write and out==s and (not F.exists() or not B.exists()): raise RuntimeError('Run245 canonical module missing')
if __name__=='__main__': main()
