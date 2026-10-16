import os
import tempfile
import types
import unittest

from PIL import Image

import editorial_eyecatch as ee
import eyecatch_publication_contract as contract
import run178_eyecatch_editorial_layout_optimizer as run178


class _Logger:
    def warning(self, *_args, **_kwargs):
        return None


class Run178LongTitleFallbackRegressionTests(unittest.TestCase):
    def test_provider_failure_renders_full_long_public_title_without_ellipsis(self):
        provider_calls = []

        def provider(*_args, **_kwargs):
            provider_calls.append(1)
            raise RuntimeError("provider unavailable")

        fake = types.SimpleNamespace(
            generate_note_editorial_eyecatch=ee.generate_note_editorial_eyecatch,
            _generate_via_chat=provider,
            SYNTHETIC_REGRESSION_MODE=False,
            logger=_Logger(),
        )
        run178.install(fake)

        title = "OpenAIの新しいAIエージェント基盤は、企業の開発現場をどこまで変えるのか"
        summary = "一次情報を基に、導入判断に必要な変化と注意点を整理する。"
        self.assertGreater(len(title), 34)

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "long-title.png")
            result = fake.generate_note_editorial_eyecatch(
                title,
                summary,
                path,
                category="AI AGENTS",
                date_label="2026.10",
            )

            self.assertEqual(path, result)
            self.assertTrue(os.path.isfile(path))
            with Image.open(path) as image:
                self.assertEqual((1280, 670), image.size)
                self.assertEqual("RGB", image.mode)
                self.assertNotIn("…", str(image.info.get("aiif_expected_headline") or ""))

            self.assertEqual(title, contract.verify_image_headline(path, title))

        self.assertEqual(1, len(provider_calls))


if __name__ == "__main__":
    unittest.main()
