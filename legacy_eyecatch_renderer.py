"""Isolated legacy/internal eyecatch renderer for Run231 Stage 2.

This module is deliberately provider-free and persistence-free. It contains only the
historical Pillow renderer retained for internal/regression compatibility. The live
note publication path continues to use ``editorial_eyecatch.generate_note_editorial_eyecatch``.

Run231 Stage 2 uses a strangler migration: production installs this implementation over
the legacy symbols exported by ``pipeline`` first; the duplicate historical block in
``pipeline.py`` is removed only after the complete zero-API regression proves parity.
"""
from __future__ import annotations

import os
import re

from PIL import Image, ImageDraw, ImageFont


_MIGRATION_MARKER = "__run231_stage2_legacy_eyecatch__"


def load_background(
    source: str,
    width: int,
    height: int,
    *,
    background_dir: str,
    source_background_image: dict,
    default_filename: str,
    logger,
) -> Image.Image | None:
    """Load/crop the historical source background without external I/O."""
    filename = source_background_image.get(source, default_filename)
    candidate_paths = [
        os.path.join(background_dir, filename),
        os.path.join(background_dir, default_filename),
    ]
    for path in candidate_paths:
        if os.path.exists(path):
            try:
                bg = Image.open(path).convert("RGB")
                src_w, src_h = bg.size
                target_ratio = width / height
                src_ratio = src_w / src_h
                if src_ratio > target_ratio:
                    new_h = height
                    new_w = int(src_ratio * new_h)
                else:
                    new_w = width
                    new_h = int(new_w / src_ratio)
                bg = bg.resize((new_w, new_h))
                left = (new_w - width) // 2
                top = (new_h - height) // 2
                return bg.crop((left, top, left + width, top + height))
            except Exception as exc:
                try:
                    logger.warning(f"[EYECATCH BG] {path} の読み込みに失敗しました: {exc}")
                except Exception:
                    pass
    return None


def extract_score_components(score_breakdown_text: str) -> tuple[int | None, int | None]:
    """Extract approved Technical Impact / Urgency values without recomputation."""
    text = str(score_breakdown_text or "")
    tech = re.search(r"Technical\s*Impact\s*[:：]?\s*(\d{1,2})\s*/\s*25", text, re.IGNORECASE)
    urgency = re.search(r"Urgency\s*[:：]?\s*(\d{1,2})\s*/\s*20", text, re.IGNORECASE)
    tech_value = int(tech.group(1)) if tech else None
    urgency_value = int(urgency.group(1)) if urgency else None
    if tech_value is not None and not 0 <= tech_value <= 25:
        tech_value = None
    if urgency_value is not None and not 0 <= urgency_value <= 20:
        urgency_value = None
    return tech_value, urgency_value


def score_color(score: int | float | None) -> tuple[int, int, int]:
    """Historical Decision Score band color contract."""
    try:
        value = max(0, min(100, int(score or 0)))
    except (TypeError, ValueError):
        value = 0
    if value <= 59:
        return (100, 116, 139)
    if value <= 69:
        return (34, 211, 238)
    if value <= 79:
        return (59, 130, 246)
    if value <= 89:
        return (139, 92, 246)
    return (245, 185, 66)


def vertical_center_shift(container_bounds: tuple[int, int], content_bounds: tuple[int, int]) -> int:
    container_top, container_bottom = container_bounds
    content_top, content_bottom = content_bounds
    container_center = (float(container_top) + float(container_bottom)) / 2.0
    content_center = (float(content_top) + float(content_bottom)) / 2.0
    return int(round(container_center - content_center))


def draw_text_stack_centered(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    rows: list[tuple[str, object, tuple[int, int, int, int]]],
    gaps: tuple[int, ...],
) -> tuple[int, int, int, int]:
    if len(gaps) != max(0, len(rows) - 1):
        raise ValueError("gaps must contain exactly len(rows)-1 values")
    if not rows:
        return box

    metrics = []
    for text, font, fill in rows:
        bbox = draw.textbbox((0, 0), text, font=font)
        metrics.append((text, font, fill, bbox, bbox[2] - bbox[0], bbox[3] - bbox[1]))

    total_height = sum(item[5] for item in metrics) + sum(gaps)
    box_center_y = (box[1] + box[3]) / 2.0
    cursor_top = box_center_y - total_height / 2.0
    box_center_x = (box[0] + box[2]) / 2.0

    visible_bounds = []
    for index, (text, font, fill, bbox, width, height) in enumerate(metrics):
        x = int(round(box_center_x - (bbox[0] + bbox[2]) / 2.0))
        y = int(round(cursor_top - bbox[1]))
        draw.text((x, y), text, font=font, fill=fill)
        visible_bounds.append((x + bbox[0], y + bbox[1], x + bbox[2], y + bbox[3]))
        cursor_top += height
        if index < len(gaps):
            cursor_top += gaps[index]

    return (
        min(b[0] for b in visible_bounds),
        min(b[1] for b in visible_bounds),
        max(b[2] for b in visible_bounds),
        max(b[3] for b in visible_bounds),
    )


def centered_pair_boxes(
    container: tuple[int, int, int, int],
    top: int,
    bottom: int,
    box_width: int,
    gap: int,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    container_center_x = (container[0] + container[2]) / 2.0
    group_width = box_width * 2 + gap
    left_x0 = int(round(container_center_x - group_width / 2.0))
    left_x1 = left_x0 + box_width
    right_x0 = left_x1 + gap
    right_x1 = right_x0 + box_width
    return (left_x0, top, left_x1, bottom), (right_x0, top, right_x1, bottom)


def _make_generate(pipeline_module):
    _draw_eyecatch_text_stack_centered = draw_text_stack_centered
    def generate_eyecatch_image(
        title_text: str,
        output_path: str = "eyecatch.png",
        source: str = "GitHub",
        decision_score: int | None = None,
        technical_impact: int | None = None,
        urgency: int | None = None,
        article_ready: bool = True,
    ) -> str | None:
        if not article_ready:
            pipeline_module.logger.info("[EYECATCH SKIP] article is not Ready")
            return None

        width, height = 1280, 670
        img = load_background(
            source,
            width,
            height,
            background_dir=pipeline_module.EYECATCH_BACKGROUND_DIR,
            source_background_image=pipeline_module.SOURCE_BACKGROUND_IMAGE,
            default_filename=pipeline_module.EYECATCH_BACKGROUND_DEFAULT,
            logger=pipeline_module.logger,
        )
        if img is None:
            img = Image.new("RGB", (width, height), color=(10, 15, 28))
            draw_bg = ImageDraw.Draw(img)
            for y in range(height):
                r = int(10 + (y / height) * 15)
                g = int(15 + (y / height) * 25)
                b = int(28 + (y / height) * 45)
                draw_bg.line([(0, y), (width, y)], fill=(r, g, b))

        score = max(0, min(100, int(decision_score or 0)))
        tech = None if technical_impact is None else max(0, min(25, int(technical_impact)))
        urg = None if urgency is None else max(0, min(20, int(urgency)))

        overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        card = (60, 78, 770, 592)
        draw.rounded_rectangle(card, radius=27, fill=(3, 13, 28, 205), outline=(205, 220, 239, 225), width=2)

        japanese_font_paths = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        lato_bold_paths = [
            "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
            "/usr/share/fonts/truetype/lato/Lato-Heavy.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]

        def text_font(size: int):
            for path in japanese_font_paths:
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
            return ImageFont.load_default()

        def number_font(size: int):
            for path in lato_bold_paths:
                try:
                    return ImageFont.truetype(path, size)
                except OSError:
                    continue
            return ImageFont.load_default()

        white = (250, 252, 255, 255)
        soft = (235, 241, 250, 255)
        border = (190, 207, 229, 225)
        accent = (*score_color(score), 255)
        bar_bg = (56, 70, 91, 235)

        def centered(text: str, cx: int, y: int, fnt, fill=white):
            bbox = draw.textbbox((0, 0), text, font=fnt)
            draw.text((cx - (bbox[0] + bbox[2]) / 2, y), text, font=fnt, fill=fill)

        title_label = "意思決定スコア  (Decision Score)"
        title_fnt = text_font(35)
        title_bbox = draw.textbbox((0, 0), title_label, font=title_fnt)
        nominal_title_y = 132
        nominal_lower_box_bottom = 548
        content_shift_y = vertical_center_shift(
            (card[1], card[3]),
            (nominal_title_y + title_bbox[1], nominal_lower_box_bottom),
        )

        centered(title_label, 415, nominal_title_y + content_shift_y, title_fnt)
        centered(f"{score}/100", 415, 204 + content_shift_y, number_font(88))

        bx0, by0, bx1, by1 = 108, 318 + content_shift_y, 722, 360 + content_shift_y
        draw.rounded_rectangle((bx0, by0, bx1, by1), radius=11, fill=bar_bg)
        progress_x = bx0 + int((bx1 - bx0) * score / 100)
        if progress_x > bx0:
            draw.rounded_rectangle((bx0, by0, progress_x, by1), radius=11, fill=accent)

        left_box, right_box = centered_pair_boxes(
            card,
            395 + content_shift_y,
            548 + content_shift_y,
            box_width=314,
            gap=18,
        )
        draw.rounded_rectangle(left_box, radius=18, fill=(2, 13, 29, 126), outline=border, width=2)
        draw.rounded_rectangle(right_box, radius=18, fill=(2, 13, 29, 126), outline=border, width=2)

        _draw_eyecatch_text_stack_centered(
            draw,
            left_box,
            [
                ("技術的破壊力", text_font(29), white),
                ("(Technical Impact)", text_font(19), soft),
                (f"{tech if tech is not None else '—'}/25", number_font(50), white),
            ],
            gaps=(8, 16),
        )
        _draw_eyecatch_text_stack_centered(
            draw,
            right_box,
            [
                ("緊急度", text_font(29), white),
                ("(Urgency)", text_font(19), soft),
                (f"{urg if urg is not None else '—'}/20", number_font(50), white),
            ],
            gaps=(8, 16),
        )

        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        img.save(output_path, "PNG")
        return output_path

    setattr(generate_eyecatch_image, _MIGRATION_MARKER, True)
    return generate_eyecatch_image


def install(pipeline_module):
    """Replace only the legacy/internal eyecatch surface; never the live editorial renderer."""
    current = getattr(pipeline_module, "generate_eyecatch_image", None)
    if getattr(current, _MIGRATION_MARKER, False):
        return pipeline_module

    live_editorial = getattr(pipeline_module, "generate_note_editorial_eyecatch", None)

    pipeline_module._load_eyecatch_background = lambda source, width, height: load_background(
        source,
        width,
        height,
        background_dir=pipeline_module.EYECATCH_BACKGROUND_DIR,
        source_background_image=pipeline_module.SOURCE_BACKGROUND_IMAGE,
        default_filename=pipeline_module.EYECATCH_BACKGROUND_DEFAULT,
        logger=pipeline_module.logger,
    )
    pipeline_module._extract_eyecatch_score_components = extract_score_components
    pipeline_module._eyecatch_score_color = score_color
    pipeline_module._eyecatch_vertical_center_shift = vertical_center_shift
    pipeline_module._draw_eyecatch_text_stack_centered = draw_text_stack_centered
    pipeline_module._eyecatch_centered_pair_boxes = centered_pair_boxes
    pipeline_module.generate_eyecatch_image = _make_generate(pipeline_module)

    # Fail closed on accidental scope expansion: the monetization/publication renderer must be
    # exactly the same callable after this compatibility install.
    if getattr(pipeline_module, "generate_note_editorial_eyecatch", None) is not live_editorial:
        raise RuntimeError("Run231 Stage2 touched the live editorial eyecatch renderer")
    return pipeline_module
