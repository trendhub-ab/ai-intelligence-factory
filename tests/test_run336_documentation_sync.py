from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import run336_documentation_sync as run336


class Run336DocumentationSyncTests(unittest.TestCase):
    def test_exact_canonical_patch_and_reference_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "\n".join((run336.README_BASELINE_OLD, run336.README_HEADING_OLD, run336.README_ANCHOR)),
                encoding="utf-8",
            )
            (root / "AI_Intelligence_Factory_最終仕様書.md").write_text(
                "\n".join((run336.SPEC_BASELINE_OLD, run336.SPEC_HEADING_OLD, run336.SPEC_EVIDENCE_OLD)),
                encoding="utf-8",
            )
            run336.sync_docs(root, cleanup=False)
            readme = (root / "README.md").read_text(encoding="utf-8")
            spec = (root / "AI_Intelligence_Factory_最終仕様書.md").read_text(encoding="utf-8")
            ref = (root / "docs/reference/RUN335_NOTE_ONBOARDING_CUSTOMER_SURFACE_BASELINE.md").read_text(encoding="utf-8")

            self.assertIn(run336.README_BASELINE_NEW, readme)
            self.assertIn(run336.README_HEADING_NEW, readme)
            self.assertIn("Run334 / Run335", readme)
            self.assertNotIn(run336.README_BASELINE_OLD, readme)
            self.assertIn(run336.SPEC_BASELINE_NEW, spec)
            self.assertIn(run336.SPEC_HEADING_NEW, spec)
            self.assertIn("Run334 workflow `34433539671`", spec)
            self.assertIn("Run335 workflow `34433925788`", spec)
            self.assertIn("public_state=current", ref)
            self.assertIn("edit_state=current", ref)
            self.assertIn("Artifact: `10135503385`", ref)
            self.assertIn("do not resave", ref.lower())

    def test_exact_replace_fails_closed_on_missing_or_duplicate_marker(self) -> None:
        with self.assertRaises(RuntimeError):
            run336._replace_once("", "x", "y", "missing")
        with self.assertRaises(RuntimeError):
            run336._replace_once("x x", "x", "y", "duplicate")

    def test_cleanup_retires_only_one_shot_run335_and_run336_machinery(self) -> None:
        expected = {
            ".github/workflows/note-membership-description-postsave-audit.yml",
            "run335_membership_description_postsave_readonly_audit.py",
            "tests/test_run335_membership_description_postsave_readonly_audit.py",
            ".github/workflows/run336-documentation-sync.yml",
            "run336_documentation_sync.py",
            "tests/test_run336_documentation_sync.py",
        }
        self.assertEqual(set(run336.CLEANUP_PATHS), expected)
        self.assertFalse(any("run334_membership_description_exact_update.py" == p for p in run336.CLEANUP_PATHS))

    def test_reference_preserves_exact_customer_surface_invariants(self) -> None:
        text = run336.REFERENCE
        self.assertIn("AI Decision Intelligence", text)
        self.assertIn("¥1,980/月", text)
        self.assertIn("114 characters", text)
        self.assertIn("AI Decision Intelligence｜会員向け意思決定DB", text)
        self.assertIn("AI Decision Intelligence｜会員向けDigest", text)
        self.assertIn("Run334 saved successfully", text)
        self.assertIn("0 Gemini/model calls / 0 Notion writes", text)


if __name__ == "__main__":
    unittest.main()
