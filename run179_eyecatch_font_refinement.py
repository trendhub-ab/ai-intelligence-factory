"""Run179: Google Fonts typography policy for public note eyecatches.

This layer keeps the Run178 semantic layout director unchanged while refining the
actual glyph faces used by the deterministic PIL renderer:
- title: Noto Sans JP, weight 900 (Black)
- subheadline: Noto Sans JP, weight 500 (Medium)
- Latin UI: Inter, weight 700 (Bold)

The Google Fonts variable font files are fetched only for a real production run,
from an immutable google/fonts commit, into a temporary directory outside the
repository.  If fetching or variable-font configuration fails, the renderer
falls back immediately to the already-installed system Noto/Lato fonts.
"""
from __future__ import annotations

import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

from PIL import ImageFont

import editorial_eyecatch as ee


GOOGLE_FONTS_COMMIT = "45b0855d499c093e4d1bd08926fec4e1a582e225"
_FONT_CACHE_DIR = Path(
    os.environ.get(
        "EYECATCH_GOOGLE_FONT_DIR",
        str(Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "ai-intelligence-factory-fonts"),
    )
)
NOTO_SANS_JP_PATH = _FONT_CACHE_DIR / "NotoSansJP-wght.ttf"
INTER_PATH = _FONT_CACHE_DIR / "Inter-opsz-wght.ttf"

_FONT_ASSETS = (
    (
        NOTO_SANS_JP_PATH,
        f"https://raw.githubusercontent.com/google/fonts/{GOOGLE_FONTS_COMMIT}/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf",
        5_000_000,
    ),
    (
        INTER_PATH,
        f"https://raw.githubusercontent.com/google/fonts/{GOOGLE_FONTS_COMMIT}/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
        500_000,
    ),
)

_TITLE_WEIGHT = 900
_SUBTITLE_WEIGHT = 500
_LATIN_BOLD_WEIGHT = 700
_TITLE_ROLE_MIN_SIZE = 40


def _valid_font_file(path: Path, min_bytes: int) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < min_bytes:
            return False
        with path.open("rb") as handle:
            header = handle.read(4)
        return header in {b"\x00\x01\x00\x00", b"OTTO", b"true", b"typ1"}
    except OSError:
        return False


def _download_font(url: str, target: Path, min_bytes: int) -> bool:
    if _valid_font_file(target, min_bytes):
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(target.suffix + ".part")
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "AI-Intelligence-Factory/Run179"})
        with urllib.request.urlopen(request, timeout=45) as response, partial.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
        if not _valid_font_file(partial, min_bytes):
            partial.unlink(missing_ok=True)
            return False
        os.replace(partial, target)
        return True
    except Exception:
        try:
            partial.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def ensure_google_font_assets(*, enabled: bool = True, logger: Any = None) -> dict[str, bool]:
    """Best-effort production bootstrap. Never makes eyecatch generation fail."""
    status: dict[str, bool] = {}
    if not enabled:
        return {str(path): _valid_font_file(path, minimum) for path, _url, minimum in _FONT_ASSETS}
    for path, url, minimum in _FONT_ASSETS:
        ok = _download_font(url, path, minimum)
        status[str(path)] = ok
        if logger is not None:
            if ok:
                logger.info("[RUN179 FONT] ready: %s", path.name)
            else:
                logger.warning("[RUN179 FONT FALLBACK] could not prepare %s; system font fallback will be used", path.name)
    return status


def _axis_label(axis: dict[str, Any]) -> str:
    raw = axis.get("name", "")
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="ignore")
        except Exception:
            raw = ""
    return str(raw).lower()


def _clamp_axis(value: float, axis: dict[str, Any]) -> float:
    minimum = float(axis.get("minimum", value))
    maximum = float(axis.get("maximum", value))
    return max(minimum, min(maximum, float(value)))


def _variable_font(path: Path, size: int, *, weight: int, optical_size: int | None = None):
    try:
        font = ImageFont.truetype(str(path), size)
    except OSError:
        return None

    get_axes = getattr(font, "get_variation_axes", None)
    set_axes = getattr(font, "set_variation_by_axes", None)
    if not callable(get_axes) or not callable(set_axes):
        return font
    try:
        axes = list(get_axes() or [])
        values: list[float] = []
        for axis in axes:
            label = _axis_label(axis)
            value = float(axis.get("default", axis.get("minimum", 0)))
            if "weight" in label:
                value = float(weight)
            elif "optical" in label and optical_size is not None:
                value = float(optical_size)
            values.append(_clamp_axis(value, axis))
        if values:
            set_axes(values)
    except Exception:
        # A Pillow build without complete variable-font support still renders the
        # downloaded family at its default axis values rather than failing.
        pass
    return font


def _static_font(paths: tuple[str, ...], size: int):
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def title_jp_font(size: int):
    font = _variable_font(NOTO_SANS_JP_PATH, size, weight=_TITLE_WEIGHT)
    if font is not None:
        return font
    return _static_font(
        (
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
        size,
    )


def subtitle_jp_font(size: int):
    font = _variable_font(NOTO_SANS_JP_PATH, size, weight=_SUBTITLE_WEIGHT)
    if font is not None:
        return font
    return _static_font(
        (
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ),
        size,
    )


def latin_ui_font(size: int, bold: bool = True):
    weight = _LATIN_BOLD_WEIGHT if bold else 400
    font = _variable_font(INTER_PATH, size, weight=weight, optical_size=size)
    if font is not None:
        return font
    return _static_font(
        (
            "/usr/share/fonts/truetype/inter/Inter-Bold.ttf" if bold else "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
            "/usr/share/fonts/truetype/lato/Lato-Bold.ttf" if bold else "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ),
        size,
    )


def _jp_font_by_role(size: int, bold: bool = True):
    # Run150/178 title sizes are >= 46/48px while subheadline sizes are <=30px.
    # This keeps both the deterministic fallback and the Gemini-directed renderer
    # on the same role-based font policy without changing approved layout geometry.
    if bold and int(size) >= _TITLE_ROLE_MIN_SIZE:
        return title_jp_font(int(size))
    return subtitle_jp_font(int(size))


def install(pipeline_module: Any) -> Any:
    """Install only font resolution; Run178 keeps ownership of line-break decisions."""
    if getattr(pipeline_module, "_RUN179_EYECATCH_FONT_REFINEMENT_INSTALLED", False):
        return pipeline_module

    ee._jp_font = _jp_font_by_role
    ee._latin_font = latin_ui_font

    pipeline_module._RUN179_EYECATCH_FONT_REFINEMENT_INSTALLED = True
    pipeline_module.RUN179_EYECATCH_TITLE_FONT = "Noto Sans JP Black (wght=900)"
    pipeline_module.RUN179_EYECATCH_SUBTITLE_FONT = "Noto Sans JP Medium (wght=500)"
    pipeline_module.RUN179_EYECATCH_LATIN_FONT = "Inter Bold (wght=700)"
    pipeline_module.RUN179_GOOGLE_FONTS_COMMIT = GOOGLE_FONTS_COMMIT
    return pipeline_module
