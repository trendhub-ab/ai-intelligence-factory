from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

PIPELINE = Path("pipeline.py")
CONTENT_MODULE = Path("content_generation_protocol.py")
EVIDENCE_MODULE = Path("evidence_sufficiency.py")
PRODUCT_MODULE = Path("product_review_protocol.py")
EXPECTED_PREIMAGE_LINES = 10840

TARGET_SIZES = {
    "assess_evidence_sufficiency": 116,
    "build_decision_prompt": 163,
    "_product_review_prompt": 21,
    "_product_review_schema_error": 2,
    "_strict_schema_int": 8,
    "_validate_product_review_payload": 62,
    "_normalize_japanese_display_label": 20,
    "_decode_product_review_json": 20,
    "_parse_product_review_response": 17,
    "_parse_product_review_model_response": 10,
    "_technology_state_to_repo": 52,
}


class RenameNames(ast.NodeTransformer):
    def __init__(self, mapping: dict[str, str]):
        self.mapping = mapping

    def visit_Name(self, node: ast.Name):
        if node.id in self.mapping:
            return ast.copy_location(ast.Name(id=self.mapping[node.id], ctx=node.ctx), node)
        return node


def _function_nodes(src: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(src)
    return {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}


def _segment(src: str, node: ast.FunctionDef) -> str:
    lines = src.splitlines(keepends=True)
    return "".join(lines[node.lineno - 1: node.end_lineno])


def _add_kwonly(fn: ast.FunctionDef, names: list[str]) -> None:
    for name in names:
        fn.args.kwonlyargs.append(ast.arg(arg=name, annotation=None))
        fn.args.kw_defaults.append(None)


def _transformed_function(src: str, name: str, mapping: dict[str, str], kwonly: list[str], *, clear_grounding_default: bool = False) -> str:
    node = deepcopy(_function_nodes(src)[name])
    if clear_grounding_default:
        positional = [a.arg for a in node.args.args]
        idx = positional.index("grounding_status_hint")
        default_start = len(positional) - len(node.args.defaults)
        default_idx = idx - default_start
        if default_idx < 0:
            raise RuntimeError("Run244 grounding default shape changed")
        node.args.defaults[default_idx] = ast.Constant(value=None)
    node = RenameNames(mapping).visit(node)
    _add_kwonly(node, kwonly)
    ast.fix_missing_locations(node)
    return ast.unparse(node) + "\n"


def _build_evidence_module(src: str) -> str:
    mapping = {
        "_FUTURE_SOURCE_PATTERN": "future_source_pattern",
        "_evidence_trace_url_key": "evidence_trace_url_key",
        "EVIDENCE_SUFFICIENT": "evidence_sufficient",
        "EVIDENCE_SUPPLEMENT_REQUIRED": "evidence_supplement_required",
        "EVIDENCE_INSUFFICIENT": "evidence_insufficient",
    }
    fn = _transformed_function(
        src,
        "assess_evidence_sufficiency",
        mapping,
        list(mapping.values()),
    )
    return (
        '"""Deterministic Evidence-to-Decision sufficiency policy extracted from pipeline.py (Run244)."""\n\n'
        "from __future__ import annotations\n\nimport re\n\n" + fn
    )


def _build_product_module(src: str) -> str:
    nodes = _function_nodes(src)
    direct = [
        "_product_review_prompt",
        "_product_review_schema_error",
        "_strict_schema_int",
        "_normalize_japanese_display_label",
        "_decode_product_review_json",
    ]
    out = [
        '"""Provider-free Product Review prompt/schema/parser protocol extracted from pipeline.py (Run244)."""',
        "",
        "from __future__ import annotations",
        "",
        "import json",
        "import re",
        "from urllib.parse import urlparse",
        "",
    ]
    for name in direct:
        out.append(_segment(src, nodes[name]).rstrip())
        out.append("")

    validate_map = {
        "_PRODUCT_REVIEW_RESPONSE_SCHEMA": "product_review_response_schema",
        "PORTFOLIO_TOPICS": "portfolio_topics",
        "_ADOPTION_SCORE_COMPONENTS": "adoption_score_components",
        "decision_intelligence": "decision_intelligence_module",
    }
    out.append(_transformed_function(
        src, "_validate_product_review_payload", validate_map, list(validate_map.values())
    ).rstrip())
    out.append("")

    parse_map = {
        "_ADOPTION_SCORE_COMPONENTS": "adoption_score_components",
        "_validate_product_review_payload": "validate_product_review_payload",
        "_normalize_japanese_display_label": "normalize_japanese_display_label",
    }
    out.append(_transformed_function(
        src, "_parse_product_review_response", parse_map, list(parse_map.values())
    ).rstrip())
    out.append("")

    model_map = {"_parse_product_review_response": "parse_product_review_response"}
    out.append(_transformed_function(
        src, "_parse_product_review_model_response", model_map, list(model_map.values())
    ).rstrip())
    out.append("")

    tech_map = {
        "_effective_evidence_source": "effective_evidence_source",
        "_github_repo_identity": "github_repo_identity",
    }
    out.append(_transformed_function(
        src, "_technology_state_to_repo", tech_map, list(tech_map.values())
    ).rstrip())
    out.append("")
    return "\n".join(out)


def _append_build_decision_prompt(content_src: str, pipeline_src: str) -> str:
    if "def build_decision_prompt(" in content_src:
        return content_src
    mapping = {
        "ENGAGEMENT_LABELS": "engagement_labels",
        "MAX_EVIDENCE_TOTAL_CHARS": "max_evidence_total_chars",
        "_truncate_source_context": "truncate_source_context",
        "_source_fact_discipline": "source_fact_discipline",
        "_human_editorial_style_rules": "human_editorial_style_rules",
        "_article_display_variant": "article_display_variant",
        "SECTION_SPLIT_TOKEN": "section_split_token",
        "datetime": "datetime_cls",
        "JST": "jst",
    }
    fn = _transformed_function(
        pipeline_src,
        "build_decision_prompt",
        mapping,
        list(mapping.values()),
        clear_grounding_default=True,
    )
    if "import json\n" not in content_src:
        if "import re\n" not in content_src:
            raise RuntimeError("Run244 content module import anchor changed")
        content_src = content_src.replace("import re\n", "import json\nimport re\n", 1)
    return content_src.rstrip() + "\n\n\n" + fn


def _wrapper_build_decision_prompt() -> str:
    return '''def build_decision_prompt(name, url, stars, desc, quality_feedback: str = "", source: str = "GitHub",
                          source_context: str = "", grounding_status_hint: str = GROUNDING_METADATA_ONLY,
                          evidence_metadata: dict | None = None, freshness: dict | None = None,
                          previous_article: str = "", evidence_result: dict | None = None):
    """Bind canonical decision prompt shaping to live pipeline editorial/evidence settings."""
    return _build_decision_prompt_impl(
        name, url, stars, desc,
        quality_feedback=quality_feedback, source=source, source_context=source_context,
        grounding_status_hint=grounding_status_hint, evidence_metadata=evidence_metadata,
        freshness=freshness, previous_article=previous_article, evidence_result=evidence_result,
        engagement_labels=ENGAGEMENT_LABELS,
        max_evidence_total_chars=MAX_EVIDENCE_TOTAL_CHARS,
        truncate_source_context=_truncate_source_context,
        source_fact_discipline=_source_fact_discipline,
        human_editorial_style_rules=_human_editorial_style_rules,
        article_display_variant=_article_display_variant,
        section_split_token=SECTION_SPLIT_TOKEN,
        datetime_cls=datetime,
        jst=JST,
    )
'''


def _wrapper_evidence() -> str:
    return '''def assess_evidence_sufficiency(source_info: dict) -> dict:
    """Bind canonical evidence sufficiency policy to live pipeline source helpers/constants."""
    return _assess_evidence_sufficiency_impl(
        source_info,
        future_source_pattern=_FUTURE_SOURCE_PATTERN,
        evidence_trace_url_key=_evidence_trace_url_key,
        evidence_sufficient=EVIDENCE_SUFFICIENT,
        evidence_supplement_required=EVIDENCE_SUPPLEMENT_REQUIRED,
        evidence_insufficient=EVIDENCE_INSUFFICIENT,
    )
'''


def _wrapper_validate_product() -> str:
    return '''def _validate_product_review_payload(obj: dict) -> dict:
    return _validate_product_review_payload_impl(
        obj,
        product_review_response_schema=_PRODUCT_REVIEW_RESPONSE_SCHEMA,
        portfolio_topics=PORTFOLIO_TOPICS,
        adoption_score_components=_ADOPTION_SCORE_COMPONENTS,
        decision_intelligence_module=decision_intelligence,
    )
'''


def _wrapper_parse_product() -> str:
    return '''def _parse_product_review_response(payload: object) -> dict:
    return _parse_product_review_response_impl(
        payload,
        adoption_score_components=_ADOPTION_SCORE_COMPONENTS,
        validate_product_review_payload=_validate_product_review_payload,
        normalize_japanese_display_label=_normalize_japanese_display_label,
    )
'''


def _wrapper_parse_model() -> str:
    return '''def _parse_product_review_model_response(response: object) -> dict:
    return _parse_product_review_model_response_impl(
        response,
        parse_product_review_response=_parse_product_review_response,
    )
'''


def _wrapper_tech_state() -> str:
    return '''def _technology_state_to_repo(state: dict) -> dict:
    return _technology_state_to_repo_impl(
        state,
        effective_evidence_source=_effective_evidence_source,
        github_repo_identity=_github_repo_identity,
    )
'''


def transform_pipeline(src: str) -> str:
    if "from evidence_sufficiency import assess_evidence_sufficiency as _assess_evidence_sufficiency_impl" in src:
        return src
    if len(src.splitlines()) != EXPECTED_PREIMAGE_LINES:
        raise RuntimeError(f"Run244 preimage line count changed: {len(src.splitlines())} != {EXPECTED_PREIMAGE_LINES}")
    nodes = _function_nodes(src)
    for name, expected in TARGET_SIZES.items():
        node = nodes.get(name)
        if node is None:
            raise RuntimeError(f"Run244 target missing: {name}")
        actual = node.end_lineno - node.lineno + 1
        if actual != expected:
            raise RuntimeError(f"Run244 target size changed: {name} {actual} != {expected}")

    content_import_anchor = "from content_generation_protocol import (\n"
    start = src.find(content_import_anchor)
    if start < 0:
        raise RuntimeError("Run244 content import anchor missing")
    close = src.find(")\n", start)
    if close < 0:
        raise RuntimeError("Run244 content import block malformed")
    block = src[start:close + 2]
    if "build_decision_prompt as _build_decision_prompt_impl" not in block:
        block = block[:-2] + "    build_decision_prompt as _build_decision_prompt_impl,\n)\n"
    extra_imports = '''from evidence_sufficiency import assess_evidence_sufficiency as _assess_evidence_sufficiency_impl
from product_review_protocol import (
    _product_review_prompt as _product_review_prompt_impl,
    _product_review_schema_error as _product_review_schema_error_impl,
    _strict_schema_int as _strict_schema_int_impl,
    _validate_product_review_payload as _validate_product_review_payload_impl,
    _normalize_japanese_display_label as _normalize_japanese_display_label_impl,
    _decode_product_review_json as _decode_product_review_json_impl,
    _parse_product_review_response as _parse_product_review_response_impl,
    _parse_product_review_model_response as _parse_product_review_model_response_impl,
    _technology_state_to_repo as _technology_state_to_repo_impl,
)
'''
    src = src[:start] + block + extra_imports + src[close + 2:]

    replacements = {
        "assess_evidence_sufficiency": _wrapper_evidence(),
        "build_decision_prompt": _wrapper_build_decision_prompt(),
        "_product_review_prompt": "_product_review_prompt = _product_review_prompt_impl\n",
        "_product_review_schema_error": "_product_review_schema_error = _product_review_schema_error_impl\n",
        "_strict_schema_int": "_strict_schema_int = _strict_schema_int_impl\n",
        "_validate_product_review_payload": _wrapper_validate_product(),
        "_normalize_japanese_display_label": "_normalize_japanese_display_label = _normalize_japanese_display_label_impl\n",
        "_decode_product_review_json": "_decode_product_review_json = _decode_product_review_json_impl\n",
        "_parse_product_review_response": _wrapper_parse_product(),
        "_parse_product_review_model_response": _wrapper_parse_model(),
        "_technology_state_to_repo": _wrapper_tech_state(),
    }
    nodes = _function_nodes(src)
    lines = src.splitlines(keepends=True)
    spans = []
    for name, replacement in replacements.items():
        node = nodes.get(name)
        if node is None:
            raise RuntimeError(f"Run244 replacement target missing after import edit: {name}")
        spans.append((node.lineno - 1, node.end_lineno, replacement))
    for start_line, end_line, replacement in sorted(spans, reverse=True):
        lines[start_line:end_line] = [replacement + ("\n" if not replacement.endswith("\n\n") else "")]
    out = "".join(lines)
    ast.parse(out)
    return out


def migrate(*, write: bool = False) -> dict:
    pipeline_src = PIPELINE.read_text(encoding="utf-8")
    if "from evidence_sufficiency import assess_evidence_sufficiency as _assess_evidence_sufficiency_impl" in pipeline_src:
        return {"changed": False, "lines": len(pipeline_src.splitlines())}
    evidence_src = _build_evidence_module(pipeline_src)
    product_src = _build_product_module(pipeline_src)
    content_src = _append_build_decision_prompt(CONTENT_MODULE.read_text(encoding="utf-8"), pipeline_src)
    migrated = transform_pipeline(pipeline_src)
    ast.parse(evidence_src)
    ast.parse(product_src)
    ast.parse(content_src)
    if write:
        EVIDENCE_MODULE.write_text(evidence_src, encoding="utf-8")
        PRODUCT_MODULE.write_text(product_src, encoding="utf-8")
        CONTENT_MODULE.write_text(content_src, encoding="utf-8")
        PIPELINE.write_text(migrated, encoding="utf-8")
    return {
        "changed": True,
        "pre_lines": len(pipeline_src.splitlines()),
        "post_lines": len(migrated.splitlines()),
        "evidence_lines": len(evidence_src.splitlines()),
        "product_lines": len(product_src.splitlines()),
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(migrate(write=args.write))
