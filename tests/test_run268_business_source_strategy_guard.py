from __future__ import annotations

import tempfile
from pathlib import Path
import shutil
import unittest

import run268_business_source_strategy_guard as guard


class Run268BusinessSourceStrategyGuardTests(unittest.TestCase):
    def test_current_repository_contract_passes(self):
        self.assertEqual([], guard.collect_errors(guard.ROOT))

    def test_guard_fails_if_producthunt_returns_to_active_source_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            required = (
                guard.ACQUISITION,
                guard.LAYER,
                guard.ENTRYPOINT,
                guard.PRODUCT,
                guard.SPEC,
                guard.WORKFLOW,
                guard.REFERENCE,
            )
            for relative in required:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(guard.ROOT / relative, target)
            layer = root / guard.LAYER
            text = layer.read_text(encoding="utf-8")
            text = text.replace(
                'ACTIVE_SOURCE_ORDER = ("GitHub", "HackerNews", "ArXiv", "OfficialVendor")',
                'ACTIVE_SOURCE_ORDER = ("GitHub", "HackerNews", "ArXiv", "ProductHunt", "OfficialVendor")',
            )
            layer.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertTrue(any("producthunt_present_in_active_source_order" in e for e in errors))

    def test_guard_fails_if_chinese_primary_vendor_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            required = (
                guard.ACQUISITION,
                guard.LAYER,
                guard.ENTRYPOINT,
                guard.PRODUCT,
                guard.SPEC,
                guard.WORKFLOW,
                guard.REFERENCE,
            )
            for relative in required:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(guard.ROOT / relative, target)
            acquisition = root / guard.ACQUISITION
            text = acquisition.read_text(encoding="utf-8").replace('"vendor": "DeepSeek"', '"vendor": "DeepSeek REMOVED"')
            acquisition.write_text(text, encoding="utf-8")
            errors = guard.collect_errors(root)
            self.assertIn("official_vendor_missing:DeepSeek", errors)


if __name__ == "__main__":
    unittest.main()
