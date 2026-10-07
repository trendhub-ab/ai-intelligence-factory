from __future__ import annotations

import types
import unittest

import eyecatch_publication_contract as eyecatch_contract
import run296_editorial_format_v2 as editorial_format


class ReadyRequiresCurrentEyecatchTests(unittest.TestCase):
    def _pipeline(self):
        calls: list[tuple[str, str, str]] = []

        def upgrade_notion_page_with_report(
            page_id: str = "page",
            *,
            clean_manuscript: str = "",
            title_text: str = "",
            eyecatch_url: str = "",
            **kwargs,
        ):
            calls.append(("upgrade", title_text, eyecatch_url))
            return True

        def save_to_notion(
            repo_name: str = "repo",
            *,
            clean_manuscript: str = "",
            title_text: str = "",
            eyecatch_url: str = "",
            **kwargs,
        ):
            calls.append(("save", title_text, eyecatch_url))
            return True

        pipeline = types.SimpleNamespace(
            upgrade_notion_page_with_report=upgrade_notion_page_with_report,
            save_to_notion=save_to_notion,
        )
        return pipeline, calls

    def test_ready_persistence_fails_closed_without_current_eyecatch(self):
        pipeline, calls = self._pipeline()
        editorial_format.install_ready_asset_contract(pipeline)

        self.assertFalse(
            pipeline.upgrade_notion_page_with_report(
                clean_manuscript="本文",
                title_text="現行タイトル",
                eyecatch_url="",
            )
        )
        self.assertFalse(
            pipeline.save_to_notion(
                clean_manuscript="本文",
                title_text="現行タイトル",
                eyecatch_url="https://example.com/legacy.png",
            )
        )
        self.assertEqual(calls, [])

    def test_ready_persistence_preserves_existing_path_for_current_eyecatch(self):
        pipeline, calls = self._pipeline()
        editorial_format.install_ready_asset_contract(pipeline)

        title = "現行タイトル"
        filename = eyecatch_contract.versioned_image_filename("article.png", title)
        current_url = f"https://example.com/{filename}"
        self.assertTrue(eyecatch_contract.current_asset_url(current_url, title))

        self.assertTrue(
            pipeline.upgrade_notion_page_with_report(
                clean_manuscript="本文",
                title_text=title,
                eyecatch_url=current_url,
            )
        )
        self.assertTrue(
            pipeline.save_to_notion(
                clean_manuscript="本文",
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

    def test_wrappers_preserve_original_signatures_for_later_runtime_layers(self):
        pipeline, _calls = self._pipeline()
        original_upgrade = pipeline.upgrade_notion_page_with_report
        original_save = pipeline.save_to_notion
        editorial_format.install_ready_asset_contract(pipeline)

        import inspect

        self.assertEqual(inspect.signature(pipeline.upgrade_notion_page_with_report), inspect.signature(original_upgrade))
        self.assertEqual(inspect.signature(pipeline.save_to_notion), inspect.signature(original_save))


if __name__ == "__main__":
    unittest.main()
