#!/usr/bin/env python3
"""Fail-closed guard for the canonical Production runtime-layer stack.

Run231 moved runtime installation out of ``production_pipeline.py``.  The only
execution-order source of truth is now ``runtime_layers.py::RUNTIME_LAYER_ORDER``
plus ``install_runtime_layers``.  This guard parses that file statically so CI
cannot be satisfied by stale imports, comments, or fake ``.install(...)`` text.

The guard is deliberately zero-network and does not import runtime_layers.py.
Dynamic construction is rejected: a production order that cannot be audited
statically is not an acceptable production contract.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUNTIME_LAYERS = ROOT / "runtime_layers.py"

_LAYER_RE = re.compile(
    r"^(?P<module>[A-Za-z_][A-Za-z0-9_]*)\.(?P<method>install|install_pipeline)$"
)


def _runtime_order(tree: ast.Module) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    assignments: list[ast.AST] = []

    for node in tree.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "RUNTIME_LAYER_ORDER" for target in node.targets):
                assignments.append(node.value)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name) and node.target.id == "RUNTIME_LAYER_ORDER":
                assignments.append(node.value)

    if len(assignments) != 1:
        failures.append(f"runtime_layer_order_assignment_count:{len(assignments)}")
        return [], failures

    value = assignments[0]
    if not isinstance(value, (ast.Tuple, ast.List)):
        failures.append("runtime_layer_order_not_literal_sequence")
        return [], failures

    order: list[str] = []
    for index, element in enumerate(value.elts):
        if not isinstance(element, ast.Constant) or not isinstance(element.value, str):
            failures.append(f"runtime_layer_order_nonliteral_entry:{index}")
            continue
        entry = element.value.strip()
        if not _LAYER_RE.fullmatch(entry):
            failures.append(f"runtime_layer_order_invalid_entry:{index}:{entry}")
            continue
        order.append(entry)

    seen: set[str] = set()
    for entry in order:
        if entry in seen:
            failures.append(f"runtime_layer_order_duplicate:{entry}")
        seen.add(entry)

    return order, failures


def _install_function(tree: ast.Module) -> tuple[ast.FunctionDef | None, list[str]]:
    funcs = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "install_runtime_layers"
    ]
    failures: list[str] = []
    if len(funcs) != 1 or not isinstance(funcs[0] if funcs else None, ast.FunctionDef):
        failures.append(f"install_runtime_layers_definition_count:{len(funcs)}")
        return None, failures
    func = funcs[0]
    if [arg.arg for arg in func.args.args] != ["pipeline_module"]:
        failures.append("install_runtime_layers_signature_drift")
    return func, failures


def _actual_install_order(func: ast.FunctionDef) -> tuple[list[str], list[str]]:
    failures: list[str] = []
    aliases: dict[str, str] = {}
    calls: list[str] = []

    for node in func.body:
        if isinstance(node, ast.Import):
            for item in node.names:
                aliases[item.asname or item.name] = item.name
            continue

        if isinstance(node, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Match)):
            # Runtime patch installation must remain a flat deterministic sequence.
            for nested in ast.walk(node):
                if isinstance(nested, ast.Call) and isinstance(nested.func, ast.Attribute):
                    if nested.func.attr in {"install", "install_pipeline"}:
                        failures.append("runtime_install_control_flow_detected")
                        break
            continue

        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Attribute):
            continue
        if call.func.attr not in {"install", "install_pipeline"}:
            continue
        if not isinstance(call.func.value, ast.Name):
            failures.append("runtime_install_dynamic_receiver")
            continue
        if len(call.args) != 1 or not isinstance(call.args[0], ast.Name) or call.args[0].id != "pipeline_module" or call.keywords:
            failures.append("runtime_install_signature_drift")
            continue
        alias = call.func.value.id
        module = aliases.get(alias)
        if not module:
            failures.append(f"runtime_install_unresolved_alias:{alias}")
            continue
        calls.append(f"{module}.{call.func.attr}")

    return calls, failures


def audit_runtime_layers(root: Path | None = None) -> list[str]:
    base = Path(root) if root is not None else ROOT
    path = base / "runtime_layers.py"
    failures: list[str] = []

    if not path.is_file():
        return ["runtime_layers_missing"]

    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
    except (OSError, UnicodeError, SyntaxError) as exc:
        return [f"runtime_layers_unparseable:{type(exc).__name__}"]

    order, order_failures = _runtime_order(tree)
    failures.extend(order_failures)

    func, func_failures = _install_function(tree)
    failures.extend(func_failures)
    actual: list[str] = []
    if func is not None:
        actual, actual_failures = _actual_install_order(func)
        failures.extend(actual_failures)

    if order and actual != order:
        failures.append(
            "runtime_layer_execution_order_mismatch:"
            f"declared={','.join(order)}:actual={','.join(actual)}"
        )

    for entry in order:
        match = _LAYER_RE.fullmatch(entry)
        if not match:
            continue
        module_path = base / f"{match.group('module')}.py"
        if not module_path.is_file():
            failures.append(f"runtime_layer_module_missing:{module_path.name}")

    return list(dict.fromkeys(failures))


def main() -> None:
    failures = audit_runtime_layers()
    if failures:
        print("RUN279_RUNTIME_LAYER_GUARD=FAIL")
        for failure in failures:
            print("-", failure)
        raise SystemExit(1)
    print("RUN279_RUNTIME_LAYER_GUARD=PASS")


if __name__ == "__main__":
    main()
