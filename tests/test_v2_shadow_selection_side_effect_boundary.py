import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "v2_shadow_selection.py"


def test_v2_shadow_core_imports_only_stdlib_and_candidate_identity():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported == {
        "__future__",
        "candidate_identity",
        "dataclasses",
        "datetime",
        "itertools",
        "typing",
    }


def test_v2_shadow_core_has_no_file_write_or_dynamic_import_surface():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    forbidden_bare_calls = {"open", "exec", "eval", "__import__"}
    forbidden_methods = {
        "write",
        "writelines",
        "write_text",
        "write_bytes",
        "unlink",
        "mkdir",
        "rename",
        "replace",
    }

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_bare_calls
        elif isinstance(node.func, ast.Attribute):
            assert node.func.attr not in forbidden_methods
