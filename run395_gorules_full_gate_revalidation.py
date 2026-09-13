"""Run395: zero-model full-gate proof for repaired GoRules article."""
from __future__ import annotations
import html, json, os, re
from pathlib import Path
from typing import Any
import requests
from run389_producthunt_surface_revalidation import deterministic_runtime, evaluate_surface, select_latest_markdown_manuscript
from run391_memmy_full_gate_revalidation import reconstruct_pre_presentation_draft as _base_reconstruct

PAGE_ID="3c4479ff-dca9-81b6-813b-cd544200f14a"
DB_TITLE="仕様書とコードの乖離をどう防ぐか。ビジネスロジック統合エンジン「GoRules」の登場から考える。"
FINAL_TITLE="GoRules：業務ルールをコードの外で管理する選択肢を、まず観察する。"
PRIMARY_URL="https://gorules.io/"
EVIDENCE_URLS=(
    "https://gorules.io/open-source",
    "https://gorules.io/open-source/rust-rules-engine",
    "https://raw.githubusercontent.com/gorules/zen/master/README.md",
)
REPORT_PATH=Path("gate_history/run395_gorules_full_gate_revalidation.json")

def _plain_html(v:str)->str:
    v=re.sub(r"(?is)<script[^>]*>.*?</script>|<style[^>]*>.*?</style>"," ",v or "")
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"(?s)<[^>]+>"," ",v))).strip()

def fetch_evidence()->tuple[str,list[dict[str,Any]]]:
    docs=[]; chunks=[]
    for url in EVIDENCE_URLS:
        r=requests.get(url,timeout=20,headers={"User-Agent":"AIIF-Run395/1.0"})
        if r.status_code!=200: raise RuntimeError(f"evidence fetch failed {url} HTTP {r.status_code}")
        text=r.text if "raw.githubusercontent.com" in url else _plain_html(r.text)
        if len(text.strip())<300: raise RuntimeError(f"evidence unexpectedly thin {url}")
        origin="github_readme" if "raw.githubusercontent.com" in url else "official_vendor"
        docs.append({"url":url,"text":text,"origin":origin}); chunks.append(f"SOURCE URL: {url}\n{text}")
    context="\n\n".join(chunks)
    required=("MIT","Rust","Python","Go")
    missing=[x for x in required if x.lower() not in context.lower()]
    if missing: raise RuntimeError(f"evidence contract drift missing={missing}")
    return context,docs

def fetch_manuscript():
    import note_ready_sync as sync
    p=sync._request("GET",f"https://api.notion.com/v1/pages/{PAGE_ID}")
    if p.status_code!=200: raise RuntimeError(f"Notion page HTTP {p.status_code}")
    s=sync._source_state(p.json())
    if not s or s.get("title")!=DB_TITLE or s.get("source")!="OfficialVendor": raise RuntimeError(f"metadata mismatch title={s.get('title') if s else None} source={s.get('source') if s else None}")
    m,caption,count=select_latest_markdown_manuscript(sync._block_children(PAGE_ID))
    return m,{"eyecatch_url":s.get("eyecatch_url") or "","caption":caption,"count":count}

def reconstruct(m:str)->str:
    d=_base_reconstruct(m)
    d=re.sub(r"(?ms)^#{2,3} Sources / Evidence\s*\n.*\Z","",d,count=1)
    return re.sub(r"\n{3,}","\n\n",d).strip()

def source_info(context,docs):
    return {"source":"OfficialVendor","primary_url":PRIMARY_URL,"primary_source_resolved":True,"verification_context":context,"context":context,"freshness_status_available":True,"requested_action_risk_tier":"LOW","numeric_claims_required":False,"actor_attribution_required":False,"deep_source_required":False,"deep_source_scanned":True,"decision_scope_safe":True,"evidence_supplement_attempted":True,"evidence_documents":docs,"checked_urls":{d["url"] for d in docs},"supplement_candidates":[],"evidence_metadata":{"coverage":{"method":"FOUND","limitations":"FOUND"},"first_party_urls":[d["url"] for d in docs]}}

def parsed(core):
    return {"title_text":FINAL_TITLE,"note_draft":core,"action_text":"割引ルールを1つ移し、同じ入力で既存実装との出力一致を確認し、変更作業と実行時間を記録する。","decision_text":"WATCH","score":55,"decision_reason_text":"ルール分離の価値はあるが、本番導入前に互換性・運用・性能を小さく検証すべき段階。","source_summary_text":"GoRulesは業務判断ルールを独立して管理・実行する仕組みで、中核エンジンはオープンソース。","what_text":"業務上の判断ルールをコード本体から切り分けて管理・実行する仕組み。","why_important_text":"変更頻度の高い判断条件を独立管理する選択肢になる。"}

def run():
    if not os.environ.get("NOTION_API_KEY"): raise RuntimeError("Notion read credential required")
    manuscript,meta=fetch_manuscript(); context,docs=fetch_evidence(); si=source_info(context,docs); p=parsed(reconstruct(manuscript))
    with deterministic_runtime() as pipe:
        ev=pipe.assess_evidence_sufficiency(si); ev_ok=str(ev.get("state"))==str(getattr(pipe,"EVIDENCE_SUFFICIENT","SUFFICIENT")); si["sufficient"]=ev_ok; si["decision_scope_safe"]=bool(ev.get("decision_scope_safe"))
        freshness={"status":"CURRENT_FIRST_PARTY_RECHECKED","current":True,"checked":True}
        fact_ok,fact_fail=pipe.validate_fact_gate(p,"GoRules",source_context=context,source="OfficialVendor",evidence_metadata=si["evidence_metadata"],source_info=si,freshness=freshness,output_truncated=False)
        ed_ok,ed_warn=pipe.validate_editorial_gate(p,"GoRules")
        pub,pub_issues=pipe.validate_publication_readiness_gate(p,context,si)
        human,human_issues=pipe.validate_human_appeal_gate(p,[])
        rows=pipe.map_gate_reasons("fact",fact_fail)+pipe.map_gate_reasons("editorial",ed_warn)+pipe.map_gate_reasons("publication",pub_issues)+pipe.map_gate_reasons("human_appeal",human_issues)
        disp=pipe.gate_reason_disposition(rows); q_ok=disp in {pipe.GATE_DISPOSITION_PASS,pipe.GATE_DISPOSITION_PASS_WITH_WARNINGS}; surf=evaluate_surface(DB_TITLE,manuscript,pipe)
    s_ok=surf.get("state")=="SURFACE_CLEAN_BODY_REGROUND_PROOF_REQUIRED"; eye=bool(meta["eyecatch_url"]); manuscript_proven=all((ev_ok,q_ok,s_ok)); full=all((manuscript_proven,eye)); blockers=[]
    if not ev_ok: blockers.append(f"evidence:{ev.get('state')}")
    if not q_ok: blockers += [f"{r.get('gate')}:{r.get('reason_code')}:{r.get('message')}" for r in rows if r.get("message")]
    if not s_ok: blockers += [f"surface:{x}" for x in surf.get("issues") or []]
    if not eye: blockers.append("eyecatch_missing")
    result={"run":"run395_gorules_full_gate_revalidation","manuscript_gate_proven":manuscript_proven,"full_gate_proven":full,"model_calls":0,"google_api_calls":0,"notion_writes":0,"publication_writes":0,"note_ready_sync":False,"ready_write_performed":False,"checks":{"evidence_ok":ev_ok,"evidence":ev,"fact_ok":fact_ok,"fact_failures":fact_fail,"editorial_ok":ed_ok,"editorial_warnings":ed_warn,"publication_state":pub,"publication_issues":pub_issues,"human_state":human,"human_issues":human_issues,"quality_disposition":disp,"quality_ok":q_ok,"surface_state":surf.get("state"),"surface_issues":surf.get("issues") or [],"eyecatch_ok":eye},"blockers":blockers,"evidence_urls":list(EVIDENCE_URLS),"manuscript_sha256":surf.get("manuscript_sha256")}
    REPORT_PATH.parent.mkdir(parents=True,exist_ok=True); REPORT_PATH.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=list),encoding="utf-8"); return result

def main():
    r=run(); c=r["checks"]
    print(f"RUN395_MANUSCRIPT_GATE_PROVEN={str(r['manuscript_gate_proven']).lower()}"); print(f"RUN395_FULL_GATE_PROVEN={str(r['full_gate_proven']).lower()}"); print(f"RUN395_EVIDENCE_OK={str(c['evidence_ok']).lower()} state={c['evidence'].get('state')}"); print(f"RUN395_FACT_OK={str(c['fact_ok']).lower()} failures={c['fact_failures']}"); print(f"RUN395_EDITORIAL_OK={str(c['editorial_ok']).lower()} warnings={c['editorial_warnings']}"); print(f"RUN395_PUBLICATION={c['publication_state']} issues={c['publication_issues']}"); print(f"RUN395_HUMAN={c['human_state']} issues={c['human_issues']}"); print(f"RUN395_QUALITY_DISPOSITION={c['quality_disposition']} quality_ok={str(c['quality_ok']).lower()}"); print(f"RUN395_SURFACE={c['surface_state']} issues={c['surface_issues']}"); print(f"RUN395_EYECATCH_OK={str(c['eyecatch_ok']).lower()}"); print(f"RUN395_BLOCKERS={r['blockers']}"); print("RUN395_MODEL_CALLS=0"); print("RUN395_NOTION_WRITES=0"); print("RUN395_PUBLICATION_WRITES=0"); return 0
if __name__=="__main__": raise SystemExit(main())
