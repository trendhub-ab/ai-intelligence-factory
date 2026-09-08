#!/usr/bin/env python3
"""Run297: specimen-bound zero-model rebase of the existing Netflix GenRec Ready article.

This one-shot operational migration:
- targets exactly one Content Intelligence page by fixed sync_id/title/source/URL;
- accepts only the exact signed pre-Run296 Ready block;
- applies Run296's deterministic reader-surface transform (no prose regeneration);
- renders the reviewed three-line eyecatch without a provider/model call;
- stores the new eyecatch on a versioned GitHub path and attaches it to the same Notion page;
- appends one current Publication Contract Ready block only after the eyecatch is verified;
- never opens note.com and contains no public-release action.

The current Ready block is the commit point: a failure before that point leaves the source
non-current and therefore blocked by Note Ready fail-closed reconciliation.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

import note_ready_sync as sync
import publication_contract as contract
import run296_editorial_format_v2 as r296

TARGET_SYNC_ID = "3bd479ffdca9817f926aeaffbb779c4b"
TARGET_SOURCE = "HackerNews"
TARGET_URL_SLUG = "netflixtechblog.com/genrec-towards-llm-native-recommendation-at-netflix-f20be6f643e3"
PRE_RUN296_POLICY_SHA256 = "b1b4d1e9d5e52788dc16396480ca0b7097701dc9354d91fd299394296fd1cd45"
RICH_TEXT_LIMIT = 1900
EYECATCH_DIR = "eyecatch_images"
EYECATCH_DATE_LABEL = "2026.09"
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class Run297Error(RuntimeError):
    pass


def _caption_fields(value: str) -> dict[str, str]:
    text = str(value or "").strip()
    if not text.startswith(contract.READY_CAPTION_PREFIX):
        return {}
    fields: dict[str, str] = {}
    for token in text[len(contract.READY_CAPTION_PREFIX):].split("|"):
        if "=" not in token:
            return {}
        key, val = token.split("=", 1)
        key, val = key.strip(), val.strip()
        if not key or key in fields:
            return {}
        fields[key] = val
    return fields


def _is_exact_pre_run296_block(body: str, caption: str) -> bool:
    fields = _caption_fields(caption)
    manuscript_sha = fields.get("manuscript_sha256", "")
    return bool(
        fields.get("contract") == contract.CONTRACT_ID
        and fields.get("policy_sha256") == PRE_RUN296_POLICY_SHA256
        and _SHA_RE.fullmatch(manuscript_sha)
        and manuscript_sha == contract.manuscript_sha256(body)
    )


def _cta_url(markdown_text: str) -> str:
    heading_alt = "|".join(
        re.escape(item)
        for item in sorted(r296._LEGACY_CTA_HEADINGS, key=len, reverse=True)
    )
    heading = re.search(rf"(?m)^###\s+(?:{heading_alt})\s*$", str(markdown_text or ""))
    if heading is None:
        return ""
    link = re.search(r"\[[^\]]+\]\((https?://[^)]+)\)", markdown_text[heading.end():])
    return link.group(1) if link else ""


def transform_genrec_manuscript(old_body: str) -> str:
    body = str(old_body or "")
    if TARGET_URL_SLUG not in body.lower():
        raise Run297Error("target_primary_url_missing")
    if body.count(f"## {r296.INTRO_HEADING_OLD}") != 1:
        raise Run297Error("legacy_intro_not_exact")
    if body.count(f"**{r296.REMOVE_SUMMARY_LABEL}**") != 1:
        raise Run297Error("legacy_summary_row_not_exact")

    old_url = _cta_url(body)
    if not old_url:
        raise Run297Error("legacy_cta_url_missing")

    new_body = r296.normalize_article_format_v2(body)
    if new_body == body:
        raise Run297Error("run296_transform_was_noop")
    if f"## {r296.INTRO_HEADING_OLD}" in new_body:
        raise Run297Error("legacy_intro_survived")
    if r296.REMOVE_SUMMARY_LABEL in new_body:
        raise Run297Error("legacy_summary_row_survived")
    if new_body.count(f"## {r296.INTRO_HEADING_NEW}") != 1:
        raise Run297Error("new_intro_not_exact")
    if new_body.count(f"### {r296.CTA_HEADING}") != 1:
        raise Run297Error("new_cta_heading_not_exact")
    if new_body.count(r296.CTA_BODY) != 1:
        raise Run297Error("new_cta_body_not_exact")
    if new_body.count(f"[{r296.CTA_LINK_LABEL}]({old_url})") != 1:
        raise Run297Error("cta_tracking_url_changed")

    source_index = new_body.find("### Sources / Evidence")
    cta_index = new_body.find(f"### {r296.CTA_HEADING}")
    if source_index < 0 or cta_index < 0 or source_index >= cta_index:
        raise Run297Error("sources_cta_order_invalid")
    return new_body


def _current_code_block(body: str) -> dict[str, Any]:
    caption = contract.current_ready_caption(body)
    segments = [body[i:i + RICH_TEXT_LIMIT] for i in range(0, len(body), RICH_TEXT_LIMIT)]
    if "".join(segments) != body:
        raise Run297Error("notion_segmentation_changed_bytes")
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [
                {"type": "text", "text": {"content": segment}}
                for segment in segments
            ],
            "language": "markdown",
            "caption": [{"type": "text", "text": {"content": caption}}],
        },
    }


def _target_page() -> tuple[dict[str, Any], dict[str, Any]]:
    response = sync._request("GET", f"https://api.notion.com/v1/pages/{TARGET_SYNC_ID}")
    if response.status_code != 200:
        raise Run297Error(f"target_page_read_http_{response.status_code}")
    page = response.json()
    state = sync._source_state(page)
    if not state:
        raise Run297Error("target_source_not_active_ready")
    if state.get("sync_id") != TARGET_SYNC_ID:
        raise Run297Error("target_sync_id_drift")
    if state.get("source") != TARGET_SOURCE:
        raise Run297Error("target_source_drift")
    if TARGET_URL_SLUG not in str(state.get("primary_url") or "").lower():
        raise Run297Error("target_primary_url_drift")
    if not r296.is_genrec_title(str(state.get("title") or "")):
        raise Run297Error("target_title_drift")
    return page, state


def _legacy_and_current(page_id: str) -> tuple[str, str]:
    legacy: list[str] = []
    current: list[str] = []
    observed_legacy_policies: set[str] = set()
    for block in sync._block_children(page_id):
        body = sync._code_body(block)
        caption = sync._code_caption(block)
        if not body or not caption:
            continue
        if contract.is_current_ready_block(body, caption):
            current.append(body)
        fields = _caption_fields(caption)
        if (
            fields.get("contract") == contract.CONTRACT_ID
            and _SHA_RE.fullmatch(fields.get("policy_sha256", ""))
            and _SHA_RE.fullmatch(fields.get("manuscript_sha256", ""))
            and fields.get("manuscript_sha256") == contract.manuscript_sha256(body)
        ):
            if fields.get("policy_sha256") != contract.policy_sha256():
                observed_legacy_policies.add(fields["policy_sha256"])
        if _is_exact_pre_run296_block(body, caption):
            legacy.append(body)

    if len(legacy) != 1:
        short = ",".join(sorted(p[:12] for p in observed_legacy_policies))
        raise Run297Error(f"pre_run296_block_not_unique:{len(legacy)}:observed={short or 'none'}")
    if len(current) > 1:
        raise Run297Error("multiple_current_policy_blocks")
    return legacy[0], current[0] if current else ""


def _render_reviewed_eyecatch(output_path: Path, summary: str) -> str:
    import run181_eyecatch_visual_balance as r181

    output_path.parent.mkdir(parents=True, exist_ok=True)
    original_subheadline = r181._subheadline_lines
    try:
        r181._subheadline_lines = lambda *_args, **_kwargs: ([], 22)
        rendered = r181._render_balanced_plan(
            r296.GENREC_SOURCE_TITLE,
            summary,
            str(output_path),
            r296.genrec_validated_plan(),
            category="MODELS",
            date_label=EYECATCH_DATE_LABEL,
            highlight_text=r296.GENREC_HIGHLIGHT,
        )
    finally:
        r181._subheadline_lines = original_subheadline
    path = Path(rendered)
    if not path.is_file() or path.stat().st_size < 10_000:
        raise Run297Error("eyecatch_render_failed")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _github_asset_url(image_path: Path) -> tuple[str, str]:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    branch = os.environ.get("GITHUB_REF_NAME", "").strip() or "main"
    if not repo or not token:
        raise Run297Error("github_asset_credentials_missing")
    policy_prefix = contract.policy_sha256()[:12]
    dest_path = f"{EYECATCH_DIR}/genrec-run296-{policy_prefix}.png"
    api_url = f"https://api.github.com/repos/{repo}/contents/{dest_path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    image_bytes = image_path.read_bytes()
    local_sha = hashlib.sha256(image_bytes).hexdigest()

    existing = requests.get(api_url, headers=headers, params={"ref": branch}, timeout=30)
    if existing.status_code == 200:
        payload = existing.json()
        try:
            remote = base64.b64decode(str(payload.get("content") or "").replace("\n", ""))
        except Exception as exc:
            raise Run297Error("existing_asset_decode_failed") from exc
        if hashlib.sha256(remote).hexdigest() != local_sha:
            raise Run297Error("versioned_asset_conflict")
    elif existing.status_code == 404:
        payload = {
            "message": "Run297: persist reviewed GenRec Run296 eyecatch",
            "content": base64.b64encode(image_bytes).decode("ascii"),
            "branch": branch,
        }
        created = requests.put(api_url, headers=headers, json=payload, timeout=45)
        if created.status_code not in {200, 201}:
            raise Run297Error(f"asset_upload_http_{created.status_code}")
    else:
        raise Run297Error(f"asset_probe_http_{existing.status_code}")

    raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{dest_path}"
    return raw_url, local_sha


def _patch_eyecatch(page_id: str, raw_url: str) -> None:
    parsed = urlparse(raw_url)
    if parsed.scheme != "https" or parsed.hostname != "raw.githubusercontent.com":
        raise Run297Error("eyecatch_url_not_expected_https_github")
    payload = {
        "properties": {
            sync.SOURCE_EYECATCH: {
                "files": [{
                    "type": "external",
                    "name": f"genrec-run296-{contract.policy_sha256()[:12]}.png",
                    "external": {"url": raw_url},
                }]
            }
        }
    }
    response = sync._request(
        "PATCH",
        f"https://api.notion.com/v1/pages/{page_id}",
        json=payload,
    )
    if response.status_code != 200:
        raise Run297Error(f"notion_eyecatch_patch_http_{response.status_code}")
    verified = sync._source_state(response.json())
    if not verified or verified.get("eyecatch_url") != raw_url:
        get = sync._request("GET", f"https://api.notion.com/v1/pages/{page_id}")
        if get.status_code != 200:
            raise Run297Error("notion_eyecatch_verify_read_failed")
        verified = sync._source_state(get.json())
        if not verified or verified.get("eyecatch_url") != raw_url:
            raise Run297Error("notion_eyecatch_verify_failed")


def rebase_genrec_run296() -> dict[str, Any]:
    if not sync.NOTION_API_KEY:
        raise Run297Error("notion_key_missing")
    current_policy = contract.policy_sha256()
    if current_policy == PRE_RUN296_POLICY_SHA256:
        raise Run297Error("current_policy_did_not_advance")

    page, state = _target_page()
    page_id = str(page.get("id") or "").replace("-", "").lower()
    if page_id != TARGET_SYNC_ID:
        raise Run297Error("target_page_id_drift")

    old_body, existing_current = _legacy_and_current(TARGET_SYNC_ID)
    new_body = transform_genrec_manuscript(old_body)
    if existing_current and existing_current != new_body:
        raise Run297Error("conflicting_current_policy_body")

    props = page.get("properties") or {}
    summary = sync._text(props.get("これは何？")) or sync._text(props.get("元情報要約"))
    image_path = Path(".runtime/run297") / "genrec-run296.png"
    image_sha = _render_reviewed_eyecatch(image_path, summary)
    raw_url, uploaded_sha = _github_asset_url(image_path)
    if image_sha != uploaded_sha:
        raise Run297Error("asset_hash_mismatch")
    _patch_eyecatch(TARGET_SYNC_ID, raw_url)

    if not existing_current:
        block = _current_code_block(new_body)
        response = sync._request(
            "PATCH",
            f"https://api.notion.com/v1/blocks/{TARGET_SYNC_ID}/children",
            json={"children": [block]},
        )
        if response.status_code != 200:
            raise Run297Error(f"notion_manuscript_append_http_{response.status_code}")

    verified = sync._source_current_ready_manuscript(TARGET_SYNC_ID)
    if verified != new_body:
        raise Run297Error("current_manuscript_readback_mismatch")
    final_page = sync._request("GET", f"https://api.notion.com/v1/pages/{TARGET_SYNC_ID}")
    if final_page.status_code != 200:
        raise Run297Error("final_source_read_failed")
    final_state = sync._source_state(final_page.json())
    if not final_state or not final_state.get("eyecatch_url"):
        raise Run297Error("final_eyecatch_missing")
    if f"genrec-run296-{current_policy[:12]}.png" not in str(final_state["eyecatch_url"]):
        raise Run297Error("final_eyecatch_not_run296_version")

    return {
        "status": "already_current_repaired" if existing_current else "rebased",
        "sync_id": TARGET_SYNC_ID,
        "old_policy_sha256": PRE_RUN296_POLICY_SHA256,
        "new_policy_sha256": current_policy,
        "old_manuscript_sha256": contract.manuscript_sha256(old_body),
        "new_manuscript_sha256": contract.manuscript_sha256(new_body),
        "eyecatch_sha256": image_sha,
        "eyecatch_lines_exact": tuple(r296.GENREC_EYECATCH_LINES) == (
            "Netflix推薦の舞台裏", "LLMネイティブへ", "舵を切った理由"
        ),
        "intro_v2": True,
        "legacy_summary_removed": True,
        "cta_v2": True,
        "sources_before_cta": True,
        "zero_gemini_calls": True,
        "note_browser_started": False,
        "private_draft_created": False,
        "public_release": False,
    }


def main() -> int:
    result = rebase_genrec_run296()
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
