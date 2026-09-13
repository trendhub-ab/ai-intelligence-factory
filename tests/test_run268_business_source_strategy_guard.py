from __future__ import annotations

import tempfile
from pathlib import Path
import shutil
import unittest

import run268_business_source_strategy_guard as guard


class Run268BusinessSourceStrategyGuardTests(unittest.TestCase):
    def _copy_contract(self, root: Path) -> None:
        for relative in (guard.ACQUISITION, guard.LAYER, guard.ENTRYPOINT):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(guard.ROOT / relative, target)

    def test_current_repository_contract_passes(self):
        self.assertEqual([], guard.collect_errors(guard.ROOT))

    def test_guard_fails_if_producthunt_returns_to_active_source_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            layer = root / guard.LAYER
            text = layer.read_text(encoding="utf-8").replace(
                'ACTIVE_SOURCE_ORDER = ("GitHub", "HackerNews", "ArXiv", "OfficialVendor")',
                'ACTIVE_SOURCE_ORDER = ("GitHub", "HackerNews", "ArXiv", "ProductHunt", "OfficialVendor")',
            )
            layer.write_text(text, encoding="utf-8")
            self.assertIn("producthunt_present_in_active_source_order", guard.collect_errors(root))

    def test_guard_fails_if_primary_vendor_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            acquisition = root / guard.ACQUISITION
            text = acquisition.read_text(encoding="utf-8").replace('"vendor": "DeepSeek"', '"vendor": "DeepSeek REMOVED"')
            acquisition.write_text(text, encoding="utf-8")
            self.assertIn("official_vendor_missing:DeepSeek", guard.collect_errors(root))

    def test_guard_fails_if_producthunt_transport_returns(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            acquisition = root / guard.ACQUISITION
            acquisition.write_text(acquisition.read_text(encoding="utf-8") + '\nPRODUCTHUNT_ENDPOINT = "https://api.producthunt.com/v2/api/graphql"\n', encoding="utf-8")
            self.assertTrue(any("api.producthunt.com" in e for e in guard.collect_errors(root)))

    def test_guard_fails_if_source_layer_installs_before_runtime_layers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._copy_contract(root)
            entrypoint = root / guard.ENTRYPOINT
            text = entrypoint.read_text(encoding="utf-8")
            a = "    install_runtime_layers(pipeline)"
            b = "    install_run268_business_source_strategy(pipeline)"
            self.assertIn(a, text)
            self.assertIn(b, text)
            text = text.replace(a, "    __SWAP__", 1).replace(b, a, 1).replace("    __SWAP__", b, 1)
            entrypoint.write_text(text, encoding="utf-8")
            self.assertIn("source_strategy_must_install_after_runtime_layers", guard.collect_errors(root))


if __name__ == "__main__":
    unittest.main()
