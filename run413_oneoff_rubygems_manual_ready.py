#!/usr/bin/env python3
"""Run413 one-off operator-approved RubyGems Ready recaption.

No model calls. Reuses exact persisted manuscript bytes on the single approved
Content Intelligence page, appends a current-policy Ready block, and refuses
all other targets.
"""
from __future__ import annotations
import os, re, requests
import publication_contract
PAGE_ID="3d9479ff-dca9-819a-814c-e4a0aeb3263f"
EXPECTED_TITLE="OpenAI agents carried out an undisclosed attack on RubyGems"
CONFIRM="RUN413_ONEOFF_RUBYGEMS_MANUAL_READY"
API_VERSION="2026-03-11"
def require_reader_summary(manuscript):
    """A caption cannot turn an incomplete review surface into a reader-ready article."""
    intro = manuscript.split("### 元情報", 1)[0]
    pattern = (
        r"^## どんな内容？[ \t]*\n(?P<what>.*?)"
        r"^\*\*なぜ重要？\*\*[ \t]*\n(?P<why>.*?)"
        r"^\*\*結論は？\*\*[ \t]*\n(?P<decision>.*)\Z"
    )
    match = re.search(pattern, intro, re.M | re.S)
    if not match or any(not value.strip() for value in match.groupdict().values()):
        raise RuntimeError("Run413 reader summary missing or incomplete; repair presentation before Ready")
    for label in ("## どんな内容？", "**なぜ重要？**", "**結論は？**"):
        if intro.count(label) != 1:
            raise RuntimeError("Run413 reader summary duplicated")
def headers():
    token=(os.getenv("NOTION_API_KEY") or os.getenv("NOTION_DECISION_INTELLIGENCE_API_KEY") or "").strip()
    if not token: raise RuntimeError("Notion token required")
    return {"Authorization":f"Bearer {token}","Content-Type":"application/json","Notion-Version":API_VERSION}
def plain(items):
    return "".join(str(x.get("plain_text") or ((x.get("text") or {}).get("content")) or "") for x in (items or []))
def rich(text):
    return [{"type":"text","text":{"content":text[i:i+1900]}} for i in range(0,len(text),1900)]
def children():
    out=[]; cursor=""
    while True:
        url=f"https://api.notion.com/v1/blocks/{PAGE_ID}/children?page_size=100"+(f"&start_cursor={cursor}" if cursor else "")
        r=requests.get(url,headers=headers(),timeout=25); r.raise_for_status(); data=r.json(); out.extend(data.get("results") or [])
        if not data.get("has_more"): return out
        cursor=str(data.get("next_cursor") or "")
        if not cursor: return out
def main():
    if os.getenv("RUN413_CONFIRM","").strip()!=CONFIRM: raise RuntimeError("Run413 explicit confirmation missing")
    r=requests.get(f"https://api.notion.com/v1/pages/{PAGE_ID}",headers=headers(),timeout=25); r.raise_for_status(); props=r.json().get("properties") or {}
    title=plain((props.get("記事名") or {}).get("title")); status=str((((props.get("記事状態") or {}).get("select") or {}).get("name")) or "")
    if title!=EXPECTED_TITLE or status!="Ready": raise RuntimeError(f"Run413 target mismatch title={title!r} status={status!r}")
    bodies=[]
    for block in children():
        if block.get("type")!="code": continue
        body=plain((block.get("code") or {}).get("rich_text"))
        if body and EXPECTED_TITLE in body: bodies.append(body)
    if not bodies: raise RuntimeError("Run413 exact persisted manuscript code block not found")
    manuscript=bodies[-1]
    require_reader_summary(manuscript)
    caption=publication_contract.current_ready_caption(manuscript)
    if not publication_contract.is_current_ready_block(manuscript,caption): raise RuntimeError("Run413 Ready caption self-check failed")
    payload={"children":[{"object":"block","type":"code","code":{"language":"markdown","rich_text":rich(manuscript),"caption":rich(caption)}}]}
    r=requests.patch(f"https://api.notion.com/v1/blocks/{PAGE_ID}/children",headers=headers(),json=payload,timeout=25); r.raise_for_status()
    print({"run":413,"page_id":PAGE_ID,"zero_model_calls":True,"manuscript_chars":len(manuscript),"policy_sha256":publication_contract.policy_sha256(),"ready_caption_verified":True})
if __name__=="__main__": main()
