"""Bounded revalidation of stale Ready inventory under current production gates."""
from __future__ import annotations
import json, os
from pathlib import Path
import note_ready_sync as nrs

DEFAULT_BATCH_SIZE=2
MAX_BATCH_SIZE=3


def _is_posted(sync_id: str) -> bool:
    if not (nrs.DEST_DATA_SOURCE_ID or nrs.DEST_DATABASE_ID):
        return False
    rows=nrs._query_db(nrs.DEST_DATA_SOURCE_ID,nrs.DEST_DATABASE_ID)
    sid=str(sync_id or "")
    for page in rows:
        state=nrs._destination_state(page)
        if state.get("sync_id")==sid and state.get("posting_status")=="投稿済み":
            return True
    return False


def _repo(page: dict, state: dict) -> dict:
    p=page.get("properties") or {}
    primary=state.get("primary_url") or state.get("original_url") or ""
    return {
      "nameWithOwner":state.get("title") or "",
      "url":state.get("original_url") or primary,
      "primaryUrl":primary,
      "source":state.get("source") or "",
      "sourceDetails":{"external_url":primary,"revalidation":"stale_ready_batch"},
      "stargazerCount":0,
    }


def _fetch_page(page_id: str) -> dict | None:
    res=nrs._request("GET",f"https://api.notion.com/v1/pages/{page_id}")
    return res.json() if res.status_code==200 else None


def run(pipeline):
    pipeline.initialize_runtime()
    batch=max(1,min(MAX_BATCH_SIZE,int(os.environ.get("STALE_READY_REVALIDATION_BATCH_SIZE",DEFAULT_BATCH_SIZE))))
    pages=nrs._query_db(nrs.SOURCE_DATA_SOURCE_ID,nrs.SOURCE_DATABASE_ID,payload={"filter":{"property":nrs.SOURCE_ARTICLE_STATUS,"select":{"equals":nrs.SOURCE_READY}}})
    result={"mode":"stale_ready_batch_revalidation","batch_limit":batch,"ready_rows":len(pages),"attempted":0,"passed":0,"failed_or_review":0,"skipped_current":0,"skipped_published":0,"skipped_invalid":0,"provider_cap":int(getattr(pipeline.DEEP_DIVE_MODEL_BUDGET,"budget",0) or 0),"items":[]}
    rank=0
    for candidate in pages:
        if result["attempted"]>=batch: break
        page_id=str(candidate.get("id") or "")
        # TOCTOU protection: re-fetch immediately before any provider work.
        page=_fetch_page(page_id)
        if not page:
            result["skipped_invalid"]+=1; continue
        state=nrs._source_state(page)
        if state is None:
            result["skipped_invalid"]+=1; continue
        if nrs._source_has_current_ready_manuscript(state["sync_id"]):
            result["skipped_current"]+=1; continue
        if _is_posted(state["sync_id"]):
            result["skipped_published"]+=1; continue
        repo=_repo(page,state)
        safe,_=pipeline.legal_safety_gate(repo)
        if not safe:
            result["skipped_invalid"]+=1; continue
        rank+=1; result["attempted"]+=1
        report=pipeline.generate_intelligence_report(repo,notion_page_id=page_id,candidate_rank=rank,candidate_origin="stale_ready_batch_revalidation",persist_results=True)
        passed=bool(report)
        result["passed" if passed else "failed_or_review"]+=1
        result["items"].append({"page_id":page_id,"result":"ready" if passed else "not_ready"})
    result["provider_used"]=int(getattr(pipeline.DEEP_DIVE_MODEL_BUDGET,"used",0) or 0)
    dest=Path("article_audit/stale_ready_batch_revalidation.json");dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    pipeline.logger.info("[STALE READY BATCH REVALIDATION] %s",{k:v for k,v in result.items() if k!="items"})
    return result
