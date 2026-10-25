"""Authenticated, bounded, private P5 checkpoint restoration.

Restore only a manually chosen encrypted Actions artifact using its Fernet key
from a repository secret. No raw article may enter Actions artifacts or logs.
"""
from __future__ import annotations

import io
import json
from pathlib import Path
import re
import zipfile

from cryptography.fernet import Fernet, InvalidToken

MAX_ARCHIVE_BYTES = 8 * 1024 * 1024
MAX_MEMBER_BYTES = 1024 * 1024


class CheckpointError(RuntimeError):
    pass


def open_checkpoint(
    encrypted: Path, secret_key: str, expected_manifest: dict,
) -> tuple[dict, dict, dict[str, bytes], int]:
    """Validate complete schema, content hashes, and fixed A-E prompt contract."""
    if not secret_key or not encrypted.is_file() or encrypted.is_symlink():
        raise CheckpointError("P5 encrypted checkpoint/key unavailable")
    if encrypted.stat().st_size > MAX_ARCHIVE_BYTES:
        raise CheckpointError("P5 checkpoint too large")
    try:
        plaintext = Fernet(secret_key.encode("ascii")).decrypt(encrypted.read_bytes())
    except (ValueError, UnicodeError, InvalidToken):
        raise CheckpointError("P5 checkpoint authentication failed") from None
    if len(plaintext) > MAX_ARCHIVE_BYTES:
        raise CheckpointError("P5 checkpoint plaintext too large")
    try:
        with zipfile.ZipFile(io.BytesIO(plaintext)) as archive:
            infos = archive.infolist()
            names = [z.filename for z in infos]
            if len(set(names)) != len(names) or len(names) > 12:
                raise CheckpointError("P5 checkpoint duplicate/excess members")
            if any(z.file_size > MAX_MEMBER_BYTES or z.is_dir() for z in infos):
                raise CheckpointError("P5 checkpoint invalid member")
            files = {z.filename: archive.read(z.filename) for z in infos}
        manifest = json.loads(files["manifest.json"])
        key = json.loads(files["KEY_OPEN_AFTER_SCORING.json"])
    except (KeyError, ValueError, zipfile.BadZipFile, UnicodeDecodeError, TypeError):
        raise CheckpointError("P5 checkpoint invalid archive") from None

    if manifest.get("status") != "INCOMPLETE_TECHNICAL_NO_GO":
        raise CheckpointError("P5 checkpoint not resumable")
    for field in ("checkpoint_schema", "arms", "model", "primary_models_by_arm",
                  "prompt_sha256", "transport", "config_flags",
                  "max_provider_requests", "case", "uses_extra_editor_persona"):
        if manifest.get(field) != expected_manifest.get(field):
            raise CheckpointError("P5 checkpoint experiment contract mismatch")
    arms = expected_manifest["arms"]
    if arms != list("ABCDE"):
        raise CheckpointError("P5 checkpoint requires five fixed arms")
    planned = {code: key.get(code) for code in arms}
    if set(planned.values()) != set("ABCDE"):
        raise CheckpointError("P5 checkpoint invalid blind assignment")
    completed = key.get("__actual_models_by_arm__")
    if not isinstance(completed, dict) or not 1 <= len(completed) < len(arms):
        raise CheckpointError("P5 checkpoint must contain a partial arm prefix")
    if list(completed) != arms[:len(completed)]:
        raise CheckpointError("P5 checkpoint completed arm order invalid")
    if any(v not in ("gemini-3.8-flash", "gemini-3.6-flash") for v in completed.values()):
        raise CheckpointError("P5 checkpoint actual-model provenance invalid")
    fallback = key.get("__fallback_used_by_arm__")
    if not isinstance(fallback, dict) or set(fallback) != set(completed):
        raise CheckpointError("P5 checkpoint fallback provenance invalid")
    if any(type(v) is not bool or v != (completed[c] !=
            expected_manifest["primary_models_by_arm"][c]) for c, v in fallback.items()):
        raise CheckpointError("P5 checkpoint inconsistent fallback provenance")
    count = len(completed)
    requests = manifest.get("gemini_requests")
    if type(requests) is not int or not count <= requests < 8:
        raise CheckpointError("P5 checkpoint exhausted/invalid request budget")
    candidates = manifest.get("candidates")
    labels = {planned[code] for code in completed}
    if not isinstance(candidates, dict) or set(candidates) != labels:
        raise CheckpointError("P5 checkpoint inconsistent candidates")
    allowed = {"manifest.json", "KEY_OPEN_AFTER_SCORING.json"}
    for label in labels:
        allowed.update((f"Candidate_{label}.md", f"Stages_Candidate_{label}.json"))
    if set(files) != allowed:
        raise CheckpointError("P5 checkpoint missing/extra files")
    import hashlib
    for label in labels:
        article = files[f"Candidate_{label}.md"]
        stages = files[f"Stages_Candidate_{label}.json"]
        if not article.endswith(b"\n") or not stages.endswith(b"\n"):
            raise CheckpointError("P5 checkpoint incomplete manuscript")
        data = candidates[label]
        if (hashlib.sha256(article[:-1]).hexdigest() != data.get("sha256")
                or hashlib.sha256(stages[:-1]).hexdigest() != data.get("stages_sha256")):
            raise CheckpointError("P5 checkpoint article checksum mismatch")
        try:
            steps = json.loads(stages)
        except (ValueError, UnicodeDecodeError):
            raise CheckpointError("P5 checkpoint stage data invalid") from None
        if (not isinstance(steps, dict) or len(steps) != data.get("stage_count")
                or not steps.get("Persona Article Generation")
                or not steps.get("Fact-Safe Review")):
            raise CheckpointError("P5 checkpoint stages inconsistent")
    return manifest, key, {k: v for k, v in files.items()
                           if k not in ("manifest.json", "KEY_OPEN_AFTER_SCORING.json")}, count
