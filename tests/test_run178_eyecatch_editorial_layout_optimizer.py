import json
import os
import tempfile
import types
import unittest
from pathlib import Path

from PIL import Image

import editorial_eyecatch as ee
import run178_eyecatch_editorial_layout_optimizer as run178


ROOT = Path(__file__).resolve().parents[1]


class _Logger:
    def warning(self, *_args, **_kwargs):
        return None


class Run178EyecatchLayoutOptimizerTests(unittest.TestCase):
    def _headline(self):
        return "AIは重要。でも正直、もう追いきれない。"

    def _subheadline(self):
        return "仕事に必要なAIの変化だけを、短時間で判断する。"

    def _valid_plan(self):
        return {
            "title_lines": ["AIは重要。", "でも正直、", "もう追いきれない。"],
            "title_font_size": 68,
            "title_line_gap": 10,
            "subheadline_lines": ["仕事に必要なAIの変化だけを、", "短時間で判断する。"],
            "subheadline_font_size": 27,
        }

    def test_valid_plan_preserves_exact_copy_and_is_accepted(self):
        plan = run178.validate_layout_plan(self._headline(), self._subheadline(), self._valid_plan())
        self.assertIsNotNone(plan)
        self.assertEqual("".join(plan["title_lines"]), self._headline())
        self.assertEqual("".join(plan["subheadline_lines"]), self._subheadline())

    def test_model_rewrite_is_rejected(self):
        plan = self._valid_plan()
        plan["title_lines"][-1] = "もう追わなくていい。"
        self.assertIsNone(run178.validate_layout_plan(self._headline(), self._subheadline(), plan))

    def test_kinsoku_violation_is_rejected(self):
        headline = "AIは重要。でも追いきれない。"
        plan = {
            "title_lines": ["AIは重要", "。でも追いきれない。"],
            "title_font_size": 68,
            "title_line_gap": 10,
            "subheadline_lines": [self._subheadline()],
            "subheadline_font_size": 27,
        }
        self.assertIsNone(run178.validate_layout_plan(headline, self._subheadline(), plan))

    def test_font_size_is_bounded_and_fitted_deterministically(self):
        plan = self._valid_plan()
        plan["title_font_size"] = 120
        plan["subheadline_font_size"] = 99
        validated = run178.validate_layout_plan(self._headline(), self._subheadline(), plan)
        self.assertIsNotNone(validated)
        self.assertLessEqual(validated["title_font_size"], 82)
        self.assertLessEqual(validated["subheadline_font_size"], 30)

    def test_validated_renderer_keeps_note_1280x670_contract(self):
        validated = run178.validate_layout_plan(self._headline(), self._subheadline(), self._valid_plan())
        self.assertIsNotNone(validated)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "run178.png")
            result = run178._render_with_validated_plan(
                self._headline(),
                self._subheadline(),
                path,
                validated,
                category="AI & TECH",
                date_label="2026.09",
            )
            self.assertEqual(path, result)
            with Image.open(path) as image:
                self.assertEqual((1280, 670), image.size)
                self.assertEqual("RGB", image.mode)

    def test_install_uses_gemini_35_only_as_layout_director(self):
        calls = []
        original_calls = []
        response_plan = self._valid_plan()

        def provider(model_name, prompt, **kwargs):
            calls.append((model_name, prompt, kwargs))
            return types.SimpleNamespace(text=json.dumps(response_plan, ensure_ascii=False))

        def original(title, summary, output_path, category=None, date_label=None):
            original_calls.append((title, summary, output_path, category, date_label))
            return "fallback"

        fake = types.SimpleNamespace(
            generate_note_editorial_eyecatch=original,
            _generate_via_chat=provider,
            SYNTHETIC_REGRESSION_MODE=False,
            logger=_Logger(),
        )
        run178.install(fake)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "optimized.png")
            result = fake.generate_note_editorial_eyecatch(
                self._headline(), self._subheadline(), path, category="AI & TECH", date_label="2026.09"
            )
            self.assertEqual(path, result)
            self.assertTrue(os.path.isfile(path))

        self.assertEqual(1, len(calls))
        model_name, _prompt, kwargs = calls[0]
        self.assertEqual("gemini-3.5-flash", model_name)
        self.assertEqual("eyecatch_layout", kwargs["request_kind"])
        self.assertFalse(kwargs["count_as_deep_dive"])
        self.assertEqual("public_eyecatch_layout", kwargs["request_context"])
        self.assertEqual([], original_calls)

    def test_provider_failure_has_zero_retry_and_uses_approved_fallback(self):
        provider_calls = []
        original_calls = []

        def provider(*_args, **_kwargs):
            provider_calls.append(1)
            raise RuntimeError("provider unavailable")

        def original(title, summary, output_path, category=None, date_label=None):
            original_calls.append(1)
            return "fallback"

        fake = types.SimpleNamespace(
            generate_note_editorial_eyecatch=original,
            _generate_via_chat=provider,
            SYNTHETIC_REGRESSION_MODE=False,
            logger=_Logger(),
        )
        run178.install(fake)
        result = fake.generate_note_editorial_eyecatch("短いタイトルです", "短い要約です", "unused.png")
        self.assertEqual("fallback", result)
        self.assertEqual(1, len(provider_calls))
        self.assertEqual(1, len(original_calls))

    def test_synthetic_mode_is_strictly_zero_api(self):
        provider_calls = []

        def provider(*_args, **_kwargs):
            provider_calls.append(1)
            raise AssertionError("must not be called")

        def original(title, summary, output_path, category=None, date_label=None):
            return "fallback"

        fake = types.SimpleNamespace(
            generate_note_editorial_eyecatch=original,
            _generate_via_chat=provider,
            SYNTHETIC_REGRESSION_MODE=True,
            logger=_Logger(),
        )
        run178.install(fake)
        self.assertEqual("fallback", fake.generate_note_editorial_eyecatch("タイトル", "要約", "unused.png"))
        self.assertEqual([], provider_calls)

    def test_install_is_idempotent(self):
        fake = types.SimpleNamespace(
            generate_note_editorial_eyecatch=lambda *args, **kwargs: "fallback",
            _generate_via_chat=lambda *args, **kwargs: None,
            SYNTHETIC_REGRESSION_MODE=True,
            logger=_Logger(),
        )
        run178.install(fake)
        first = fake.generate_note_editorial_eyecatch
        run178.install(fake)
        self.assertIs(first, fake.generate_note_editorial_eyecatch)

    def test_production_entrypoint_installs_run178_after_run177(self):
        source = (ROOT / "production_pipeline.py").read_text(encoding="utf-8")
        self.assertIn("import run178_eyecatch_editorial_layout_optimizer", source)
        self.assertIn("run178_eyecatch_editorial_layout_optimizer.install(pipeline_module)", source)
        self.assertLess(
            source.index("run177_paid_funnel_alignment.install(pipeline_module)"),
            source.index("run178_eyecatch_editorial_layout_optimizer.install(pipeline_module)"),
        )

    def test_existing_reader_natural_break_contract_is_untouched(self):
        self.assertEqual(
            ee.balanced_headline_lines("AIに“同僚”ができ始めた。"),
            ["AIに“同僚”が", "でき始めた。"],
        )


if __name__ == "__main__":
    unittest.main()
