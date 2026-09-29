import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, PngImagePlugin

import editorial_eyecatch as editorial
import eyecatch_publication_contract as contract
import run180_eyecatch_semantic_layout as semantic
import run181_eyecatch_visual_balance as impact
import note_draft_automation as note


class EyecatchHeadlineIntegrityTests(unittest.TestCase):
    def test_publication_contract_import_does_not_require_pillow(self):
        command = ("import sys; sys.modules['PIL'] = None; "
                   "import eyecatch_publication_contract; print('ok')")
        result = subprocess.run([sys.executable, "-c", command], cwd=Path(__file__).resolve().parents[1],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_long_headline_cannot_be_auto_ellipsized_by_base_renderer(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                editorial.generate_note_editorial_eyecatch(
                    "AIへの指示を最小化するLLM解説を自動で生成する仕組みは、開発現場で何を変えるのか",
                    "概要", str(Path(directory) / "cover.png"),
                )

    def test_model_title_containing_ellipsis_is_rejected_even_when_source_has_one(self):
        self.assertIsNone(semantic._validate_eyecatch_title("調査...続報", "調査..."))
        self.assertIsNone(semantic._validate_eyecatch_title("調査…続報", "調査…"))

    def test_invalid_primary_headline_retries_second_model_before_failing_closed(self):
        source = "LLM解説を自動で生成する仕組みは、開発現場で何を変えるのか"
        sub = "仕組みを読む。"
        calls = []

        def provider(model, *_args, **_kwargs):
            calls.append(model)
            copy = "LLM解説を自動で生…" if len(calls) == 1 else "LLM解説を自動で生成する"
            return SimpleNamespace(parsed={"eyecatch_title": copy, "title_lines": [copy],
                                           "title_font_size": 52, "title_line_gap": 12,
                                           "subheadline_lines": [sub], "subheadline_font_size": 24,
                                           "highlight_text": ""})

        @contextmanager
        def timeout_guard(_seconds):
            yield

        pipeline = SimpleNamespace(
            SYNTHETIC_REGRESSION_MODE=False,
            _generate_via_chat=provider,
            _gemini_call_timeout=timeout_guard,
        )
        result = semantic._request_layout_plan(pipeline, source, sub)
        self.assertEqual(result["eyecatch_title"], "LLM解説を自動で生成する")
        self.assertEqual(calls, ["gemini-3.6-flash", "gemini-3.5-flash"])

    def test_publication_asset_rejects_missing_or_wrong_rendered_headline(self):
        title = "AIへの指示を最小化するLLM解説を自動で生成する仕組み"
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "cover.png"
            Image.new("RGB", (1280, 670), "white").save(image)
            with self.assertRaises(contract.EyecatchContractError):
                contract.verify_image_headline(image, title)
            for expected, rendered in (("AIへの指示を最小化する", "AIへの指示を最小化す…"),
                                       ("AIへの指示を最小化する", "AIへの指示を最小化す"),
                                       ("AIへの指示を最小化する…", "AIへの指示を最小化する…")):
                info = PngImagePlugin.PngInfo()
                info.add_text("aiif_public_title_sha256", contract.title_sha256(title))
                info.add_text("aiif_expected_headline", expected)
                info.add_text("aiif_rendered_headline", rendered)
                Image.new("RGB", (1280, 670), "white").save(image, pnginfo=info)
                with self.assertRaises(contract.EyecatchContractError):
                    contract.verify_image_headline(image, title)

    def test_blank_png_with_matching_metadata_cannot_pass_post_render_gate(self):
        title = "AIへの指示を最小化するLLM解説"
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "blank.png"
            proof = contract.headline_pnginfo(title, title, [title])
            Image.new("RGB", (1280, 670), "white").save(image, pnginfo=proof)
            with self.assertRaises(contract.EyecatchContractError):
                contract.verify_image_headline(image, title)

    def test_rendered_plan_round_trip_proves_expected_headline(self):
        import run178_eyecatch_editorial_layout_optimizer as layout

        title = "AIへの指示を最小化するLLM解説"
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "cover.png"
            plan = {"eyecatch_title": "AIへの指示を最小化するLLM解説", "title_lines": ["AIへの指示を最小化する", "LLM解説"],
                    "title_font_size": 52, "title_line_gap": 12, "subheadline_lines": ["仕組みを読む。"],
                    "subheadline_font_size": 24}
            layout._render_with_validated_plan(title, "仕組みを読む。", str(image), plan)
            self.assertEqual(contract.verify_image_headline(image, title), plan["eyecatch_title"])
            with Image.open(image) as generated:
                metadata = PngImagePlugin.PngInfo()
                for key, value in generated.info.items():
                    if isinstance(value, str):
                        metadata.add_text(key, value)
            Image.new("RGB", (1280, 670), "white").save(image, pnginfo=metadata)
            with self.assertRaises(contract.EyecatchContractError):
                contract.verify_image_headline(image, title)
            layout._render_with_validated_plan(title, "仕組みを読む。", str(image), plan)
            with Image.open(image) as generated:
                invisible = generated.convert("RGBA")
                invisible.putalpha(0)
            invisible.save(image, pnginfo=metadata)
            with self.assertRaises(contract.EyecatchContractError):
                contract.verify_image_headline(image, title)
            plan["title_lines"] = ["AIへの指示を最小化する", "LLM解説…"]
            with self.assertRaises(contract.EyecatchContractError):
                layout._render_with_validated_plan(title, "仕組みを読む。", str(image), plan)

    def test_production_impact_renderer_preserves_approved_long_shortening(self):
        title = "AIへの指示を最小化するLLM解説を自動で生成する仕組みは、開発現場で何を変えるのか"
        expected = "AIへの指示を最小化するLLM解説"
        plan = {"eyecatch_title": expected, "title_lines": ["AIへの指示を最小化する", "LLM解説"],
                "title_font_size": 52, "title_line_gap": 12, "subheadline_lines": ["仕組みを読む。"],
                "subheadline_font_size": 24}
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "cover.png"
            impact._render_balanced_plan(title, "仕組みを読む。", str(image), plan)
            self.assertEqual(expected, contract.verify_image_headline(image, title))
            plan["title_lines"] = ["AIへの指示を最小化する", "LLM解…"]
            with self.assertRaises(contract.EyecatchContractError):
                impact._render_balanced_plan(title, "仕組みを読む。", str(image), plan)

    def test_note_download_rejects_ellipsized_image_before_browser_draft(self):
        title = "AIへの指示を最小化するLLM解説を自動で生成する仕組み"
        url = "https://example.org/" + contract.versioned_image_filename("cover.png", title)
        info = PngImagePlugin.PngInfo()
        info.add_text("aiif_public_title_sha256", contract.title_sha256(title))
        info.add_text("aiif_expected_headline", "AIへの指示を最小化するLLM解説")
        info.add_text("aiif_rendered_headline", "AIへの指示を最小化するLLM解説…")
        buffer = io.BytesIO()
        Image.new("RGB", (1280, 670), "white").save(buffer, format="PNG", pnginfo=info)
        image_bytes = buffer.getvalue()
        import hashlib
        manifest = {"contract_id": contract.CONTRACT_ID,
                    "policy_sha256": contract.policy_sha256(),
                    "public_title_sha256": contract.title_sha256(title),
                    "image_sha256": hashlib.sha256(image_bytes).hexdigest()}

        class Response:
            status_code = 200

            def __init__(self, payload):
                self.payload = payload

            def json(self):
                return self.payload

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def iter_content(self, _size):
                yield self.payload

        with tempfile.TemporaryDirectory() as directory, \
             patch.object(note, "ARTIFACT_DIR", Path(directory)), \
             patch.object(note.requests, "get", side_effect=[Response(manifest), Response(image_bytes)]):
            with self.assertRaisesRegex(note.NoteDraftError, "main headline failed final inspection"):
                note._download_eyecatch(url, "a" * 32, title)
            self.assertFalse((Path(directory) / ("a" * 32 + ".png")).exists())


if __name__ == "__main__":
    unittest.main()
