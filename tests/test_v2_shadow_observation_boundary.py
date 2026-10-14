from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path


MODULE = Path(__file__).resolve().parents[1] / "v2_shadow_observation.py"
FORBIDDEN_IMPORT_PREFIXES = (
    "pipeline",
    "notion",
    "note_",
    "content_generation",
    "product_delivery",
    "deferred_queue",
    "publication",
    "google",
    "openai",
    "subprocess",
)
FORBIDDEN_HTTP_METHODS = {"post", "put", "patch", "delete"}
FILESYSTEM_MUTATIONS = {"open", "mkdir", "makedirs", "write_text", "write_bytes", "unlink", "rename", "replace"}


def _tree() -> ast.AST:
    return ast.parse(MODULE.read_text(encoding="utf-8"))


def _imports() -> list[str]:
    imported: list[str] = []
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    return imported


def test_v2_003_imports_v2_002_but_no_production_or_model_surfaces():
    imported = _imports()

    assert "v2_live_shadow_acquisition" in imported
    assert not any(
        module == prefix or module.startswith(prefix)
        for module in imported
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def test_v2_003_exposes_no_mutating_http_methods_or_subprocess():
    mutating_calls = []
    for node in ast.walk(_tree()):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr.lower() in FORBIDDEN_HTTP_METHODS:
            mutating_calls.append(func.attr.lower())

    assert mutating_calls == []
    assert "subprocess" not in _imports()


def test_v2_003_filesystem_mutation_is_only_explicit_output_parent_and_json_file():
    tree = _tree()
    write_function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "write_observation"
    )
    inside = []
    for node in ast.walk(write_function):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in FILESYSTEM_MUTATIONS:
            inside.append(func.id)
        elif isinstance(func, ast.Attribute) and func.attr in FILESYSTEM_MUTATIONS:
            inside.append(func.attr)

    outside = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or node in set(ast.walk(write_function)):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in FILESYSTEM_MUTATIONS:
            outside.append(func.id)
        elif isinstance(func, ast.Attribute) and func.attr in FILESYSTEM_MUTATIONS:
            outside.append(func.attr)

    assert Counter(inside) == Counter({"mkdir": 1, "write_text": 1})
    assert outside == []


def test_v2_003_contains_no_git_mutation_command_strings():
    string_literals = [
        node.value
        for node in ast.walk(_tree())
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    forbidden = ("git push", "git commit", "gh pr", "gh issue", "gh workflow run")
    assert not any(token in text.lower() for token in forbidden for text in string_literals)
