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

src = Path("pipeline.py").read_text(encoding="utf-8")
tree = ast.parse(src)
rows = []
for node in tree.body:
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or not getattr(node, "end_lineno", None):
        continue
    size = node.end_lineno - node.lineno + 1
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
print(json.dumps(rows[:80], ensure_ascii=False, indent=2))
