from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parent
SPEC_PATH = "AI_Intelligence_Factory_最終仕様書.md"

_METADATA_PATTERNS = {
    "spec_change_date": re.compile(r"^仕様最終変更日:\s*\*\*(\d{4}-\d{2}-\d{2})\*\*\s*$", re.MULTILINE),
    "production_review_date": re.compile(r"^Production最終照合日:\s*\*\*(\d{4}-\d{2}-\d{2})\*\*\s*$", re.MULTILINE),
    "production_contract_fingerprint": re.compile(
        r"^Production Contract Fingerprint:\s*\*\*`([0-9a-f]{64})`\*\*\s*$",
        re.MULTILINE,
    ),
    "implementation_audit_sha": re.compile(
        r"^実装監査基準SHA:\s*\*\*`([0-9a-f]{40})`\*\*\s*$",
        re.MULTILINE,
    ),
}

_EXCLUDED_PREFIXES = (
    "tests/",
    "docs/",
    ".runtime/",
)

_RUNTIME_CONFIG_NAMES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "Dockerfile",
    "runtime.txt",
}


def _normalise(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def is_production_surface(path: str) -> bool:
    """Return True for tracked surfaces whose bytes can alter Production behaviour/assets."""
    value = _normalise(path)
    if not value or value == SPEC_PATH:
        return False
    if value.startswith(_EXCLUDED_PREFIXES):
        return False
    if value.startswith(".github/workflows/"):
        return value.endswith((".yml", ".yaml"))
    if value.startswith(".github/actions/"):
        return True
    if value.startswith("assets/"):
        return True
    if value.startswith("local_skills/"):
        return True
    if value.endswith((".py", ".sh")):
        return True
    if Path(value).name in _RUNTIME_CONFIG_NAMES:
        return True
    return False


def fingerprint_entries(entries: Mapping[str, bytes | str]) -> str:
    """Hash the name + content digest of every Production surface deterministically."""
    digest = hashlib.sha256()
    for raw_path in sorted(entries):
        path = _normalise(raw_path)
        if not is_production_surface(path):
            continue
        payload = entries[raw_path]
        data = payload.encode("utf-8") if isinstance(payload, str) else bytes(payload)
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
        digest.update(b"\n")
    return digest.hexdigest()


def _git(*args: str, root: Path = ROOT) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.decode("utf-8", errors="strict")


def tracked_production_entries(root: Path = ROOT) -> dict[str, bytes]:
    raw = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    entries: dict[str, bytes] = {}
    for item in raw.decode("utf-8", errors="strict").split("\0"):
        if not item or not is_production_surface(item):
            continue
        candidate = root / item
        if not candidate.is_file():
            raise RuntimeError(f"tracked Production surface is unreadable: {item}")
        entries[item] = candidate.read_bytes()
    if not entries:
        raise RuntimeError("no tracked Production surfaces found")
    return entries


def production_contract_fingerprint(root: Path = ROOT) -> str:
    return fingerprint_entries(tracked_production_entries(root))


def latest_production_commit_date(root: Path = ROOT) -> str:
    """Return YYYY-MM-DD for the newest commit that touched a Production surface."""
    output = _git("log", "--date=short", "--pretty=format:__AIIF_COMMIT__%cs", "--name-only", "--no-renames", root=root)
    current_date: str | None = None
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("__AIIF_COMMIT__"):
            current_date = line.removeprefix("__AIIF_COMMIT__")
            continue
        if line and current_date and is_production_surface(line):
            return current_date
    raise RuntimeError("could not find a Production-surface commit in git history")


def _metadata_value(spec_text: str, key: str) -> str | None:
    match = _METADATA_PATTERNS[key].search(spec_text)
    return match.group(1) if match else None


def audit_metadata(
    spec_text: str,
    *,
    expected_fingerprint: str,
    latest_production_date: str,
) -> list[str]:
    failures: list[str] = []
    values = {key: _metadata_value(spec_text, key) for key in _METADATA_PATTERNS}

    for key, value in values.items():
        if value is None:
            failures.append(f"missing_or_invalid_{key}")

    if values["production_contract_fingerprint"] is not None:
        if values["production_contract_fingerprint"] != expected_fingerprint:
            failures.append("production_contract_fingerprint_mismatch")

    if values["production_review_date"] is not None:
        if values["production_review_date"] != latest_production_date:
            failures.append("production_review_date_stale")

    if values["spec_change_date"] and values["production_review_date"]:
        if values["spec_change_date"] > values["production_review_date"]:
            failures.append("spec_change_date_after_production_review")

    return failures


def audit_repository(root: Path = ROOT) -> tuple[list[str], str, str]:
    spec_file = root / SPEC_PATH
    if not spec_file.is_file():
        return ["canonical_spec_missing"], "", ""
    expected = production_contract_fingerprint(root)
    latest_date = latest_production_commit_date(root)
    failures = audit_metadata(
        spec_file.read_text(encoding="utf-8"),
        expected_fingerprint=expected,
        latest_production_date=latest_date,
    )
    return failures, expected, latest_date


def main() -> int:
    try:
        failures, expected, latest_date = audit_repository(ROOT)
    except (OSError, RuntimeError, subprocess.CalledProcessError, UnicodeError) as exc:
        print("SPECIFICATION_FRESHNESS_GUARD=FAIL")
        print(f"guard_error={type(exc).__name__}:{exc}")
        return 1

    if failures:
        print("SPECIFICATION_FRESHNESS_GUARD=FAIL")
        print(f"expected_production_contract_fingerprint={expected}")
        print(f"latest_production_commit_date={latest_date}")
        for failure in failures:
            print(f"failure={failure}")
        return 1

    print("SPECIFICATION_FRESHNESS_GUARD=PASS")
    print(f"production_contract_fingerprint={expected}")
    print(f"production_review_date={latest_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
