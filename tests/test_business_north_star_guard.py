"""Pure offline regression for the binding AIIF business review contract."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import business_north_star_guard as guard


def valid_body():
    return ("Business authority: docs/AIIF_BUSINESS_NORTH_STAR.md\n\n" +
        "".join(f"### {name}\n" +
                "具体的な変更範囲、関連する既存資産、実環境で検証する指標を明示します。\n\n"
                for name in guard.HEADINGS))


class BusinessNorthStarGuardTest(unittest.TestCase):
    def test_repository_contract_has_all_required_components(self):
        guard.verify_repository()

    def test_approved_pr_shape(self):
        guard.verify_pr_body(valid_body())

    def test_unfilled_template_is_rejected(self):
        text = valid_body().replace(
            "具体的な変更範囲、関連する既存資産、実環境で検証する指標を明示します。",
            "（具体的な改善対象を記入）", 1)
        with self.assertRaisesRegex(guard.AlignmentError, "SECTION_UNFILLED"):
            guard.verify_pr_body(text)

    def test_missing_section_or_canonical_is_rejected(self):
        with self.assertRaisesRegex(guard.AlignmentError, "MISSING_CANONICAL"):
            guard.verify_pr_body("### 事業目的\n内容です")
        with self.assertRaisesRegex(guard.AlignmentError, "SECTION_MISSING"):
            guard.verify_pr_body(valid_body().replace("### オーナー承認", "### other"))

    def test_missing_agent_reference_fails_closed(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            for name in (guard.SOURCE, "AGENTS.md", ".github/PULL_REQUEST_TEMPLATE.md",
                         "PAID_PRODUCT_CONTRACT.md"):
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text((guard.ROOT / name).read_text(encoding="utf-8"),
                             encoding="utf-8")
            guard.verify_repository(root)
            (root / "AGENTS.md").write_text("missing", encoding="utf-8")
            with self.assertRaisesRegex(guard.AlignmentError, "AGENT_REFERENCE_MISSING"):
                guard.verify_repository(root)


if __name__ == "__main__":
    unittest.main()
