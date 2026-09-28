"""Fail-closed publication contract for public note eyecatch assets.

The article Publication Contract proves manuscript bytes.  Eyecatches need the same
property: an old PNG must not become current merely because it still exists at an HTTPS
URL.  This module binds one rendered image to the current public note title and the
current eyecatch rendering policy through a sidecar manifest.

No provider calls, browser actions, Notion writes, or publication actions live here.
"""
from __future__ import annotations

import hashlib
import json
import re
import base64
import zlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse


CONTRACT_ID = "aiif-eyecatch-v1"
ROOT = Path(__file__).resolve().parent

POLICY_FILES = (
    "editorial_eyecatch.py",
    "eyecatch_badge_taxonomy.py",
    "run178_eyecatch_editorial_layout_optimizer.py",
    "run179_eyecatch_font_refinement.py",
    "run180_eyecatch_semantic_layout.py",
    "run181_eyecatch_visual_balance.py",
    "run182_eyecatch_conclusion_emphasis.py",
    "run183_eyecatch_emphasis_scale.py",
    "eyecatch_publication_contract.py",
)

_TOKEN_RE = re.compile(r"__ecv1_([0-9a-f]{16})\.png$", re.I)


class EyecatchContractError(RuntimeError):
    pass


_ELLIPSIS_RE = re.compile(r"\.\.\.|…")


def headline_pnginfo(public_title: str, expected: str, rendered_lines: list[str]) -> PngImagePlugin.PngInfo:
    """Record the approved copy and the actual lines passed to the text renderer."""
    from PIL import PngImagePlugin
    rendered = "".join(rendered_lines)
    if not expected or not rendered or _ELLIPSIS_RE.search(expected + rendered):
        raise EyecatchContractError("eyecatch main headline contains an ellipsis or is empty")
    if re.sub(r"\s+", "", expected) != re.sub(r"\s+", "", rendered):
        raise EyecatchContractError("eyecatch rendered headline differs from approved copy")
    info = PngImagePlugin.PngInfo()
    info.add_text("aiif_public_title_sha256", title_sha256(public_title))
    info.add_text("aiif_expected_headline", expected)
    info.add_text("aiif_rendered_headline", rendered)
    return info


def bind_headline_pixels(image: Image.Image, info: PngImagePlugin.PngInfo,
                         runs: list[tuple[str, Any, int, int, tuple[int, int, int]]]) -> None:
    """Bind each expected glyph mask to ink actually present in the rendered image."""
    from PIL import Image, ImageDraw
    if not runs:
        raise EyecatchContractError("eyecatch headline was not drawn")
    records = []
    for text, font, x, y, color in runs:
        mask = Image.new("L", image.size, 0)
        draw = ImageDraw.Draw(mask)
        extent = draw.textbbox((x, y), text, font=font)
        if extent[0] < 0 or extent[1] < 0 or extent[2] > image.width or extent[3] > image.height:
            raise EyecatchContractError("eyecatch headline extends outside the image")
        draw.text((x, y), text, font=font, fill=255)
        box = mask.getbbox()
        if box is None:
            raise EyecatchContractError("eyecatch headline has no visible glyphs")
        x0, y0, x1, y1 = box
        opaque = bytes(1 if value == 255 else 0 for value in mask.crop(box).tobytes())
        if sum(opaque) < 8:
            raise EyecatchContractError("eyecatch headline lacks opaque glyph pixels")
        records.append([x0, y0, x1 - x0, y1 - y0, list(color),
                        base64.b64encode(zlib.compress(opaque)).decode("ascii")])
    info.add_text("aiif_headline_ink_v1", json.dumps(records, separators=(",", ":")))
    _check_headline_pixels(image, records)


def _check_headline_pixels(image: Image.Image, records: Any) -> None:
    if not isinstance(records, list) or not records or len(records) > 12:
        raise EyecatchContractError("eyecatch headline pixel proof is missing")
    for row in records:
        try:
            x, y, width, height, color, encoded = row
            if not (isinstance(x, int) and isinstance(y, int) and isinstance(width, int)
                    and isinstance(height, int) and isinstance(color, list) and len(color) == 3
                    and 0 <= x < image.width and 0 <= y < image.height
                    and 0 < width <= image.width - x and 0 < height <= image.height - y):
                raise ValueError("invalid pixel proof dimensions")
            decoder = zlib.decompressobj()
            bits = decoder.decompress(base64.b64decode(encoded), width * height + 1)
            if len(bits) != width * height or not decoder.eof or sum(bits) < 8:
                raise ValueError("incomplete glyph proof")
            pixels = image.crop((x, y, x + width, y + height)).convert("RGB").tobytes()
            foreground = bytes(color)
            if any(pixels[i * 3:i * 3 + 3] != foreground for i, bit in enumerate(bits) if bit):
                raise ValueError("rendered pixels differ from expected glyphs")
        except (TypeError, ValueError, IndexError, zlib.error, UnicodeError) as exc:
            raise EyecatchContractError("eyecatch headline pixels failed inspection") from exc


def verify_image_headline(image_path: str | Path, public_title: str) -> str:
    """Fail closed on absent, shortened, or ellipsized title evidence in saved PNG bytes."""
    from PIL import Image
    try:
        with Image.open(image_path) as image:
            if image.format != "PNG" or image.size != (1280, 670) or image.mode != "RGB":
                raise EyecatchContractError("eyecatch image has invalid format or geometry")
            expected = str(image.info.get("aiif_expected_headline") or "")
            rendered = str(image.info.get("aiif_rendered_headline") or "")
            digest = str(image.info.get("aiif_public_title_sha256") or "")
            pixel_proof = image.info.get("aiif_headline_ink_v1")
            if not isinstance(pixel_proof, str):
                raise EyecatchContractError("eyecatch headline pixel proof is missing")
            _check_headline_pixels(image, json.loads(pixel_proof))
    except (OSError, ValueError) as exc:
        raise EyecatchContractError("eyecatch image cannot be inspected") from exc
    if digest != title_sha256(public_title) or not expected or _ELLIPSIS_RE.search(expected + rendered):
        raise EyecatchContractError("eyecatch title proof is missing or contains an ellipsis")
    if re.sub(r"\s+", "", expected) != re.sub(r"\s+", "", rendered):
        raise EyecatchContractError("eyecatch rendered headline does not match expected headline")
    return expected


def _normalized_title(value: str) -> str:
    text = str(value or "").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def require_public_title(parsed: dict[str, Any]) -> str:
    """Return the approved public note title; never fall back to discovery/source names."""
    title = _normalized_title((parsed or {}).get("title_text", ""))
    if not title:
        raise EyecatchContractError("public note title is required for eyecatch generation")
    if "\n" in title or "\r" in title:
        raise EyecatchContractError("public note title must be one logical line")
    return title


def title_sha256(public_title: str) -> str:
    title = _normalized_title(public_title)
    if not title:
        raise EyecatchContractError("public note title is empty")
    return hashlib.sha256(title.encode("utf-8")).hexdigest()


def policy_sha256(root: Path | None = None) -> str:
    base = root or ROOT
    digest = hashlib.sha256()
    digest.update(b"AIIF_EYECATCH_POLICY_V1\0")
    for relative in POLICY_FILES:
        path = base / relative
        if not path.is_file():
            raise EyecatchContractError(f"eyecatch policy file is missing: {relative}")
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def image_sha256(path: str | Path) -> str:
    target = Path(path)
    if not target.is_file():
        raise EyecatchContractError("eyecatch image is missing")
    digest = hashlib.sha256()
    with target.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def asset_token(public_title: str, *, root: Path | None = None) -> str:
    digest = hashlib.sha256()
    digest.update(CONTRACT_ID.encode("utf-8"))
    digest.update(b"\0")
    digest.update(title_sha256(public_title).encode("ascii"))
    digest.update(b"\0")
    digest.update(policy_sha256(root).encode("ascii"))
    return digest.hexdigest()[:16]


def versioned_image_filename(base_filename: str, public_title: str, *, root: Path | None = None) -> str:
    base = Path(str(base_filename or "eyecatch.png")).name
    stem = Path(base).stem or "eyecatch"
    return f"{stem}__ecv1_{asset_token(public_title, root=root)}.png"


def manifest_filename(image_filename: str) -> str:
    name = Path(str(image_filename or "")).name
    if not name.endswith(".png"):
        raise EyecatchContractError("eyecatch manifest requires a PNG filename")
    return name + ".json"


def build_manifest(public_title: str, image_path: str | Path, *, root: Path | None = None) -> dict[str, str]:
    return {
        "contract_id": CONTRACT_ID,
        "policy_sha256": policy_sha256(root),
        "public_title_sha256": title_sha256(public_title),
        "image_sha256": image_sha256(image_path),
    }


def write_manifest(public_title: str, image_path: str | Path, *, root: Path | None = None) -> Path:
    image = Path(image_path)
    manifest_path = image.with_name(image.name + ".json")
    manifest_path.write_text(
        json.dumps(build_manifest(public_title, image, root=root), ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def validate_manifest(
    manifest: Any,
    public_title: str,
    image_path: str | Path,
    *,
    root: Path | None = None,
) -> bool:
    if not isinstance(manifest, dict):
        return False
    expected = build_manifest(public_title, image_path, root=root)
    return all(str(manifest.get(key) or "") == value for key, value in expected.items())


def validate_manifest_metadata(
    manifest: Any,
    public_title: str,
    *,
    root: Path | None = None,
) -> bool:
    if not isinstance(manifest, dict):
        return False
    return (
        str(manifest.get("contract_id") or "") == CONTRACT_ID
        and str(manifest.get("policy_sha256") or "") == policy_sha256(root)
        and str(manifest.get("public_title_sha256") or "") == title_sha256(public_title)
        and bool(re.fullmatch(r"[0-9a-f]{64}", str(manifest.get("image_sha256") or "")))
    )


def current_asset_url(url: str, public_title: str, *, root: Path | None = None) -> bool:
    """Prove URL naming is bound to the current title/policy before any download."""
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme != "https" or not parsed.path:
        return False
    name = Path(parsed.path).name
    match = _TOKEN_RE.search(name)
    return bool(match and match.group(1).lower() == asset_token(public_title, root=root))


def require_current_asset_url(url: str, public_title: str, *, root: Path | None = None) -> str:
    value = str(url or "").strip()
    if not current_asset_url(value, public_title, root=root):
        raise EyecatchContractError("eyecatch URL is not bound to the current title/policy")
    return value


def upload_current_asset_pair(
    uploader: Any,
    image_path: str | Path,
    base_filename: str,
    public_title: str,
    *,
    root: Path | None = None,
) -> str:
    """Upload image + current manifest atomically from the caller's perspective.

    The transport may leave an orphan image if the manifest upload fails, but the returned
    public URL stays empty so Notion/note can never consume an unproven asset.
    """
    verify_image_headline(image_path, public_title)
    image_filename = versioned_image_filename(base_filename, public_title, root=root)
    sidecar_path = write_manifest(public_title, image_path, root=root)
    image_url = str(uploader(str(image_path), image_filename) or "")
    if not image_url:
        return ""
    sidecar_url = str(uploader(str(sidecar_path), manifest_filename(image_filename)) or "")
    return image_url if sidecar_url else ""


def manifest_url(image_url: str) -> str:
    parsed = urlparse(str(image_url or "").strip())
    if parsed.scheme != "https" or not parsed.path.endswith(".png"):
        raise EyecatchContractError("invalid eyecatch image URL")
    return urlunparse(parsed._replace(path=parsed.path + ".json"))
