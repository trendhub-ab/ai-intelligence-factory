#!/usr/bin/env python3
"""Zero-provider portfolio audit for stale Ready inventory.

Read-only by contract: no provider initialization, no Notion writes, no Ready restamp.
Classification uses only authoritative persisted metadata plus provenance recovery.
"""
from __future__ import annotations
import json
from pathlib import Path
import note_ready_sync as nrs
import pipeline
from article_revalidation import rehydrate_recovery_repo
from stale_ready_retirement_audit import _repo_from_ready


def _num(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def classify_state(state: dict, *, recoverable: bool, current: bool=False, published: bool=False) -> tuple[str, list[str]]:
    reasons=[]
    if published:
        return "protected_published", ["already_published"]
    if current:
        return "protected_current", ["current_contract"]
    if not recoverable:
        return "retire_candidate", ["provenance_unrecoverable"]
    decision=_num(state.get("decision_score"))
    value=_num(state.get("article_value"))
    if decision is None or value is None:
        return "manual_unknown", ["insufficient_value_metadata"]
    if decision >= 75 and value >= 75:
        return "keep_fast_path", [f"decision_score={decision:g}", f"article_value={value:g}"]
    if decision >= 60 and value >= 60:
        return "reader_reedit_candidate", [f"decision_score={decision:g}", f"article_value={value:g}"]
    if decision >= 45 or value >= 45:
        return "deep_revalidation_candidate", [f"decision_score={decision:g}", f"article_value={value:g}"]
    return "retire_candidate", [f"decision_score={decision:g}", f"article_value={value:g}"]


def run():
    pages=nrs._query_db(nrs.SOURCE_DATA_SOURCE_ID,nrs.SOURCE_DATABASE_ID,payload={"filter":{"property":nrs.SOURCE_ARTICLE_STATUS,"select":{"equals":nrs.SOURCE_READY}}})
    out={"mode":"stale_ready_zero_api_portfolio_audit","model_calls":0,"writes":0,"ready_rows":len(pages),
         "buckets":{"protected_published":0,"protected_current":0,"keep_fast_path":0,"reader_reedit_candidate":0,"deep_revalidation_candidate":0,"retire_candidate":0,"manual_unknown":0},"items":[]}
    for page in pages:
        state=nrs._source_state(page)
        if state is None:
            bucket,reasons="manual_unknown",["invalid_ready_state"]
            recoverable=False
        else:
            current=nrs._source_has_current_ready_manuscript(state["sync_id"])
            item=_repo_from_ready(page,state)
            recoverable=bool(rehydrate_recovery_repo(pipeline,item))
            bucket,reasons=classify_state(state,recoverable=recoverable,current=current,published=False)
        out["buckets"][bucket]+=1
        out["items"].append({"page_id":page.get("id") or "","title":(state or {}).get("title") or "","source":(state or {}).get("source") or "",
            "decision_score":(state or {}).get("decision_score"),"article_value":(state or {}).get("article_value"),"recoverable":recoverable,"bucket":bucket,"reasons":reasons})
    out["items"].sort(key=lambda x:(x["bucket"],-(x["decision_score"] or -1),-(x["article_value"] or -1),x["title"]))
    dest=Path("article_audit/stale_ready_zero_api_portfolio_audit.json");dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    pipeline.logger.info("[STALE READY ZERO API PORTFOLIO AUDIT] %s",{k:v for k,v in out.items() if k!="items"})
    return out


if __name__=="__main__": run()
