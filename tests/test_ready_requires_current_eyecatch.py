from __future__ import annotations

import types
import unittest

import eyecatch_publication_contract as eyecatch_contract
import runtime_layers


class ReadyRequiresCurrentEyecatchTests(unittest.TestCase):
    def _pipeline(self):
        calls: list[tuple[str, str, str]] = []

        def upgrade_notion_page_with_report(*, title_text: str = "", eyecatch_url: str = "", **kwargs):
            calls.append(("upgrade", title_text, eyecatch_url))
            return True

        def save_to_notion(*, title_text: str = "", eyecatch_url: str = "", **kwargs):
            calls.append(("save", title_text, eyecatch_url))
            return True

        pipeline = types.SimpleNamespace(
            upgrade_notion_page_with_report=upgrade_notion_page_with_report,
            save_to_notion=save_to_notion,
        )
        return pipeline, calls

    def test_ready_persistence_fails_closed_without_current_eyecatch(self):
        installer = getattr(runtime_layers, "install_ready_asset_contract", None)
        self.assertTrue(callable(installer), "runtime must install a Ready eyecatch asset contract")

        pipeline, calls = self._pipeline()
        installer(pipeline)

        self.assertFalse(
            pipeline.upgrade_notion_page_with_report(
                title_text="現行タイトル",
                eyecatch_url="",
            )
        )
        self.assertFalse(
            pipeline.save_to_notion(
                title_text="現行タイトル",
                eyecatch_url="https://example.com/legacy.png",
            )
        )
        self.assertEqual(calls, [])

    def test_ready_persistence_preserves_existing_path_for_current_eyecatch(self):
        installer = getattr(runtime_layers, "install_ready_asset_contract", None)
        self.assertTrue(callable(installer), "runtime must install a Ready eyecatch asset contract")

        pipeline, calls = self._pipeline()
        installer(pipeline)

        title = "現行タイトル"
        filename = eyecatch_contract.versioned_image_filename("article.png", title)
        current_url = f"https://example.com/{filename}"
        self.assertTrue(eyecatch_contract.current_asset_url(current_url, title))

        self.assertTrue(
            pipeline.upgrade_notion_page_with_report(
                title_text=title,
                eyecatch_url=current_url,
            )
        )
        self.assertTrue(
            pipeline.save_to_notion(
                title_text=title,
                eyecatch_url=current_url,
            )
        )
        self.assertEqual(
            calls,
            [
                ("upgrade", title, current_url),
                ("save", title, current_url),
            ],
        )


if __name__ == "__main__":
    unittest.main()
