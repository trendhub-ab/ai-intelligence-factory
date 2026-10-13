from __future__ import annotations

import ast
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "v2_live_shadow_acquisition.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "pipeline",
    "notion",
    "note_",
    "content_generation",
    "product_delivery",
    "deferred_queue",
    "eyecatch",
)
FORBIDDEN_HTTP_METHODS = {"post", "put", "patch", "delete"}
FORBIDDEN_WRITE_CALLS = {
    "open",
    "write_text",
    "write_bytes",
    "unlink",
    "rename",
    "replace",
    "mkdir",
    "makedirs",
}


def _tree() -> ast.AST:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def test_v2_002_does_not_import_production_write_or_pipeline_surfaces():
    imported = []
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    assert "v2_shadow_selection" in imported
    assert not any(
        module == prefix or module.startswith(prefix)
        for module in imported
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def test_v2_002_exposes_no_mutating_http_methods():
    mutating_calls = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr.lower() in FORBIDDEN_HTTP_METHODS:
            mutating_calls.append(func.attr.lower())

    assert mutating_calls == []


def test_v2_002_has_no_filesystem_write_calls():
    suspicious = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in FORBIDDEN_WRITE_CALLS:
            suspicious.append(func.id)
        elif isinstance(func, ast.Attribute) and func.attr in FORBIDDEN_WRITE_CALLS:
            suspicious.append(func.attr)

    assert suspicious == []
