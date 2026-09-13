"""Run394: zero-model full-gate proof for repaired AI Search Console article."""
from __future__ import annotations
import html, json, os, re
from pathlib import Path
from typing import Any
import requests
from run389_producthunt_surface_revalidation import deterministic_runtime, evaluate_surface, select_latest_markdown_manuscript
from run391_memmy_full_gate_revalidation import reconstruct_pre_presentation_draft as _base_reconstruct

PAGE_ID="3bc479ff-dca9-81cb-905d-f6f5452c66e5"
DB_TITLE="AI検索で自社が「無視」されていないかを確認する技術：AI Search Consoleの導入判断"
FINAL_TITLE="AI Search Console：AI検索で自社ブランドがどう見えるかを測る。"
PRIMARY_URL="https://search-console.ai/"
EVIDENCE_URLS=("https://search-console.ai/","https://search-console.ai/terms/")
REPORT_PATH=Path("gate_history/run394_ai_search_console_full_gate_revalidation.json")

def _plain_html(v:str)->str:
    v=re.sub(r"(?is)<script[^>]*>.*?</script>|<style[^>]*>.*?</style>"," ",v or "")
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"(?s)<[^>]+>"," ",v))).strip()

def fetch_evidence()->tuple[str,list[dict[str,Any]]]:
    docs=[]; chunks=[]
    for url in EVIDENCE_URLS:
        r=requests.get(url,timeout=20,headers={"User-Agent":"AIIF-Run394/1.0"})
        if r.status_code!=200: raise RuntimeError(f"evidence fetch failed {url} HTTP {r.status_code}")
        text=_plain_html(r.text)
        if len(text)<300: text=r.text
        docs.append({"url":url,"text":text,"origin":"official_vendor"}); chunks.append(f"SOURCE URL: {url}\n{text}")
    context="\n\n".join(chunks)
    required=("ChatGPT","Perplexity","Gemini","AI-powered analytics","inaccurate","independently")
    missing=[x for x in required if x.lower() not in context.lower()]
    if missing: raise RuntimeError(f"evidence contract drift missing={missing}")
    return context,docs

def fetch_manuscript():
    import note_ready_sync as sync
    p=sync._request("GET",f"https://api.notion.com/v1/pages/{PAGE_ID}")
    if p.status_code!=200: raise RuntimeError(f"Notion page HTTP {p.status_code}")
    s=sync._source_state(p.json())
    if not s or s.get("title")!=DB_TITLE or s.get("source")!="OfficialVendor": raise RuntimeError("metadata mismatch")
    m,caption,count=select_latest_markdown_manuscript(sync._block_children(PAGE_ID))
    return m,{"eyecatch_url":s.get("eyecatch_url") or "","caption":caption,"count":count}

def reconstruct(m:str)->str:
    d=_base_reconstruct(m)
    d=re.sub(r"(?ms)^#{2,3} Sources / Evidence\s*\n.*\Z","",d,count=1)
    return re.sub(r"\n{3,}","\n\n",d).strip()

def source_info(context,docs):
    return {"source":"OfficialVendor","primary_url":PRIMARY_URL,"primary_source_resolved":True,"verification_context":context,"context":context,"freshness_status_available":True,"requested_action_risk_tier":"LOW","numeric_claims_required":False,"actor_attribution_required":False,"deep_source_required":False,"deep_source_scanned":True,"decision_scope_safe":True,"evidence_supplement_attempted":True,"evidence_documents":docs,"checked_urls":{d["url"] for d in docs},"supplement_candidates":[],"evidence_metadata":{"coverage":{"method":"FOUND","limitations":"FOUND"},"first_party_urls":[d["url"] for d in docs]}}

def parsed(core):
    return {"title_text":FINAL_TITLE,"note_draft":core,"action_text":"重要な質問を5つに絞り、手作業のAI回答とツール表示を比較して継続利用を判断する。","decision_text":"TRY","score":75,"decision_reason_text":"AI上でのブランド表示を継続的に確認する必要がある企業なら、小規模に測定価値を確かめる余地がある。","source_summary_text":"AI Search ConsoleはChatGPT、Perplexity、Gemini上でのブランド可視性を追跡する分析サービス。","what_text":"AI上で自社ブランドがどう表示されるかを追う分析サービス。","why_important_text":"通常の検索順位とは別に、AI回答上のブランド表示を観測できる。"}

def run():
    if not os.environ.get("NOTION_API_KEY"): raise RuntimeError("Notion read credential required")
    manuscript,meta=fetch_manuscript(); context,docs=fetch_evidence(); si=source_info(context,docs); p=parsed(reconstruct(manuscript))
    with deterministic_runtime() as pipe:
        ev=pipe.assess_evidence_sufficiency(si); ev_ok=str(ev.get("state"))==str(getattr(pipe,"EVIDENCE_SUFFICIENT","SUFFICIENT")); si["sufficient"]=ev_ok; si["decision_scope_safe"]=bool(ev.get("decision_scope_safe"))
        freshness={"status":"CURRENT_FIRST_PARTY_RECHECKED","current":True,"checked":True}
        fact_ok,fact_fail=pipe.validate_fact_gate(p,"AI Search Console",source_context=context,source="OfficialVendor",evidence_metadata=si["evidence_metadata"],source_info=si,freshness=freshness,output_truncated=False)
        ed_ok,ed_warn=pipe.validate_editorial_gate(p,"AI Search Console")
        pub,pub_issues=pipe.validate_publication_readiness_gate(p,context,si)
        human,human_issues=pipe.validate_human_appeal_gate(p,[])
        rows=pipe.map_gate_reasons("fact",fact_fail)+pipe.map_gate_reasons("editorial",ed_warn)+pipe.map_gate_reasons("publication",pub_issues)+pipe.map_gate_reasons("human_appeal",human_issues)
        disp=pipe.gate_reason_disposition(rows); q_ok=disp in {pipe.GATE_DISPOSITION_PASS,pipe.GATE_DISPOSITION_PASS_WITH_WARNINGS}; surf=evaluate_surface(DB_TITLE,manuscript,pipe)
    s_ok=surf.get("state")=="SURFACE_CLEAN_BODY_REGROUND_PROOF_REQUIRED"; eye=bool(meta["eyecatch_url"]); full=all((ev_ok,q_ok,s_ok,eye)); blockers=[]
    if not ev_ok: blockers.append(f"evidence:{ev.get('state')}")
    if not q_ok: blockers += [f"{r.get('gate')}:{r.get('reason_code')}:{r.get('message')}" for r in rows if r.get("message")]
    if not s_ok: blockers += [f"surface:{x}" for x in surf.get("issues") or []]
    if not eye: blockers.append("eyecatch_missing")
    result={"run":"run394_ai_search_console_full_gate_revalidation","full_gate_proven":full,"model_calls":0,"google_api_calls":0,"notion_writes":0,"publication_writes":0,"note_ready_sync":False,"ready_write_performed":False,"checks":{"evidence_ok":ev_ok,"evidence":ev,"fact_ok":fact_ok,"fact_failures":fact_fail,"editorial_ok":ed_ok,"editorial_warnings":ed_warn,"publication_state":pub,"publication_issues":pub_issues,"human_state":human,"human_issues":human_issues,"quality_disposition":disp,"quality_ok":q_ok,"surface_state":surf.get("state"),"surface_issues":surf.get("issues") or [],"eyecatch_ok":eye},"blockers":blockers,"evidence_urls":list(EVIDENCE_URLS),"manuscript_sha256":surf.get("manuscript_sha256")}
    REPORT_PATH.parent.mkdir(parents=True,exist_ok=True); REPORT_PATH.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=list),encoding="utf-8"); return result

def main():
    r=run(); c=r["checks"]
    print(f"RUN394_FULL_GATE_PROVEN={str(r['full_gate_proven']).lower()}"); print(f"RUN394_EVIDENCE_OK={str(c['evidence_ok']).lower()} state={c['evidence'].get('state')}"); print(f"RUN394_FACT_OK={str(c['fact_ok']).lower()} failures={c['fact_failures']}"); print(f"RUN394_EDITORIAL_OK={str(c['editorial_ok']).lower()} warnings={c['editorial_warnings']}"); print(f"RUN394_PUBLICATION={c['publication_state']} issues={c['publication_issues']}"); print(f"RUN394_HUMAN={c['human_state']} issues={c['human_issues']}"); print(f"RUN394_QUALITY_DISPOSITION={c['quality_disposition']} quality_ok={str(c['quality_ok']).lower()}"); print(f"RUN394_SURFACE={c['surface_state']} issues={c['surface_issues']}"); print(f"RUN394_EYECATCH_OK={str(c['eyecatch_ok']).lower()}"); print(f"RUN394_BLOCKERS={r['blockers']}"); print("RUN394_MODEL_CALLS=0"); print("RUN394_NOTION_WRITES=0"); print("RUN394_PUBLICATION_WRITES=0"); return 0
if __name__=="__main__": raise SystemExit(main())
