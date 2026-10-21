#!/usr/bin/env python3
"""Owner-authorized private-only Forget-Only replacement (zero model calls).

The manuscript remains in a PRIVATE Notion stage; never commit it to Git.
All writes target a pre-existing Ready source and exactly one unpublished queue
record with the stable draft ID. A failed partial application is fail-closed:
no new draft, no auto retry, no public release.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from PIL import Image, ImageDraw, ImageFont
import eyecatch_publication_contract as image_contract
import publication_contract
import note_ready_sync as sync
import ready_draft_regeneration as existing

STAGE_NAME = "AIIF｜Forget-Only記事の差し替え正本（非公開・未反映）"
ARTICLE_SHA256 = "ed8a3dd92195e364178091ac80d0106cb735886939c1e7873c9af1c6c4c17a9a"
DRAFT_ID_SHA256 = "26441aade090755c0c517cb80e16e33be30f32f99ef6cee398d2f17ee99975fb"
MASTER_URL = ("https://raw.githubusercontent.com/trendhub-ab/ai-intelligence-factory/"
              "runtime-state/eyecatch_images/"
              "Why_Forget-Only_Unlearning_Needs_Memorization__ecv1_3ddaad6906731d52.png")
MASTER_BLOB_SHA = "6364f83d83984a414a446bf401844d2a7f6adeef"
ASSET_BASENAME = "Why_Forget-Only_Unlearning_Needs_Memorization.png"
HOOK = "忘れるには、記憶が要る。"
REVIEW_STATUS = "Needs Editorial Review"


class SwapBlocked(RuntimeError):
    pass


def require(value: Any, message: str):
    if not value:
        raise SwapBlocked(message)


def notion(method: str, path: str, payload: dict | None = None) -> dict:
    response = sync._request(method, "https://api.notion.com/v1/" + path, json=payload)
    if response.status_code != 200:
        raise SwapBlocked("Notion operation refused: " + method + " " + path.split("/")[0]
                          + " HTTP " + str(response.status_code))
    return response.json()


def children(page_id: str) -> list[dict]:
    result = []
    cursor = ""
    for _ in range(12):
        url = "blocks/" + page_id + "/children?page_size=100"
        if cursor:
            url += "&start_cursor=" + cursor
        payload = notion("GET", url)
        result.extend(payload.get("results") or [])
        cursor = str(payload.get("next_cursor") or "")
        if not payload.get("has_more"):
            return result
        require(cursor, "Notion pagination cursor missing")
    raise SwapBlocked("Too many Notion block pages")


def rich_text(value: list[dict] | None) -> str:
    return "".join(str(v.get("plain_text") or (v.get("text") or {}).get("content") or "")
                   for v in value or [])


def stage_article() -> tuple[str, str]:
    res = sync._request("POST", "https://api.notion.com/v1/search",
                        json={"query": STAGE_NAME, "page_size": 50})
    require(res.status_code == 200, "Private Notion stage is not API-readable")
    exact = [x for x in res.json().get("results") or []
             if x.get("object") == "page"
             and rich_text(((x.get("properties") or {}).get("title") or {}).get("title")) == STAGE_NAME]
    require(len(exact) == 1, "Expected one exact private revision stage")
    candidate_blocks = [b for b in children(exact[0]["id"]) if b.get("type") == "code"
                        and (b.get("code") or {}).get("language") == "markdown"]
    require(len(candidate_blocks) == 1, "Expected single stage manuscript code block")
    article = rich_text(candidate_blocks[0]["code"].get("rich_text"))
    require(hashlib.sha256(article.encode("utf-8")).hexdigest() == ARTICLE_SHA256,
            "Staged manuscript is not the user-approved exact text")
    title = article.splitlines()[0].removeprefix("# ").strip()
    require(title and article.startswith("# " + title + "\n"), "Invalid approved article H1")
    require("## どんな内容？" in article and "### 元情報" in article,
            "Approved article structure is not complete")
    return article, title


def source_row(sync_id: str) -> tuple[dict, dict]:
    page = notion("GET", "pages/" + sync_id)
    state = sync._source_state(page)
    require(state and state["sync_id"] == sync_id, "Source is not exactly current Ready")
    require(sync._select((page.get("properties") or {}).get("コンテンツ状態")) == "Deep Dive",
            "Source is not Deep Dive")
    require(state.get("source") in sync.ALLOWED_SOURCES, "Unknown original source")
    return page, state


def queue_row(sync_id: str) -> dict:
    pages = sync._query_db(sync.DEST_DATA_SOURCE_ID, sync.DEST_DATABASE_ID,
          payload={"filter":{"property":"同期ID","rich_text":{"equals":sync_id}}})
    exact = [p for p in pages if sync._normalize_page_id(
        sync._text((p.get("properties") or {}).get("同期ID"))) == sync_id]
    require(len(exact) == 1, "Destination must be one existing queue row")
    p = exact[0]
    props = p.get("properties") or {}
    draft_id = sync._text(props.get("note下書きID"))
    require(hashlib.sha256(draft_id.encode("utf-8")).hexdigest() == DRAFT_ID_SHA256,
            "Unexpected draft ID")
    require(sync._select(props.get("投稿状態")) == "投稿準備中", "Draft must be private")
    require(sync._select(props.get("品質状態")) == "Ready", "Queue quality must be Ready")
    require(not sync._url(props.get("note公開URL")) and not ((props.get("投稿日") or {}).get("date")),
            "Public posting evidence exists")
    return p


def preflight(sync_id: str) -> dict:
    require(re.fullmatch(r"[a-fA-F0-9]{32}",sync_id), "Invalid source page ID")
    article, new_title = stage_article()
    page, state = source_row(sync_id)
    queue = queue_row(sync_id)
    props = queue["properties"]
    require(sync._text(props.get("記事タイトル")) == state["title"],
            "Old source/destination title drift")
    blocks = [b for b in children(sync_id)
              if b.get("type") == "code" and (b.get("code") or {}).get("language") == "markdown"]
    require(len(blocks) == 1, "Expected exactly one canonical Ready manuscript block")
    original = rich_text((blocks[0].get("code") or {}).get("rich_text"))
    caption = rich_text((blocks[0].get("code") or {}).get("caption"))
    require(publication_contract.is_current_ready_block(original,caption),
            "Source manuscript contract is not current")
    require(original.startswith("# " + state["title"] + "\n"), "Source title/body drift")
    require(image_contract.current_asset_url(state["eyecatch_url"],state["title"]),
            "Original cover is not current")
    require(new_title != state["title"],"Replacement title is already active")
    return {"article":article,"title":new_title,"old":original,"old_title":state["title"],
            "old_eyecatch":state["eyecatch_url"],"old_block":blocks[0],
            "queue_id":queue["id"],"draft_id":sync._text(props.get("note下書きID")),
            "source_id":sync_id}


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
                 "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc"):
        if Path(path).is_file():
            return ImageFont.truetype(path,size)
    raise SwapBlocked("Noto CJK Bold not installed; no visual fallback")


def render_cover(new_title: str, dest: Path) -> None:
    resp = requests.get(MASTER_URL,timeout=25)
    resp.raise_for_status()
    raw=resp.content
    blob=hashlib.sha1(b"blob "+str(len(raw)).encode()+bytes([0])+raw).hexdigest()
    require(blob==MASTER_BLOB_SHA,"Base image SHA mismatch")
    with Image.open(io.BytesIO(raw)) as im:
        require(im.format=="PNG" and im.size==(1280,670),"Base image dimensions invalid")
        master=im.convert("RGB")
    img=master.copy()
    draw=ImageDraw.Draw(img)
    # Preserve all typography outside the designated editable left-side zones.
    draw.rectangle((34,202,800,527), fill=(255,255,255))
    for x in range(801,841):
        a=(841-x)/40
        for y in range(202,528):
            p=master.getpixel((x,y))
            img.putpixel((x,y),tuple(round(255*a+(1-a)*v) for v in p))
    draw.text((48,212),HOOK,font=font(28),fill=(16,38,77))
    draw.rectangle((48,250,425,255),fill=(223,230,250))
    lines = ("AIに「忘れさせる」には、","なぜ記憶が必要なのか？")
    require("".join(lines)==new_title,"Approved headline must match new public title")
    size=61
    while size>=45 and max(draw.textbbox((0,0),line,font=font(size))[2]
                            for line in lines)>765:
        size-=1
    require(size>=45,"Headline cannot fit in user-approved two lines")
    face=font(size)
    runs=[]
    for line,y in zip(lines,(309,389)):
        draw.text((43,y),line,font=face,fill=(6,30,67))
        runs.append((line,face,43,y,(6,30,67)))
    info=image_contract.headline_pnginfo(new_title,new_title,list(lines))
    image_contract.bind_headline_pixels(img,info,runs)
    dest.parent.mkdir(parents=True,exist_ok=True)
    img.save(dest,format="PNG",pnginfo=info,optimize=True)
    image_contract.verify_image_headline(dest,new_title)


def page_properties(new_title: str,url: str) -> dict:
    return {"properties":{
       "note記事タイトル":{"rich_text":[{"type":"text","text":{"content":new_title}}]},
       "アイキャッチ":{"files":[{"name":url.rsplit("/",1)[-1],"type":"external",
                                 "external":{"url":url}}]},
       "記事状態":{"select":{"name":"Ready"}}
    }}


def apply(rev: dict) -> dict:
    import pipeline
    import run190_note_persistent_cloud as chrome
    require(os.environ.get("GH_PAT"),"GitHub token missing")
    require(os.environ.get("NOTE_STORAGE_STATE_B64"),"note Chrome login state missing")
    target=rev["source_id"]
    # Verify stable existing note edit route *before* any external mutation.
    chrome.install()
    existing_destination=existing.destination_preflight(target)
    route=existing.draft_route_preflight(existing_destination)
    require(existing_destination["note_draft_id"]==rev["draft_id"],"Draft drift")
    dest=Path(".runtime/private-forget-only-cover.png")
    render_cover(rev["title"],dest)
    pipeline.EYECATCH_GITHUB_BRANCH="runtime-state"
    pipeline.EYECATCH_GITHUB_DIR="eyecatch_images"
    cover_url=image_contract.upload_current_asset_pair(
        pipeline.upload_eyecatch_to_github,str(dest),ASSET_BASENAME,rev["title"])
    require(cover_url and image_contract.current_asset_url(cover_url,rev["title"]),
            "Versioned cover and current manifest upload failed")
    old_block=rev["old_block"]
    new_caption=publication_contract.current_ready_caption(
        rev["article"],
        style_name=publication_contract._caption_fields(
            rich_text((old_block.get("code") or {}).get("caption"))).get("style","classic"))
    # Fail closed while changing manuscript; no Ready status with mismatched bytes.
    notion("PATCH","pages/"+target,{"properties":{"記事状態":{"select":{"name":REVIEW_STATUS}}}})
    try:
        chunks=[rev["article"][i:i+1900] for i in range(0,len(rev["article"]),1900)]
        notion("PATCH","blocks/"+old_block["id"],{"code":{
           "language":"markdown",
           "rich_text":[{"type":"text","text":{"content":c}} for c in chunks],
           "caption":[{"type":"text","text":{"content":new_caption}}]}})
        updated=[b for b in children(target) if b.get("type")=="code"
                 and (b.get("code") or {}).get("language")=="markdown"]
        require(len(updated)==1 and
                publication_contract.is_exact_current_ready_block(
                  rich_text((updated[0].get("code") or {}).get("rich_text")),
                  rich_text((updated[0].get("code") or {}).get("caption")),rev["article"]),
                "Updated publication contract bytes could not be verified")
        notion("PATCH","pages/"+target,page_properties(rev["title"],cover_url))
        require(sync._source_current_ready_manuscript(target)==rev["article"],
                "Updated Ready manuscript readback not exact")
        synced=sync.sync_note_ready_db(target_sync_id=target)
        require(int(synced.get("source_ready") or 0)==1,
                "Existing queue did not reconcile exactly one Ready article")
        require(existing.destination_preflight(target)["note_draft_id"]==rev["draft_id"],
                "Queue lost existing draft identity")
        note=existing.apply_current_article_to_existing_draft(target,expected_route=route)
        require(note.get("status")=="existing_ready_draft_regenerated"
                and note.get("same_edit_route") is True
                and note.get("title_verified") is True
                and note.get("body_verified") is True
                and note.get("eyecatch_verified") is True
                and note.get("new_draft_created") is False
                and note.get("public_release") is False,
                "Private note draft replacement did not pass all proofs")
        require(existing.destination_preflight(target)["note_draft_id"]==rev["draft_id"],
                "Post-save draft identity drift")
        return {"status":"EXACT_PRIVATE_SWAP_SUCCESS","draft_id_preserved":True,
                "ready_article_updated":True,"title_body_cover_verified":True,
                "gemini_calls":0,"new_draft_created":False,"public_release":False}
    except Exception:
        # A failed operation may have modified Notion/note partly. Freeze Ready
        # to prevent other auto-delivery. No blind retry or unsafe auto rollback.
        try:
            notion("PATCH","pages/"+target,
                   {"properties":{"記事状態":{"select":{"name":REVIEW_STATUS}}}})
        except Exception:
            pass
        raise


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--sync-id",required=True)
    p.add_argument("--apply",action="store_true")
    p.add_argument("--confirm",default="")
    args=p.parse_args()
    rev=preflight(args.sync_id)
    if not args.apply:
        print(json.dumps({"status":"PRIVATE_SWAP_PREFLIGHT_PASS","draft_bound":True,
             "new_title_sha256":hashlib.sha256(rev["title"].encode()).hexdigest(),
             "article_sha256":ARTICLE_SHA256,"gemini_calls":0,"notion_write":False,
             "note_write":False},sort_keys=True))
        return
    require(args.confirm=="SWAP_EXISTING_PRIVATE_DRAFT_ONCE","One-off confirmation missing")
    print(json.dumps(apply(rev),sort_keys=True))


if __name__=="__main__":
    main()
