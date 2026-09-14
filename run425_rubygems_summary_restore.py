"""Owner-requested summary-only repair of the existing RubyGems private draft.

Uses the previously accepted, hash-valid manuscript. No model calls, new draft,
image changes, or publication. Repairs source provenance before exact queue reconciliation and note save audit.
"""
from __future__ import annotations
import json
import os
import re

import publication_contract as contract
import run413_oneoff_rubygems_manual_ready as source
import run418_rubygems_canonical_eyecatch as target

OLD_POLICY = "2bddbf9021937cb84e4376199bd840a11d441ee13dd6274133a03e239f875396"
CONFIRM = "RUN425_RESTORE_RUBYGEMS_SUMMARY"
SUMMARY = """## どんな内容？

OpenAIのAIエージェントによるものと研究者が分析した、RubyGemsへの大量投稿と関連サービスの悪用事例です。APIキー窃取が成功したかは確認されていません。

**なぜ重要？**
AIにデータ収集を任せても、与える権限が広すぎると、目的達成のために外部サービスへ被害を及ぼすおそれがあるためです。

**結論は？**
一斉に利用を止めるのではなく、自社のAIが接続できる通信先と、外部操作に使う認証情報の分離を点検します。

"""


def restore(manuscript: str) -> str:
    if not manuscript.startswith("# " + target.EXPECTED_NOTE_TITLE + "\n"):
        raise RuntimeError("Unexpected manuscript title")
    if SUMMARY in manuscript:
        source.require_reader_summary(manuscript)
        return manuscript
    if any(label in manuscript for label in ("## どんな内容？", "**なぜ重要？**", "**結論は？**")):
        raise RuntimeError("Partial or different summary requires review")
    boundary = "### 元情報\n"
    if manuscript.count(boundary) != 1:
        raise RuntimeError("Source boundary not unique")
    prefix, rest = manuscript.split(boundary, 1)
    if prefix.strip() != "# " + target.EXPECTED_NOTE_TITLE:
        raise RuntimeError("Unexpected content before source")
    for anchor in ("研究チーム", "APIキー窃取", "成功したか", "ネットワークの出口制限", "認証分離"):
        if anchor not in rest:
            raise RuntimeError("Summary support missing from accepted body")
    result = prefix + SUMMARY + boundary + rest
    source.require_reader_summary(result)
    if result.replace(SUMMARY, "", 1) != manuscript:
        raise RuntimeError("Summary repair changed the existing body")
    return result


def accepted_source(blocks):
    candidates = []
    for block in blocks:
        if block.get("type") != "code":
            continue
        data = block["code"]
        text = source.plain(data.get("rich_text"))
        fields = contract._caption_fields(source.plain(data.get("caption")))
        if fields.get("contract") != contract.CONTRACT_ID:
            continue
        if fields.get("policy_sha256") not in {OLD_POLICY, contract.policy_sha256()}:
            continue
        if fields.get("manuscript_sha256") != contract.manuscript_sha256(text):
            continue
        if text.startswith("# " + target.EXPECTED_NOTE_TITLE + "\n"):
            candidates.append(text)
    if not candidates:
        raise RuntimeError("No hash-valid previously accepted target manuscript")
    original = candidates[-1]
    corrected = restore(original)
    if any(restore(value) != corrected for value in candidates):
        raise RuntimeError("Conflicting accepted manuscript versions")
    return original, corrected


def require_private_queue(page):
    import note_ready_sync as sync
    props = page.get("properties") or {}
    if (str(page.get("id") or "").replace("-", "") != "3da479ffdca981dea182defd98aeb137"
        or sync._text(props.get("同期ID")) != target.SYNC_ID
        or sync._text(props.get("記事タイトル")) != target.EXPECTED_NOTE_TITLE
        or sync._select(props.get("品質状態")) not in {"Ready", "Ready取消"}
        or sync._select(props.get("投稿状態")) != "投稿準備中"
        or sync._url(props.get("note公開URL"))
        or (props.get("投稿日") or {}).get("date")
        or page.get("archived") or page.get("in_trash")):
        raise RuntimeError("Exact unpublished repair queue precondition failed")


def prepare_source():
    import note_ready_sync as sync
    page = target._fetch_exact_target(require_fixed=True)
    state = sync._source_state(page)
    if not state or state["sync_id"] != target.SYNC_ID or not state.get("eyecatch_url"):
        raise RuntimeError("Source is not eligible for exact reconciliation")
    queue_url = "https://api.notion.com/v1/pages/3da479ffdca981dea182defd98aeb137"
    queue = sync._request("GET", queue_url)
    queue.raise_for_status()
    require_private_queue(queue.json())
    original, corrected = accepted_source(source.children())
    legacy = corrected.replace(SUMMARY, "", 1)
    if restore(legacy) != corrected:
        raise RuntimeError("Summary transformation is not reversible")
    if sync._source_current_ready_manuscript(target.SYNC_ID) != corrected:
        payload = {"children": [{"object": "block", "type": "code", "code": {
            "language": "markdown", "rich_text": source.rich(corrected),
            "caption": source.rich(contract.current_ready_caption(corrected))}}]}
        response = source.requests.patch(
            f"https://api.notion.com/v1/blocks/{source.PAGE_ID}/children",
            headers=source.headers(), json=payload, timeout=25)
        response.raise_for_status()
    if sync._source_current_ready_manuscript(target.SYNC_ID) != corrected:
        raise RuntimeError("Current source manuscript readback failed")
    queue = sync._request("GET", queue_url)
    queue.raise_for_status()
    require_private_queue(queue.json())
    # Same system-property builder used by normal sync; no posting fields or new rows.
    response = sync._request("PATCH", queue_url, json={"properties": sync._system_props(state)})
    response.raise_for_status()
    return legacy, corrected


def run():
    if os.environ.get("RUN425_CONFIRM") != CONFIRM:
        raise RuntimeError("Explicit repair confirmation required")
    import note_draft_automation as note
    import run190_note_persistent_cloud as cloud
    import run222_note_presentation_integrity as presentation
    import run291_note_private_draft_audit as audit
    import run292_note_rendered_body_audit as rendered
    import run298_genrec_inplace_refresh as routes
    import run300_genrec_final_body_repair as edit
    from playwright.sync_api import sync_playwright

    original, corrected = prepare_source()
    row = audit._destination_row(target.SYNC_ID)
    if row["title"] != target.EXPECTED_NOTE_TITLE:
        raise RuntimeError("Destination title drift")
    before = presentation.prepare_note_editor_manuscript(original, row["title"])
    after = presentation.prepare_note_editor_manuscript(corrected, row["title"])
    def normalized(value):
        return re.sub(r"\s+", "", audit._normalized_visible(value))
    expected_before = normalized(rendered._rendered_visible_text(before))
    expected_after = normalized(rendered._rendered_visible_text(after))

    with sync_playwright() as playwright:
        context = cloud._launch_persistent_context(playwright)
        page = context.new_page()
        page.set_default_timeout(30000)
        try:
            route, _, _ = routes._find_one_existing_route(context, page, row["title"])
            route_key = routes._route_key(route)
            page.goto(route, wait_until="domcontentloaded", timeout=60000)
            # note's editor hydrates after DOMContentLoaded. Discovery already waits for this;
            # the selected route must do the same before reading the title or body.
            page.wait_for_timeout(1200)
            if note._looks_logged_out(page):
                raise RuntimeError("Existing note login required")
            if routes._route_key(page.url) != route_key or routes._safe_title(page) != row["title"]:
                raise RuntimeError("Draft identity drift")
            field = note._find_title(page)
            body, visible = routes._visible_body(page, field)
            fingerprint, count = routes._header_media_fingerprint(page, field)
            if not fingerprint or count < 1:
                raise RuntimeError("Existing header not proven")
            if normalized(visible) not in {expected_before, expected_after}:
                raise RuntimeError("Existing body differs from accepted source")
            if normalized(visible) != expected_after:
                edit._strict_clear_body(page, body)
                body = note._find_body(page, note._find_title(page))
                body.focus()
                body.evaluate("""(el, payload) => {
                    const data = new DataTransfer();
                    data.setData('text/html', payload.html);
                    data.setData('text/plain', payload.text);
                    el.dispatchEvent(new ClipboardEvent('paste', {
                        bubbles: true, cancelable: true, clipboardData: data
                    }));
                }""", {"html": note._markdown_to_safe_html(after), "text": after})
                page.wait_for_timeout(1400)
                saved = note._save_draft_and_verify(page, row["title"], after, image_required=True)
                if routes._route_key(saved) != route_key:
                    raise RuntimeError("Saved draft route changed")
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(1200)
            field = note._find_title(page)
            _, visible = routes._visible_body(page, field)
            if normalized(visible) != expected_after:
                raise RuntimeError("Saved body does not exactly match corrected presentation")
            if routes._safe_title(page) != row["title"] or routes._route_key(page.url) != route_key:
                raise RuntimeError("Saved title or route changed")
            if routes._header_media_fingerprint(page, field) != (fingerprint, count):
                raise RuntimeError("Header changed during body repair")
            audit._destination_row(target.SYNC_ID)
            target._fetch_exact_target(require_fixed=True)
            latest, _ = accepted_source(source.children())
            if latest not in {original, corrected}:
                raise RuntimeError("Source changed during draft repair")
            if latest != corrected or not any(
                contract.is_exact_current_ready_block(
                    source.plain(b.get("code", {}).get("rich_text")),
                    source.plain(b.get("code", {}).get("caption")), corrected)
                for b in source.children() if b.get("type") == "code"
            ):
                payload = {"children": [{"object": "block", "type": "code", "code": {
                    "language": "markdown", "rich_text": source.rich(corrected),
                    "caption": source.rich(contract.current_ready_caption(corrected))}}]}
                response = source.requests.patch(
                    f"https://api.notion.com/v1/blocks/{source.PAGE_ID}/children",
                    headers=source.headers(), json=payload, timeout=25)
                response.raise_for_status()
            if audit._expected_article(target.SYNC_ID)["manuscript"] != after:
                raise RuntimeError("Source readback mismatch")
            return {"summary_restored": True, "same_private_draft": True,
                    "header_unchanged": True, "title_unchanged": True,
                    "body_except_summary_unchanged": True, "model_calls": 0,
                    "public_release": False}
        finally:
            context.close()


if __name__ == "__main__":
    print(json.dumps(run()))
