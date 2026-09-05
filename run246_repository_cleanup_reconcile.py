from pathlib import Path

REPLACEMENTS = {
    Path("README.md"): (
        "- **Current repository organization baseline:** Run201 — repository garbage cleanup without intended runtime behavior change",
        "- **Current repository organization baseline:** Run246 — falsified repository hygiene cleanup with active/runtime asset protection",
    ),
    Path("AI_Intelligence_Factory_最終仕様書.md"): (
        "Repository Organization Baseline: **Run201 — repository garbage cleanup without intended runtime behavior change**  ",
        "Repository Organization Baseline: **Run246 — falsified repository hygiene cleanup with active/runtime asset protection**",
    ),
    Path("tests/test_run200_repository_layout.py"): (
        "        self.assertIn(\"Current repository organization baseline:** Run201\", readme)\n        self.assertIn(\"repository garbage cleanup without intended runtime behavior change\", readme)",
        "        self.assertIn(\"Current repository organization baseline:** Run246\", readme)\n        self.assertIn(\"falsified repository hygiene cleanup with active/runtime asset protection\", readme)",
    ),
}


def main() -> None:
    for path, (old, new) in REPLACEMENTS.items():
        text = path.read_text(encoding="utf-8")
        old_count = text.count(old)
        new_count = text.count(new)
        if old_count == 0 and new_count == 1:
            continue
        if old_count != 1 or new_count != 0:
            raise RuntimeError(f"{path}: reconciliation preimage mismatch old={old_count} new={new_count}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("RUN246_RECONCILIATION=PASS")


if __name__ == "__main__":
    main()
