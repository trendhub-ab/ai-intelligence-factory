from __future__ import annotations
from pathlib import Path

PIPELINE = Path("pipeline.py")
MIGRATION = Path("run245_fact_validation_migration.py")

OLD_PIPELINE_FACT = '''        _normalized_evidence_text=_normalized_evidence_text, _normalized_named_fact=_normalized_named_fact,
        _numeric_claim_condition_tags=_numeric_claim_condition_tags, _numeric_condition_compatible=_numeric_condition_compatible,
        _is_protocol_cardinality_expression=_is_protocol_cardinality_expression, _claim_is_negated=_claim_is_negated,
        _evidence_has_substantive_coverage=_evidence_has_substantive_coverage, _clean_relation_entity=_clean_relation_entity,
        _looks_like_relation_entity=_looks_like_relation_entity, _relation_family_for_predicate=_relation_family_for_predicate,
        _extract_explicit_relation_claim=_extract_explicit_relation_claim, _evidence_supports_relation=_evidence_supports_relation,
'''
NEW_PIPELINE_FACT = '''        _normalized_evidence_text=_normalized_evidence_text, _normalized_named_fact=_normalized_named_fact,
'''
OLD_PIPELINE_BOUNDARY = '''        _normalized_named_fact=_normalized_named_fact, _expand_evidence_aliases=_expand_evidence_aliases,
        classify_action_risk_tier=classify_action_risk_tier,
'''
NEW_PIPELINE_BOUNDARY = '''        _normalized_named_fact=_normalized_named_fact, classify_action_risk_tier=classify_action_risk_tier,
'''

OLD_MIGRATION_FACT = r'''        _normalized_evidence_text=_normalized_evidence_text, _normalized_named_fact=_normalized_named_fact,\n        _numeric_claim_condition_tags=_numeric_claim_condition_tags, _numeric_condition_compatible=_numeric_condition_compatible,\n        _is_protocol_cardinality_expression=_is_protocol_cardinality_expression, _claim_is_negated=_claim_is_negated,\n        _evidence_has_substantive_coverage=_evidence_has_substantive_coverage, _clean_relation_entity=_clean_relation_entity,\n        _looks_like_relation_entity=_looks_like_relation_entity, _relation_family_for_predicate=_relation_family_for_predicate,\n        _extract_explicit_relation_claim=_extract_explicit_relation_claim, _evidence_supports_relation=_evidence_supports_relation,\n'''
NEW_MIGRATION_FACT = r'''        _normalized_evidence_text=_normalized_evidence_text, _normalized_named_fact=_normalized_named_fact,\n'''
OLD_MIGRATION_BOUNDARY = r'''        _normalized_named_fact=_normalized_named_fact, _expand_evidence_aliases=_expand_evidence_aliases,\n        classify_action_risk_tier=classify_action_risk_tier,\n'''
NEW_MIGRATION_BOUNDARY = r'''        _normalized_named_fact=_normalized_named_fact, classify_action_risk_tier=classify_action_risk_tier,\n'''


def replace_exact(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count == 0 and new in text:
        return
    if count != 1:
        raise RuntimeError(f"{path}: binding preimage mismatch count={count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_exact(PIPELINE, OLD_PIPELINE_FACT, NEW_PIPELINE_FACT)
    replace_exact(PIPELINE, OLD_PIPELINE_BOUNDARY, NEW_PIPELINE_BOUNDARY)
    replace_exact(MIGRATION, OLD_MIGRATION_FACT, NEW_MIGRATION_FACT)
    replace_exact(MIGRATION, OLD_MIGRATION_BOUNDARY, NEW_MIGRATION_BOUNDARY)
    print("RUN245_BINDING_REPAIR=PASS")


if __name__ == "__main__":
    main()
