from __future__ import annotations

import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import note_manuscript
import publication_contract
import publication_source_contract as source_contract
import run280_publication_dependency_guard as dependency_guard

ROOT = Path(__file__).resolve().parents[1]
READY_WORKFLOW = ROOT / ".github" / "workflows" / "note-ready-sync.yml"


def _load_note_ready_sync_without_external_dependency():
    if "note_ready_sync" in sys.modules:
        return sys.modules["note_ready_sync"]
    fake_requests = types.ModuleType("requests")
    with mock.patch.dict(sys.modules, {"requests": fake_requests}):
        return importlib.import_module("note_ready_sync")


def _rt(value: str) -> dict:
    return {"rich_text": [{"type": "text", "plain_text": value, "text": {"content": value}}]}


def _source_page(source: str) -> dict:
    return {
        "id": "12345678-1234-1234-1234-1234567890ab",
        "url": "https://www.notion.so/123456781234123412341234567890ab",
        "properties": {
            "記事状態": {"select": {"name": "Ready"}},
            "note記事タイトル": _rt("title"),
            "判断": {"select": {"name": "TRY"}},
            "情報源": {"select": {"name": source}},
            "元情報URL": {"url": "https://example.com/source"},
            "一次情報URL": _rt("https://example.com/primary"),
            "アイキャッチ": {
                "files": [{"type": "external", "external": {"url": "https://example.com/a.png"}}]
            },
        },
    }


class Run281SourceContractTests(unittest.TestCase):
    def test_active_public_source_contract_has_official_vendor_and_no_product_hunt(self) -> None:
        self.assertEqual(
            set(source_contract.ACTIVE_PUBLIC_SOURCES),
            {"GitHub", "HackerNews", "ArXiv", "OfficialVendor"},
        )
        self.assertIn("OfficialVendor", source_contract.SOURCE_RIGHTS_NOTE)
        self.assertNotIn("ProductHunt", source_contract.ACTIVE_PUBLIC_SOURCES)
        self.assertNotIn("ProductHunt", source_contract.SOURCE_RIGHTS_NOTE)
        self.assertEqual(source_contract.READER_SOURCE_LABELS["OfficialVendor"], "公式ベンダー")

    def test_note_ready_uses_exact_canonical_source_allowlist(self) -> None:
        note_ready_sync = _load_note_ready_sync_without_external_dependency()
        self.assertEqual(note_ready_sync.ALLOWED_SOURCES, set(source_contract.ACTIVE_PUBLIC_SOURCES))
        official = note_ready_sync._source_state(_source_page("OfficialVendor"))
        self.assertIsNotNone(official)
        self.assertEqual(official["source"], "OfficialVendor")
        self.assertIsNone(note_ready_sync._source_state(_source_page("ProductHunt")))

    def test_official_vendor_manuscript_has_current_rights_and_reader_label(self) -> None:
        manuscript = note_manuscript.build_clean_note_manuscript(
            "本文です。",
            "Vendor release",
            "https://vendor.example/release",
            "",
            source="OfficialVendor",
            title_text="公式アップデート",
            split_free_paid=lambda draft, _name: (draft, ""),
            display_heading_aliases=lambda _key: [],
            subscription_enabled=False,
            subscription_landing_url="",
            subscription_campaign_id="",
        )
        self.assertIn("発見経路**: 公式ベンダー", manuscript)
        self.assertIn("各ベンダーが公式に公開した一次情報", manuscript)
        self.assertNotIn("Product Hunt", manuscript)

    def test_public_source_contract_is_part_of_policy_fingerprint(self) -> None:
        self.assertIn("publication_source_contract.py", publication_contract.PUBLICATION_POLICY_FILES)
        self.assertIn("candidate_identity.py", publication_contract.PUBLICATION_POLICY_FILES)
        self.assertIn("eyecatch_badge_taxonomy.py", publication_contract.PUBLICATION_POLICY_FILES)


class Run281FanoutCausalityTests(unittest.TestCase):
    def test_parent_preflights_before_child_dispatch_and_pins_candidate(self) -> None:
        source = READY_WORKFLOW.read_text(encoding="utf-8")
        preflight = source.index("- name: Resolve exact private-draft fan-out eligibility")
        dispatch = source.index("- name: Dispatch private note draft flow only for an exact eligible Ready")
        self.assertLess(preflight, dispatch)
        block = source[dispatch:]
        self.assertIn("steps.fanout.outputs.eligible == 'true'", block)
        self.assertIn('sync_id="$SELECTED_SYNC_ID"', block)
        self.assertIn("run199_note_vm_preflight", source[preflight:dispatch])

    def test_push_can_never_run_fanout_preflight_or_dispatch(self) -> None:
        source = READY_WORKFLOW.read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("github.event_name == 'workflow_dispatch'"), 2)
        self.assertNotIn("workflow_run:", source)


class Run281RecursiveDependencyTests(unittest.TestCase):
    def test_every_policy_module_is_scanned_not_only_handpicked_roots(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".github/workflows").mkdir(parents=True)
            (root / "publication_contract.py").write_text(
                "PUBLICATION_POLICY_FILES = ('policy_leaf.py',)\n",
                encoding="utf-8",
            )
            (root / "policy_leaf.py").write_text("import hidden_public_helper\n", encoding="utf-8")
            (root / "hidden_public_helper.py").write_text("VALUE = 1\n", encoding="utf-8")
            (root / ".github/workflows/note-ready-sync.yml").write_text(
                "on:\n  push:\n    paths:\n      - 'policy_leaf.py'\n",
                encoding="utf-8",
            )
            with mock.patch.object(dependency_guard, "REQUIRED_PUBLICATION_DEPENDENCIES", ()):
                failures = dependency_guard.validate_repository(root)
            self.assertTrue(any("hidden_public_helper.py" in row for row in failures), failures)


if __name__ == "__main__":
    unittest.main(verbosity=2)
