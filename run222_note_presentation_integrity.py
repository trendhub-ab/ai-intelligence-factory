"""Run222: keep public-note footer order and editor presentation human-clean.

Production intent:
- keep Sources / Evidence and the article disclaimer attached to the article itself;
- place the subscriber CTA after those trust/provenance blocks so the CTA is the final action;
- remove a duplicated leading H1 when note already has the same title in its title field;
- never expose a raw Markdown ``# `` heading in note body presentation;
- remove supported fenced-code language labels at the explicit note-presentation boundary because
  note readback does not preserve that metadata, while preserving code text byte-for-byte;
- preserve the stored current-publication-contract manuscript for validation before applying
  note-editor-only presentation transforms;
- require a current title/policy-bound eyecatch before a manuscript may persist as Ready;
- zero Gemini/model calls and no public-release action.
"""
from __future__ import annotations

import functools
import inspect
import re
from typing import Any

import eyecatch_publication_contract as eyecatch_contract

CTA_HEADINGS = {
    "「自分はどうする？」まで判断したい方へ",
    "調査と判断の時間を減らしたい方へ",
    "有料サブスクのご案内",
}
SOURCE_HEADING = "Sources / Evidence"
_FENCE_LANGUAGE = re.compile(r"^(\s*)```([A-Za-z0-9][A-Za-z0-9_+.#-]{0,39})\s*$")
_READY_ASSET_MARKER = "_run222_ready_asset_contract_installed"


def _plain_heading(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[*_`]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _find_h3(text: str, labels: set[str]) -> re.Match[str] | None:
    for match in re.finditer(r"(?m)^\s*###\s+(.+?)\s*$", text):
        if _plain_heading(match.group(1)) in labels:
            return match
    return None


def _preceding_divider(text: str, before: int, *, lower_bound: int = 0) -> int | None:
    matches = list(re.finditer(r"(?m)^\s*---\s*$", text[lower_bound:before]))
    if not matches:
        return None
    return lower_bound + matches[-1].start()


def move_subscription_cta_after_evidence(markdown_text: str) -> str:
    """Move the subscriber CTA after Sources/Evidence + disclaimer, idempotently.

    The function can normalize a manuscript that still has the pre-Run222 footer order, but the
    note browser path calls it only *after* the manuscript has satisfied the current Publication
    Contract. A manuscript stamped under an older policy must first be deterministically rebuilt
    and restamped under the current policy; stale provenance is never accepted or bypassed.
    """
    text = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    cta = _find_h3(text, CTA_HEADINGS)
    source = _find_h3(text, {SOURCE_HEADING})
    if cta is None or source is None or cta.start() > source.start():
        return text

    cta_start = _preceding_divider(text, cta.start())
    if cta_start is None:
        cta_start = cta.start()
    source_start = _preceding_divider(text, source.start(), lower_bound=cta.end())
    if source_start is None or source_start <= cta_start:
        source_start = source.start()

    cta_block = text[cta_start:source_start].strip()
    prefix = text[:cta_start].rstrip()
    evidence_and_disclaimer = text[source_start:].strip()
    if not cta_block or not evidence_and_disclaimer:
        return text
    parts = [part for part in (prefix, evidence_and_disclaimer, cta_block) if part]
    return "\n\n".join(parts).strip()


def _normalize_title(value: str) -> str:
    text = _plain_heading(value)
    text = text.replace("　", " ")
    return re.sub(r"\s+", " ", text).strip()


def _strip_duplicate_leading_h1(markdown_text: str, title: str) -> str:
    text = str(markdown_text or "").replace("\r\n", "\n").replace("\r", "\n")
    match = re.match(r"^\s*#\s+(.+?)\s*(?:\n+|$)", text)
    if match and _normalize_title(match.group(1)) == _normalize_title(title):
        text = text[match.end():]
    return text.lstrip("\n")


def strip_fenced_code_language_metadata(markdown_text: str) -> str:
    """Remove only simple fenced-code language labels before canonical note delivery.

    This is an explicit presentation transform required by the P0-A design: note's supported
    DOM/readback path proves code text and block boundaries, but not source fence metadata.  A
    simple language token such as ``python`` is therefore removed *before* canonicalization.
    Unsupported/compound info strings are deliberately left unchanged so the canonical parser
    rejects them fail-closed instead of silently discarding unknown metadata.
    """
    out: list[str] = []
    in_code = False
    for line in str(markdown_text or "").split("\n"):
        stripped = line.strip()
        if not in_code:
            match = _FENCE_LANGUAGE.fullmatch(line)
            if match:
                out.append(f"{match.group(1)}```")
                in_code = True
                continue
            if stripped == "```":
                in_code = True
        elif stripped == "```":
            in_code = False
        out.append(line)
    return "\n".join(out)


def _demote_body_h1_outside_code(markdown_text: str) -> str:
    """note title field is the document H1; body-level H1 becomes H2, code fences untouched."""
    out: list[str] = []
    in_code = False
    for line in str(markdown_text or "").split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
            out.append(line)
            continue
        if not in_code and re.match(r"^\s*#\s+\S", line):
            line = re.sub(r"^(\s*)#\s+", r"\1## ", line, count=1)
        out.append(line)
    return "\n".join(out)


def prepare_note_editor_manuscript(markdown_text: str, title: str) -> str:
    """Presentation-only transform applied after stored manuscript validation."""
    text = move_subscription_cta_after_evidence(markdown_text)
    text = _strip_duplicate_leading_h1(text, title)
    text = strip_fenced_code_language_metadata(text)
    text = _demote_body_h1_outside_code(text)
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def _ready_asset_decision(signature: inspect.Signature, args: tuple[Any, ...], kwargs: dict[str, Any]) -> bool | None:
    """Return None for non-manuscript writes, otherwise whether the Ready asset is current."""
    bound = signature.bind_partial(*args, **kwargs)
    manuscript = str(bound.arguments.get("clean_manuscript") or "")
    if not manuscript:
        return None
    public_title = str(bound.arguments.get("title_text") or "").strip()
    eyecatch_url = str(bound.arguments.get("eyecatch_url") or "").strip()
    return bool(public_title and eyecatch_contract.current_asset_url(eyecatch_url, public_title))


def _log_ready_asset_block(pipeline_module: Any, operation: str) -> None:
    logger = getattr(pipeline_module, "logger", None)
    warning = getattr(logger, "warning", None) if logger is not None else None
    if callable(warning):
        warning(
            "[READY ASSET CONTRACT BLOCK] %s refused: current title-bound eyecatch asset is required",
            operation,
        )


def install_ready_asset_contract(pipeline_module: Any) -> Any:
    """Fail closed before Ready persistence when its current eyecatch asset is absent/stale.

    The exact same deterministic ``current_asset_url`` contract is used by downstream note Ready
    synchronization.  This closes the upstream/downstream mismatch without retrying image
    generation, calling a model, mutating note, or changing non-manuscript persistence.
    """
    if getattr(pipeline_module, _READY_ASSET_MARKER, False):
        return pipeline_module

    original_upgrade = getattr(pipeline_module, "upgrade_notion_page_with_report", None)
    original_save = getattr(pipeline_module, "save_to_notion", None)
    if not callable(original_upgrade) or not callable(original_save):
        return pipeline_module

    upgrade_signature = inspect.signature(original_upgrade)
    save_signature = inspect.signature(original_save)

    @functools.wraps(original_upgrade)
    def upgrade_with_current_ready_asset(*args: Any, **kwargs: Any):
        decision = _ready_asset_decision(upgrade_signature, args, kwargs)
        if decision is False:
            _log_ready_asset_block(pipeline_module, "upgrade_notion_page_with_report")
            return False
        return original_upgrade(*args, **kwargs)

    @functools.wraps(original_save)
    def save_with_current_ready_asset(*args: Any, **kwargs: Any):
        decision = _ready_asset_decision(save_signature, args, kwargs)
        if decision is False:
            _log_ready_asset_block(pipeline_module, "save_to_notion")
            return False
        return original_save(*args, **kwargs)

    pipeline_module.upgrade_notion_page_with_report = upgrade_with_current_ready_asset
    pipeline_module.save_to_notion = save_with_current_ready_asset
    setattr(pipeline_module, _READY_ASSET_MARKER, True)
    pipeline_module.RUN222_READY_REQUIRES_CURRENT_EYECATCH = True
    return pipeline_module


def install_pipeline(pipeline_module: Any) -> Any:
    """Ensure newly generated canonical manuscripts end with the CTA after provenance."""
    # Install the Ready asset guard independently so lightweight tests or reused runtime objects
    # that already carry the presentation marker cannot silently skip the publication invariant.
    install_ready_asset_contract(pipeline_module)
    if getattr(pipeline_module, "_run222_pipeline_installed", False):
        return pipeline_module
    original = pipeline_module.build_clean_note_manuscript

    def build_clean_note_manuscript(*args: Any, **kwargs: Any) -> str:
        return move_subscription_cta_after_evidence(original(*args, **kwargs))

    pipeline_module.build_clean_note_manuscript = build_clean_note_manuscript
    pipeline_module._run222_pipeline_installed = True
    return pipeline_module


def install_note(note_module: Any) -> Any:
    """Transform only after whichever current-contract guard already wraps _prepare_article."""
    if getattr(note_module, "_run222_note_installed", False):
        return note_module
    original = note_module._prepare_article

    def _prepare_article(requested_sync_id: str = "") -> dict[str, Any]:
        article = original(requested_sync_id)
        article = dict(article)
        article["manuscript"] = prepare_note_editor_manuscript(
            str(article.get("manuscript") or ""), str(article.get("title") or "")
        )
        return article

    note_module._prepare_article = _prepare_article
    note_module._run222_note_installed = True
    return note_module
