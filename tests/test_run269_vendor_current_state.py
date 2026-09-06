from __future__ import annotations

import unittest

from run269_vendor_current_state import (
    OFFICIAL_VENDOR_REGISTRY,
    _extract_recent_update,
    fetch_official_vendor_updates,
)
from source_normalization import normalize_item


class FakeResponse:
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url

    def raise_for_status(self):
        return None


class Run269VendorCurrentStateTests(unittest.TestCase):
    def test_bytedance_registry_uses_official_model_list_current_state(self):
        row = next(row for row in OFFICIAL_VENDOR_REGISTRY if row["vendor"] == "ByteDance Doubao/Seed")
        self.assertTrue(row["current_state_page"])
        self.assertIn("1799865", row["release_url"])

    def test_recent_update_timestamp_is_extracted_from_official_page_shape(self):
        self.assertEqual(
            "2026.07.20",
            _extract_recent_update("<div>模型列表</div><span>最近更新时间：2026.07.20 17:28:20</span>"),
        )

    def test_fallback_becomes_explicit_structured_current_state(self):
        vendor = {
            "vendor": "ByteDance Doubao/Seed",
            "region": "CN",
            "release_url": "https://example.com/models",
            "allowed_domains": ("example.com",),
            "current_state_page": True,
            "current_state_label": "公式モデル一覧",
        }
        html = "<h1>模型列表</h1><p>最近更新时间：2026.07.20 17:28:20</p>"

        rows = fetch_official_vendor_updates(
            1,
            normalize_item=normalize_item,
            http_get=lambda url, **kwargs: FakeResponse(html, url),
            registry=(vendor,),
        )
        self.assertEqual(1, len(rows))
        details = rows[0]["sourceDetails"]
        self.assertEqual("structured_current_state", details["vendor_record_kind"])
        self.assertTrue(details["current_state_page"])
        self.assertEqual("2026.07.20", rows[0]["publishedAt"])
        self.assertIn("リリースイベントではなく", rows[0]["sourceContext"])


if __name__ == "__main__":
    unittest.main()
