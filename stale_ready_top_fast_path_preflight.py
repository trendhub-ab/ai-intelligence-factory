#!/usr/bin/env python3
"""Read-only zero-provider preflight for the single top stale Ready fast-path candidate."""
from __future__ import annotations
import json
from pathlib import Path
import note_ready_sync as nrs
import pipeline
from article_revalidation import rehydrate_recovery_repo
from stale_ready_retirement_audit import _repo_from_ready
from stale_ready_zero_api_portfolio_audit import classify_state, fast_path_priority


def run():
    pages=nrs._query_db(nrs.SOURCE_DATA_SOURCE_ID,nrs.SOURCE_DATABASE_ID,payload={"filter":{"property":nrs.SOURCE_ARTICLE_STATUS,"select":{"equals":nrs.SOURCE_READY}}})
    candidates=[]
    for page in pages:
        state=nrs._source_state(page)
        if state is None: continue
        current=nrs._source_has_current_ready_manuscript(state["sync_id"])
        item=_repo_from_ready(page,state)
        recovered=rehydrate_recovery_repo(pipeline,item)
        recoverable=bool(recovered)
        bucket,_=classify_state(state,recoverable=recoverable,current=current,published=False)
        if bucket!="keep_fast_path": continue
        priority,flag=fast_path_priority(state)
        candidates.append((priority,str(state.get("title") or ""),page,state,recovered,flag))
    candidates.sort(key=lambda x:(-x[0],x[1]))
    top=candidates[0] if candidates else None
    out={"mode":"stale_ready_top_fast_path_preflight","model_calls":0,"writes":0,"ready_rows":len(pages),"fast_path_candidates":len(candidates),"selected":None}
    if top:
        priority,_,page,state,recovered,flag=top
        primary=str(getattr(recovered,"primary_source_resolved","") or getattr(recovered,"primary_url","") or state.get("primary_url") or "")
        original=str(state.get("original_url") or "")
        out["selected"]={"page_id":page.get("id") or "","sync_id":state.get("sync_id") or "","title":state.get("title") or "","source":state.get("source") or "","decision_score":state.get("decision_score"),"article_value":state.get("article_value"),"fast_path_priority":priority,"priority_flag":flag,"publication_contract_current":nrs._source_has_current_ready_manuscript(state["sync_id"]),"provenance_recoverable":bool(recovered),"primary_source_resolved":bool(primary),"primary_url":primary,"original_url":original,"requires_model_validation":True,"requires_current_gates":True,"safe_to_restamp_without_validation":False,"remaining_reasons":["stale_publication_contract","current_evidence_fact_publication_reader_gates_not_reexecuted"]}
    dest=Path("article_audit/stale_ready_top_fast_path_preflight.json");dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    pipeline.logger.info("[STALE READY TOP FAST PATH PREFLIGHT] %s",out)
    return out

if __name__=="__main__": run()
