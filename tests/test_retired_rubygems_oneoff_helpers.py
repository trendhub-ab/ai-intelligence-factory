from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUARD = Path(__file__).resolve()

# Historical, article-specific RubyGems repair helpers whose issue_comment workflows
# were already retired. Run417 is intentionally NOT here: current Production still
# installs it through run190_note_persistent_cloud -> run194_note_persistent_cloud.
RETIRED_FILES = (
    "run413_oneoff_rubygems_manual_ready.py",
    "run414_rubygems_eyecatch.py",
    "run416_rubygems_zero_model_eyecatch.py",
    "run418_rubygems_canonical_eyecatch.py",
    "run419_rubygems_eyecatch_plan_repair.py",
    "run421_rubygems_zero_model_canonical_layout.py",
    "run422_rubygems_pinned_canonical_copy.py",
    "run425_rubygems_summary_restore.py",
    "tests/test_run414_rubygems_eyecatch.py",
    "tests/test_run416_zero_model_eyecatch.py",
    "tests/test_run418_rubygems_canonical_eyecatch.py",
    "tests/test_run419_eyecatch_plan_repair.py",
    "tests/test_run421_zero_model_canonical_layout.py",
    "tests/test_run422_pinned_canonical_copy.py",
    "tests/test_run425_summary_restore.py",
)

RETIRED_TOKENS = tuple(Path(path).stem for path in RETIRED_FILES)
EXECUTABLE_SUFFIXES = {".py", ".yml", ".yaml"}


def _active_reference_hits() -> list[tuple[str, str]]:
    excluded = {ROOT / path for path in RETIRED_FILES}
    excluded.add(GUARD)

    hits: list[tuple[str, str]] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in EXECUTABLE_SUFFIXES:
            continue
        if path in excluded or ".git" in path.parts or "docs" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        for token in RETIRED_TOKENS:
            if token in text:
                hits.append((str(path.relative_to(ROOT)), token))
    return hits


def test_retired_rubygems_helpers_have_no_active_references() -> None:
    assert _active_reference_hits() == []


def test_retired_rubygems_helpers_and_dedicated_tests_are_absent() -> None:
    leftovers = [path for path in RETIRED_FILES if (ROOT / path).exists()]
    assert leftovers == [], f"retired RubyGems helper/test files still present: {leftovers}"


def test_run417_body_verification_remains_on_current_production_path() -> None:
    run417 = ROOT / "run417_note_body_verification.py"
    run417_test = ROOT / "tests/test_run417_note_body_verification.py"
    run190 = (ROOT / "run190_note_persistent_cloud.py").read_text(encoding="utf-8")
    assert run417.is_file()
    assert run417_test.is_file()
    assert "import run417_note_body_verification as run417" in run190
    assert "run417.install(base)" in run190
