from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Run196RepositoryGuardContractTests(unittest.TestCase):
    def test_repository_guard_covers_shared_member_writer_lock(self):
        source = (ROOT / "repository_falsification_guard.py").read_text(encoding="utf-8")
        self.assertIn("member-derived-notion-writes", source)
        self.assertIn("member_notion_writer_not_shared_serialized", source)
        self.assertIn("subscriber_brief_rate_limit_contract_missing", source)
        self.assertIn("subscriber_brief_direct_notion_transport_bypass", source)


if __name__ == "__main__":
    unittest.main()