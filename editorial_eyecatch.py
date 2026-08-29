import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from PIL import Image, ImageDraw, ImageFont

NOTE_EYECATCH_OUTPUT_DIR = os.environ.get("NOTE_EYECATCH_OUTPUT_DIR", "note_eyecatch_images")
WIDTH = 1280
HEIGHT = 670
BRAND_NAME = "AI Intelligence Factory"

_CATEGORY_RULES = (
    ("AI AGENTS", ("agent", "agentic", "multi-agent", "multi agent", "エージェント", "自律型")),
    ("SECURITY", ("security", "secure", "vulnerability", "vulnerab", "cve-", "attack", "jailbreak", "prompt injection", "セキュリティ", "脆弱", "攻撃", "安全性")),
    ("ROBOTICS", ("robot", "robotics", "ロボット", "ヒューマノイド")),
    ("MULTIMODAL", ("multimodal", "vision", "image generation", "video generation", "speech", "audio", "マルチモーダル", "画像生成", "動画生成", "音声")),
    ("MODELS", ("llm", "language model", "reasoning model", "transformer", "inference", "model", "モデル", "推論")),
    ("DEV TOOLS", ("developer", "sdk", "cli", "ide", "coding", "code generation", "repository", "github", "開発者", "開発ツール", "コーディング", "コード生成")),
    ("AI INFRA", ("gpu", "accelerator", "serving", "latency", "throughput", "hardware", "chip", "infrastructure", "推論基盤", "インフラ", "半導体", "ハードウェア")),
    ("DATA", ("database", "vector database", "retrieval", "rag", "data pipeline", "データベース", "検索拡張", "データ基盤")),
    ("AI BUSINESS", ("pricing", "enterprise", "startup", "business", "product launch", "revenue", "企業", "料金", "価格", "事業", "ビジネス")),
    ("RESEARCH", ("paper", "benchmark", "arxiv", "research", "研究", "論文", "ベンチマーク")),
)

_CATEGORY_ACCENTS = {
    "AI AGENTS": (49, 104, 229),
    "MODELS": (75, 88, 206),
    "DEV TOOLS": (31, 119, 180),
    "SECURITY": (82, 76, 180),
    "ROBOTICS": (43, 111, 170),
    "MULTIMODAL": (105, 79, 196),
    "AI INFRA": (52, 91, 163),
    "DATA": (25, 126, 146),
    "AI BUSINESS": (48, 104, 147),
    "RESEARCH": (67, 105, 190),
    "AI & TECH": (49, 104, 229),
}

_INTERNAL_PATTERNS = (
    r"Decision\s*Score\s*[:：]?\s*\d+(?:\s*/\s*100)?",
    r"意思決定スコア\s*[:：]?\s*\d+(?:\s*/\s*100)?",
    r"Technical\s*Impact\s*[:：]?\s*\d+",
    r"技術的破壊力\s*[:：]?\s*\d+",
    r"Urgency\s*[:：]?\s*\d+",
    r"緊急度\s*[:：]?\s*\d+",
    r"\b(?:NOW|TRY|WATCH|WAIT|AVOID)\b",
)


def infer_editorial_category(title: str = "", summary: str = "", source: str = "") -> str:
    text = f"{title}\n{summary}\n{source}".lower()
    for label, keywords in _CATEGORY_RULES:
        if any(keyword.lower() in text for keyword in keywords):
            return label
    return "AI & TECH"


def _clean_public_copy(text: str) -> str:
    value = re.sub(r"https?://\S+", "", text or "")
    value = re.sub(r"[#*_`>]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    for pattern in _INTERNAL_PATTERNS:
        value = re.sub(pattern, "", value, flags=re.I)
    value = re.sub(r"\s{2,}", " ", value).strip(" -—–｜|:：")
    return value


def editorial_hook_from_title(title: str, max_chars: int = 34) -> str:
    text = _clean_public_copy(title)
    text = re.sub(r"^【[^】]{1,28}】\s*", "", text)
    if not text:
        return "AIの変化を、わかりやすく。"
    candidates = [part.strip() for part in re.split(r"(?:\s*[｜|]\s*|\s+[—–―]{1,2}\s+|\s*[:：]\s*)", text) if part.strip()]
    if candidates and len(candidates[0]) >= 10:
        text = candidates[0]
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    punctuation = max(cut.rfind("、"), cut.rfind("。"), cut.rfind("？"), cut.rfind("!"), cut.rfind("！"))
    if punctuation >= max_chars // 2:
        cut = cut[: punctuation + 1]
    else:
        cut = cut.rstrip("、。！？!? ") + "…"
    return cut


def editorial_subheadline(summary: str, headline: str = "", max_chars: int = 48) -> str:
    text = _clean_public_copy(summary)
    if not text:
        return "難しい変化を、仕事と暮らしの目線で読み解く。"
    sentence = re.split(r"(?<=[。！？!?])\s*", text)[0].strip()
    if sentence and sentence not in headline:
        text = sentence
    if len(text) > max_chars:
        text = text[:max_chars].rstrip("、。！？!? ") + "…"
    return text or "難しい変化を、仕事と暮らしの目線で読み解く。"


def _font(paths: tuple[str, ...], size: int):
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _jp_font(size: int, bold: bool = True):
    if bold:
        paths = (
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        )
    else:
        paths = (
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        )
    return _font(paths, size)


def _latin_font(size: int, bold: bool = True):
    paths = (
        "/usr/share/fonts/truetype/lato/Lato-Bold.ttf" if bold else "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
        "/usr/share/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/truetype/dejavu/DejaVuSans.ttf",
    )
    return _font(paths, size)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return max(0, box[2] - box[0])


def _wrap_chars(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and _text_width(draw, candidate, font) > max_width:
            lines.append(current.rstrip())
            current = char.lstrip()
            if len(lines) >= max_lines:
                break
        else:
            current = candidate
    if len(lines) < max_lines and current:
        lines.append(current.rstrip())
    if "".join(lines) != text and lines:
        last = lines[-1].rstrip("、。！？!?… ")
        while last and _text_width(draw, last + "…", font) > max_width:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines[:max_lines]


def _fit_headline(draw: ImageDraw.ImageDraw, text: str, max_width: int = 760, max_lines: int = 3):
    for size in range(82, 49, -2):
        font = _jp_font(size, bold=True)
        lines = _wrap_chars(draw, text, font, max_width, max_lines)
        if lines and len(lines) <= max_lines and all(_text_width(draw, line, font) <= max_width for line in lines):
            return font, lines
    font = _jp_font(48, bold=True)
    return font, _wrap_chars(draw, text, font, max_width, max_lines)


def _light(color: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(int(round(channel + (255 - channel) * factor)) for channel in color)


def _draw_brand(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int]) -> None:
    x0, baseline = 42, 75
    bar_width = 9
    heights = (16, 24, 34, 45)
    for index, height in enumerate(heights):
        fill = accent if index < 3 else (10, 35, 73)
        x = x0 + index * 13
        draw.rectangle((x, baseline - height, x + bar_width, baseline), fill=fill)
    draw.text((104, 36), BRAND_NAME, font=_latin_font(27, bold=True), fill=(10, 35, 73))


def _draw_tags(draw: ImageDraw.ImageDraw, category: str, date_label: str, accent: tuple[int, int, int]) -> None:
    tag_font = _latin_font(24, bold=True)
    date_font = _latin_font(23, bold=True)
    category_w = _text_width(draw, category, tag_font) + 48
    date_w = _text_width(draw, date_label, date_font) + 40
    gap = 14
    right = WIDTH - 44
    date_box = (right - date_w, 32, right, 80)
    category_box = (date_box[0] - gap - category_w, 32, date_box[0] - gap, 80)
    draw.rounded_rectangle(category_box, radius=9, fill=accent)
    draw.rounded_rectangle(date_box, radius=9, fill=(252, 253, 255), outline=(198, 210, 228), width=2)
    draw.text((category_box[0] + 24, 43), category, font=tag_font, fill=(255, 255, 255))
    draw.text((date_box[0] + 20, 43), date_label, font=date_font, fill=(15, 35, 70))


def _draw_network_illustration(draw: ImageDraw.ImageDraw, accent: tuple[int, int, int]) -> None:
    pale = _light(accent, 0.84)
    pale2 = _light(accent, 0.93)
    line = _light(accent, 0.58)

    # Calm layered wave at the bottom, matching the selected white editorial reference.
    draw.polygon([(650, 620), (760, 600), (885, 614), (1030, 590), (1280, 610), (1280, 670), (650, 670)], fill=pale2)
    draw.polygon([(760, 640), (910, 620), (1050, 638), (1180, 610), (1280, 622), (1280, 670), (760, 670)], fill=(247, 250, 255))

    cards = [
        (1000, 170, 1115, 244),
        (880, 300, 1005, 380),
        (1090, 286, 1218, 384),
        (1000, 430, 1125, 515),
    ]
    centers = []
    for x0, y0, x1, y1 in cards:
        centers.append(((x0 + x1) // 2, (y0 + y1) // 2))
        draw.rounded_rectangle((x0 + 4, y0 + 8, x1 + 4, y1 + 8), radius=13, fill=(229, 237, 249))
        draw.rounded_rectangle((x0, y0, x1, y1), radius=13, fill=(255, 255, 255), outline=pale, width=2)
        draw.line((x0 + 22, y0 + 29, x1 - 22, y0 + 29), fill=line, width=4)
        draw.line((x0 + 22, y0 + 46, x1 - 45, y0 + 46), fill=(197, 214, 238), width=3)
    # One chart card and one checklist card remain abstract; no topic-specific source logos.
    draw.ellipse((900, 319, 926, 345), fill=pale, outline=accent, width=2)
    draw.pieslice((900, 319, 926, 345), 270, 30, fill=accent)
    for yy in (315, 338, 361):
        draw.line((1110, yy, 1118, yy + 8), fill=accent, width=2)
        draw.line((1118, yy + 8, 1131, yy - 5), fill=accent, width=2)
        draw.line((1142, yy + 2, 1193, yy + 2), fill=line, width=3)

    # Network connectors.
    connectors = ((centers[0], centers[1]), (centers[0], centers[2]), (centers[1], centers[3]), (centers[2], centers[3]))
    for (ax, ay), (bx, by) in connectors:
        draw.line((ax, ay, bx, by), fill=line, width=2)
        mx, my = (ax + bx) // 2, (ay + by) // 2
        draw.ellipse((mx - 5, my - 5, mx + 5, my + 5), fill=accent)

    # Human and AI silhouettes facing one another, deliberately generic and non-photoreal.
    human = (38, 77, 139)
    draw.ellipse((768, 480, 842, 554), fill=_light(human, 0.78))
    draw.polygon([(792, 523), (824, 531), (858, 595), (750, 595)], fill=_light(human, 0.88))
    draw.polygon([(776, 493), (796, 469), (829, 474), (844, 495), (830, 510), (808, 497), (793, 515)], fill=human)

    ai_fill = _light(accent, 0.72)
    draw.ellipse((1125, 480, 1203, 558), fill=ai_fill, outline=accent, width=2)
    draw.polygon([(1142, 540), (1187, 540), (1225, 600), (1098, 600)], fill=_light(accent, 0.86))
    draw.arc((1147, 498, 1186, 538), 200, 340, fill=accent, width=2)
    draw.ellipse((1158, 515, 1164, 521), fill=accent)
    draw.ellipse((1177, 515, 1183, 521), fill=accent)
    for radius in (15, 28, 42):
        draw.arc((1164 - radius, 520 - radius, 1164 + radius, 520 + radius), 300, 55, fill=line, width=1)


def generate_note_editorial_eyecatch(title: str, summary: str, output_path: str,
                                      category: str | None = None, date_label: str | None = None) -> str:
    category = (category or infer_editorial_category(title, summary)).strip() or "AI & TECH"
    accent = _CATEGORY_ACCENTS.get(category, _CATEGORY_ACCENTS["AI & TECH"])
    date_label = date_label or datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y.%m")
    headline = editorial_hook_from_title(title)
    subheadline = editorial_subheadline(summary, headline)

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    img = Image.new("RGB", (WIDTH, HEIGHT), (252, 253, 255))
    draw = ImageDraw.Draw(img)

    _draw_network_illustration(draw, accent)
    _draw_brand(draw, accent)
    _draw_tags(draw, category, date_label, accent)

    headline_font, headline_lines = _fit_headline(draw, headline, max_width=760, max_lines=3)
    navy = (7, 30, 66)
    y = 160
    line_gap = 10
    for line_text in headline_lines:
        bbox = draw.textbbox((0, 0), line_text, font=headline_font)
        draw.text((48, y - bbox[1]), line_text, font=headline_font, fill=navy)
        y += (bbox[3] - bbox[1]) + line_gap

    sub_y = min(535, max(485, y + 18))
    draw.rectangle((48, sub_y + 2, 53, sub_y + 42), fill=accent)
    sub_font = _jp_font(27, bold=True)
    sub_lines = _wrap_chars(draw, subheadline, sub_font, 725, 2)
    for index, line_text in enumerate(sub_lines):
        draw.text((72, sub_y + index * 38), line_text, font=sub_font, fill=(18, 42, 79))

    img.save(output_path, "PNG", optimize=True)
    return output_path
