#!/usr/bin/env python3
"""Read-only audit of the exact Ready inventory used by note Ready sync."""
import json
from pathlib import Path
import note_ready_sync as nrs
import pipeline
from article_revalidation import rehydrate_recovery_repo


def _repo_from_ready(page, state):
    p=page.get("properties") or {}
    source=state.get("source") or ""
    original=state.get("original_url") or ""
    primary=state.get("primary_url") or original
    return {
        "notion_page_id": page.get("id") or "",
        "revalidation_stale_ready": True,
        "repo": {
            "nameWithOwner": state.get("title") or "",
            "url": original or primary,
            "primaryUrl": primary,
            "source": source,
            "sourceDetails": {"external_url": primary or original, "regen_note": "Ready inventory audit"},
        },
    }


def run():
    pages=nrs._query_db(nrs.SOURCE_DATA_SOURCE_ID,nrs.SOURCE_DATABASE_ID,payload={"filter":{"property":nrs.SOURCE_ARTICLE_STATUS,"select":{"equals":nrs.SOURCE_READY}}})
    out={"mode":"stale_ready_retirement_audit","model_calls":0,"writes":0,"ready_status_rows":len(pages),"stale":0,"current":0,"recoverable":0,"unrecoverable":0,"invalid":0,"items":[]}
    for page in pages:
        state=nrs._source_state(page)
        if state is None:
            out["invalid"]+=1; continue
        if nrs._source_has_current_ready_manuscript(state["sync_id"]):
            out["current"]+=1; continue
        out["stale"]+=1
        item=_repo_from_ready(page,state)
        restored=rehydrate_recovery_repo(pipeline,item)
        status="recoverable" if restored else "unrecoverable"
        out[status]+=1
        out["items"].append({"page_id":page.get("id") or "","status":status,"source":state.get("source") or ""})
    p=Path("article_audit/stale_ready_retirement_audit.json");p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    pipeline.logger.info("[STALE READY RETIREMENT AUDIT] %s",{k:v for k,v in out.items() if k!="items"})
    return out

if __name__=="__main__": run()
