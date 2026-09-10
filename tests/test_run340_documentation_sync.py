from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import run340_documentation_sync as run340


class Run340DocumentationSyncTests(unittest.TestCase):
    def test_exact_canonical_patch_and_reference_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text(
                "\n".join((run340.README_BASELINE_ANCHOR, run340.README_HEADING_OLD, run340.README_REFS_OLD)),
                encoding="utf-8",
            )
            (root / "AI_Intelligence_Factory_最終仕様書.md").write_text(
                "\n".join((run340.SPEC_BASELINE_ANCHOR, run340.SPEC_HEADING_OLD, run340.SPEC_REFS_OLD)),
                encoding="utf-8",
            )
            run335 = root / "docs/reference/RUN335_NOTE_ONBOARDING_CUSTOMER_SURFACE_BASELINE.md"
            run335.parent.mkdir(parents=True, exist_ok=True)
            run335.write_text(run340.RUN335_RELATIONSHIP_OLD, encoding="utf-8")

            run340.sync_docs(root, cleanup=False)

            readme = (root / "README.md").read_text(encoding="utf-8")
            spec = (root / "AI_Intelligence_Factory_最終仕様書.md").read_text(encoding="utf-8")
            run335_text = run335.read_text(encoding="utf-8")
            ref = (root / "docs/reference/RUN339B_NOTE_PUBLIC_PURCHASE_FUNNEL_BASELINE.md").read_text(encoding="utf-8")

            self.assertIn("Current paid member note purchase funnel baseline", readme)
            self.assertIn("Run339b", readme)
            self.assertIn("3,969 ms", readme)
            self.assertIn("note_gql_auth_token", readme)
            self.assertIn("Paid Member note Purchase Funnel Baseline", spec)
            self.assertIn("Run339b workflow `34437339132`", spec)
            self.assertIn("Run339b artifact `10136678201`", spec)
            self.assertIn("RUN339B_NOTE_PUBLIC_PURCHASE_FUNNEL_BASELINE.md", run335_text)
            self.assertIn("Public purchase-funnel rendering", run335_text)
            self.assertIn("workflow run: `34437339132`", ref)
            self.assertIn("audit job: `102745213582`", ref)
            self.assertIn("artifact: `10136678201`", ref)
            self.assertIn("3,969 ms", ref)
            self.assertIn("explicit_auth_cookie_names_after=[]", ref)
            self.assertIn("0 clicks / 0 fills / 0 saves", ref)

    def test_exact_replace_fails_closed_on_missing_or_duplicate_anchor(self) -> None:
        with self.assertRaises(RuntimeError):
            run340._replace_once("", "x", "y", "missing")
        with self.assertRaises(RuntimeError):
            run340._replace_once("x x", "x", "y", "duplicate")

    def test_cleanup_is_limited_to_run338_diagnostic_and_run340_one_shot(self) -> None:
        expected = {
            ".github/workflows/note-membership-public-surface-diagnostic.yml",
            "run338_membership_public_surface_diagnostic.py",
            "tests/test_run338_membership_public_surface_diagnostic.py",
            ".github/workflows/run340-documentation-sync.yml",
            "run340_documentation_sync.py",
            "tests/test_run340_documentation_sync.py",
        }
        self.assertEqual(set(run340.CLEANUP_PATHS), expected)
        protected = {
            ".github/workflows/note-membership-public-funnel-audit.yml",
            "run339_membership_public_funnel_audit.py",
            "tests/test_run339_membership_public_funnel_audit.py",
            "run334_membership_description_exact_update.py",
        }
        self.assertTrue(protected.isdisjoint(set(run340.CLEANUP_PATHS)))

    def test_reference_preserves_customer_and_security_boundaries(self) -> None:
        text = run340.REFERENCE
        self.assertIn("AI Decision Intelligence", text)
        self.assertIn("¥1,980 / 月", text)
        self.assertIn("114 characters", text)
        self.assertIn("AI Decision Intelligence｜会員向け意思決定DB", text)
        self.assertIn("AI Decision Intelligence｜会員向けDigest", text)
        self.assertIn("https://note.com/trendhub_biz/membership/join", text)
        self.assertIn("note_gql_auth_token", text)
        self.assertIn("Any other cookie", text)
        self.assertIn("zero_gemini_calls=true", text)
        self.assertIn("notion_writes=0", text)


if __name__ == "__main__":
    unittest.main()
