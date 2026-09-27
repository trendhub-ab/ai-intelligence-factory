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


def manifest_url(image_url: str) -> str:
    parsed = urlparse(str(image_url or "").strip())
    if parsed.scheme != "https" or not parsed.path.endswith(".png"):
        raise EyecatchContractError("invalid eyecatch image URL")
    return urlunparse(parsed._replace(path=parsed.path + ".json"))
