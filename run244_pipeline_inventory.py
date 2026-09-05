from __future__ import annotations

import ast
import json
from pathlib import Path

RISK_TOKENS = {
    "gemini": ("gemini", "genai", "generate_content", "model"),
    "notion": ("notion",),
    "network": ("requests", "http", "fetch_", "github_api"),
    "persistence": ("write", "save", "persist", "patch", "create_page", "update_page", "open("),
    "quality_gate": ("fact_gate", "evidence_gate", "decision_gate", "publication", "human_appeal", "quality"),
    "quota_retry": ("quota", "rpd", "rpm", "tpm", "pending_retry", "retry_budget"),
}
TARGET_NAMES = {
    "assess_evidence_sufficiency", "build_decision_prompt", "_product_review_prompt",
    "_product_review_schema_error", "_strict_schema_int", "_validate_product_review_payload",
    "_normalize_japanese_display_label", "_decode_product_review_json", "_parse_product_review_response",
    "_parse_product_review_model_response", "_technology_state_to_repo",
}

src = Path("pipeline.py").read_text(encoding="utf-8")
tree = ast.parse(src)
rows = []
target_sizes = {}
for node in tree.body:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not getattr(node, "end_lineno", None):
        continue
    size = node.end_lineno - node.lineno + 1
    if node.name in TARGET_NAMES:
        target_sizes[node.name] = size
    if size < 50:
        continue
    body = ast.get_source_segment(src, node) or ""
    low = body.lower()
    signals = {k: any(tok in low for tok in toks) for k, toks in RISK_TOKENS.items()}
    calls = sorted({n.func.id for n in ast.walk(node) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)})
    rows.append({
        "name": node.name,
        "start": node.lineno,
        "end": node.end_lineno,
        "lines": size,
        "signals": signals,
        "calls": calls[:30],
    })
rows.sort(key=lambda r: (-r["lines"], r["name"]))
print("PIPELINE_LINES", len(src.splitlines()))
print("RUN244_TARGET_SIZES", json.dumps(target_sizes, ensure_ascii=False, sort_keys=True))
print(json.dumps(rows[:80], ensure_ascii=False, indent=2))
