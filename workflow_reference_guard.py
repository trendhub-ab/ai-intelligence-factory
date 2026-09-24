#!/usr/bin/env python3
"""Fail closed on dangling GitHub Actions execution references.

Run257 protects the repository against a common class of silent automation damage:
workflows that still exist but point at deleted/renamed scripts, tests, local actions,
upstream workflow names, or `gh workflow run` targets.

The guard is intentionally zero-network and dependency-free. It validates only
references that are provably repository-local; dynamic/external commands are left
alone rather than guessed.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import shlex


WORKFLOW_DIR = Path(".github/workflows")
_WORKFLOW_SUFFIXES = {".yml", ".yaml"}

# Production/operational execution must be explicit. Persistent cron is forbidden
# repository-wide; these writer workflows additionally have a narrow trigger allowlist.
_OPERATIONAL_TRIGGER_POLICY = {
    "daily-one-shot.yml": {"workflow_dispatch"},
    "daily.yml": {"workflow_dispatch"},
    "note-publication-reconcile.yml": {"workflow_dispatch"},
    "note-ready-sync.yml": {"workflow_dispatch"},
    "subscriber-decision-brief.yml": {"workflow_dispatch", "workflow_run", "pull_request"},
    "member-presentation-sync.yml": {"workflow_dispatch", "workflow_run"},
}

_RUN_RE = re.compile(r"^(?P<indent>\s*)(?:-\s*)?run:\s*(?P<rest>.*)$")
_NAME_RE = re.compile(r"^name:\s*(?P<value>.+?)\s*$")
_LOCAL_USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*['\"]?(?P<path>\./[^\s#'\"]+)", re.MULTILINE)
_REPO_FILE_RE = re.compile(
    r"(?<![/\w.-])((?:\./)?[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*\.(?:py|sh))\b"
)
_UNITTEST_DISCOVER_PATTERN_RE = re.compile(
    r"(?P<flag>(?:-p|--pattern)\s+)(?P<quote>['\"]?)(?P<pattern>[^\s'\"\n]+\.py)(?P=quote)"
)
_UNITTEST_RE = re.compile(
    r"(?:^|[;&|]\s*)python(?:3(?:\.\d+)?)?\s+-m\s+unittest\s+(?P<args>[^\n;&|]+)",
    re.MULTILINE,
)
_GH_WORKFLOW_RUN_RE = re.compile(
    r"\bgh\s+workflow\s+run\s+(?:\"(?P<double>[^\"]+)\"|'(?P<single>[^']+)'|(?P<bare>[^\s\\]+))"
)


def _strip_yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _workflow_name(text: str) -> str | None:
    for line in text.splitlines():
        match = _NAME_RE.match(line)
        if match:
            return _strip_yaml_scalar(match.group("value"))
    return None


def _top_level_on_triggers(text: str) -> set[str]:
    """Return conventional top-level keys under the workflow `on:` block."""
    lines = text.splitlines()
    triggers: set[str] = set()
    in_on = False
    for line in lines:
        if not in_on:
            if line == "on:":
                in_on = True
            continue
        if line and not line.startswith(" "):
            break
        match = re.match(r"^  ([A-Za-z_]+):", line)
        if match:
            triggers.add(match.group(1))
    return triggers


def _run_blocks(text: str) -> list[str]:
    """Extract shell bodies from `run:` and `- run:` without a YAML dependency."""
    lines = text.splitlines()
    blocks: list[str] = []
    index = 0
    while index < len(lines):
        match = _RUN_RE.match(lines[index])
        if not match:
            index += 1
            continue
        base_indent = len(match.group("indent"))
        rest = match.group("rest").strip()
        if rest.startswith(("|", ">")):
            body: list[str] = []
            index += 1
            while index < len(lines):
                line = lines[index]
                if not line.strip():
                    body.append("")
                    index += 1
                    continue
                indent = len(line) - len(line.lstrip(" "))
                if indent <= base_indent:
                    break
                body.append(line)
                index += 1
            blocks.append("\n".join(body))
            continue
        if rest:
            blocks.append(rest)
        index += 1
    return blocks


def _workflow_run_targets(text: str) -> list[str]:
    """Return static `on.workflow_run.workflows` names from conventional Actions YAML."""
    lines = text.splitlines()
    targets: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped != "workflow_run:":
            index += 1
            continue
        workflow_run_indent = len(line) - len(line.lstrip(" "))
        index += 1
        while index < len(lines):
            current = lines[index]
            if current.strip():
                current_indent = len(current) - len(current.lstrip(" "))
                if current_indent <= workflow_run_indent:
                    break
            current_stripped = current.strip()
            if current_stripped.startswith("workflows:"):
                workflows_indent = len(current) - len(current.lstrip(" "))
                tail = current_stripped.split(":", 1)[1].strip()
                if tail.startswith("[") and tail.endswith("]"):
                    inner = tail[1:-1].strip()
                    if inner:
                        targets.extend(
                            _strip_yaml_scalar(item.strip())
                            for item in inner.split(",")
                            if item.strip()
                        )
                    index += 1
                    continue
                index += 1
                while index < len(lines):
                    item_line = lines[index]
                    if not item_line.strip():
                        index += 1
                        continue
                    item_indent = len(item_line) - len(item_line.lstrip(" "))
                    if item_indent <= workflows_indent:
                        break
                    item = item_line.strip()
                    if item.startswith("-"):
                        value = item[1:].strip()
                        if value:
                            targets.append(_strip_yaml_scalar(value))
                    index += 1
                continue
            index += 1
    return targets


def _unittest_modules(run_block: str) -> list[str]:
    modules: list[str] = []
    for match in _UNITTEST_RE.finditer(run_block):
        try:
            tokens = shlex.split(match.group("args"), comments=False, posix=True)
        except ValueError:
            continue
        if "discover" in tokens:
            continue
        skip_next = False
        for token in tokens:
            if skip_next:
                skip_next = False
                continue
            if token in {"-s", "--start-directory", "-p", "--pattern", "-t", "--top-level-directory"}:
                skip_next = True
                continue
            if token.startswith("-"):
                continue
            if token.startswith("tests.") and re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+", token):
                modules.append(token)
    return modules


def _module_path(module: str) -> Path:
    return Path(*module.split(".")).with_suffix(".py")


def _resolve_local(root: Path, token: str) -> Path:
    normalized = token[2:] if token.startswith("./") else token
    return root / normalized


def _without_unittest_discover_patterns(run_block: str) -> str:
    """Remove `unittest discover -p test_x.py` selectors from file-reference scanning.

    The pattern is a selector under the start directory, not an executable file path
    relative to repository root. Explicit unittest modules are validated separately.
    """
    return _UNITTEST_DISCOVER_PATTERN_RE.sub(lambda match: match.group("flag") + "<pattern>", run_block)



def _literal_newline_escape_errors(text: str, rel: str) -> list[str]:
    """Reject accidental literal backslash-n in YAML structure, but allow block scalar bodies.

    Shell commands and other block scalars may intentionally contain \\n (for example
    printf format strings). Structural YAML must use real line breaks so choice values,
    artifact paths, env values, and step keys cannot be silently fused.
    """
    errors: list[str] = []
    block_indent: int | None = None
    for lineno, line in enumerate(text.splitlines(), start=1):
        if block_indent is not None:
            if line.strip():
                indent = len(line) - len(line.lstrip(" "))
                if indent > block_indent:
                    continue
                block_indent = None
            else:
                continue
        stripped = line.strip()
        scalar_head = stripped.split("#", 1)[0].rstrip()
        if ":" in scalar_head and scalar_head.endswith(("|", ">", "|-", "|+", ">-", ">+")):
            block_indent = len(line) - len(line.lstrip(" "))
            continue
        if "\\n" in line:
            errors.append(
                f"{rel}:{lineno}: literal backslash-n in workflow YAML structure; use a real line break"
            )
    return errors

def validate(root: str | Path = ".") -> list[str]:
    root_path = Path(root)
    workflow_dir = root_path / WORKFLOW_DIR
    if not workflow_dir.is_dir():
        return [f"workflow directory missing: {WORKFLOW_DIR.as_posix()}"]

    workflows = sorted(
        path for path in workflow_dir.iterdir() if path.is_file() and path.suffix in _WORKFLOW_SUFFIXES
    )
    texts = {path: path.read_text(encoding="utf-8") for path in workflows}
    names = {path: _workflow_name(text) for path, text in texts.items()}

    errors: list[str] = []
    missing_name = [path for path, name in names.items() if not name]
    for path in missing_name:
        errors.append(f"{path.relative_to(root_path)}: top-level workflow name is missing")

    name_counts = Counter(name for name in names.values() if name)
    for name, count in sorted(name_counts.items()):
        if count > 1:
            errors.append(f"duplicate workflow name is ambiguous ({count} files): {name}")
    known_names = set(name_counts)

    for workflow_path, text in texts.items():
        rel = workflow_path.relative_to(root_path).as_posix()
        errors.extend(_literal_newline_escape_errors(text, rel))

        triggers = _top_level_on_triggers(text)
        if "schedule" in triggers:
            errors.append(
                f"{rel}: fixed schedule trigger is forbidden; use an explicit reservation/dispatch"
            )
        allowed = _OPERATIONAL_TRIGGER_POLICY.get(workflow_path.name)
        if allowed is not None:
            disallowed = sorted(triggers - allowed)
            if disallowed:
                errors.append(
                    f"{rel}: disallowed automatic trigger(s): {', '.join(disallowed)}"
                )

        for local_action in _LOCAL_USES_RE.finditer(text):
            target = _resolve_local(root_path, local_action.group("path"))
            if not target.exists():
                errors.append(f"{rel}: local action path does not exist: {local_action.group('path')}")

        for upstream in _workflow_run_targets(text):
            if "$" in upstream or "${{" in upstream:
                continue
            if upstream not in known_names:
                errors.append(f"{rel}: workflow_run references unknown workflow name: {upstream}")

        for block in _run_blocks(text):
            file_scan_block = _without_unittest_discover_patterns(block)
            for token in _REPO_FILE_RE.findall(file_scan_block):
                target = _resolve_local(root_path, token)
                if not target.exists():
                    errors.append(f"{rel}: run block references missing repository file: {token}")

            for module in _unittest_modules(block):
                target = root_path / _module_path(module)
                if not target.is_file():
                    errors.append(f"{rel}: unittest module does not exist: {module} -> {_module_path(module)}")

            for match in _GH_WORKFLOW_RUN_RE.finditer(block):
                target = match.group("double") or match.group("single") or match.group("bare") or ""
                target = target.strip()
                if not target or "$" in target or "${{" in target or target.isdigit():
                    continue
                if target.endswith((".yml", ".yaml")):
                    workflow_target = Path(target)
                    if workflow_target.parent == Path("."):
                        workflow_target = WORKFLOW_DIR / workflow_target
                    if not (root_path / workflow_target).is_file():
                        errors.append(f"{rel}: gh workflow run target file does not exist: {target}")
                elif target not in known_names:
                    errors.append(f"{rel}: gh workflow run references unknown workflow name: {target}")

    return sorted(set(errors))


def main() -> int:
    errors = validate()
    if errors:
        print("[WORKFLOW REFERENCE GUARD] FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("[WORKFLOW REFERENCE GUARD] PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
