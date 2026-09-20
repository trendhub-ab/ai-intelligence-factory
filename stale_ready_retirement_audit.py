#!/usr/bin/env python3
"""Dry-run audit of stale Ready inventory. No writes, no model calls."""
import json
from pathlib import Path
import pipeline
from article_revalidation import select_revalidation_items, rehydrate_recovery_repo


def run():
    pipeline.initialize_runtime()
    rows=select_revalidation_items(pipeline,limit=100,scan_limit=100,include_quality_failed=False,include_stale_ready=True,prefer_stale_ready=True)
    out={"mode":"stale_ready_retirement_audit","model_calls":0,"writes":0,"scanned":len(rows or []),"recoverable":0,"unrecoverable":0,"items":[]}
    for item in rows or []:
        if not item.get("revalidation_stale_ready"): continue
        restored=rehydrate_recovery_repo(pipeline,item)
        status="recoverable" if restored else "unrecoverable"
        out[status]+=1
        out["items"].append({"page_id":item.get("notion_page_id",""),"status":status,"source":(item.get("repo") or {}).get("source","")})
    p=Path("article_audit/stale_ready_retirement_audit.json");p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    pipeline.logger.info("[STALE READY RETIREMENT AUDIT] %s",{k:v for k,v in out.items() if k!="items"})
    return out

if __name__=="__main__": run()
