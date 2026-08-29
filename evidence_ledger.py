"""Append-only Evidence Ledger and zero-Gemini source-health maintenance.

Run117 isolates durable evidence provenance from current Technology state.  The ledger
is optional until its Notion database is configured; once enabled it stores compact
judgment evidence, hashes, immutable source versions, and source-health observations.
"""
from __future__ import annotations

import hashlib
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests

from evidence_authority import classify_evidence

ENABLE_EVIDENCE_LEDGER = os.environ.get("ENABLE_EVIDENCE_LEDGER", "false").lower() in {"1","true","yes","on"}
EVIDENCE_LEDGER_REQUIRED = os.environ.get("EVIDENCE_LEDGER_REQUIRED", "false").lower() in {"1","true","yes","on"}
NOTION_EVIDENCE_DATABASE_ID = os.environ.get("NOTION_EVIDENCE_DATABASE_ID", "").strip()
NOTION_EVIDENCE_DATA_SOURCE_ID = os.environ.get("NOTION_EVIDENCE_DATA_SOURCE_ID", "").strip()
NOTION_API_VERSION = os.environ.get("NOTION_API_VERSION", "2026-03-11")
EVIDENCE_HEALTH_MAX_CHECKS_PER_RUN = max(0, int(os.environ.get("EVIDENCE_HEALTH_MAX_CHECKS_PER_RUN", "20")))
EVIDENCE_EXTRACT_MAX_CHARS = max(300, min(1800, int(os.environ.get("EVIDENCE_EXTRACT_MAX_CHARS", "1400"))))

HEALTH_VALUES = {"VERIFIED","COSMETIC_CHANGE","MOVED","MATERIAL_CHANGE","MISSING","FETCH_ERROR"}

P_TITLE='根拠レコード'; P_ENTITY='技術エンティティID'; P_TECH_PAGE='技術ページID'
P_URL='根拠URL'; P_IMMUTABLE='不変根拠URL'; P_RESOLVED='解決済みURL'; P_VERSION='ソース版'; P_SOURCE='ソース種別'; P_ROLE='根拠役割'
P_RETRIEVED='取得日'; P_VERIFIED='最終検証日'; P_HEALTH='ソース状態'; P_DOC_HASH='文書ハッシュ'
P_EXTRACT_HASH='抽出ハッシュ'; P_EXTRACT='根拠抜粋'; P_ID='根拠ID'; P_ACTIVE='有効スナップショット'; P_TRIGGER='再レビュー対象'
P_AUTHORITY='権威性クラス'; P_ELIGIBLE='判断根拠利用可'; P_AUTH_REASON='権威性理由'
P_BINDING='エンティティ紐付け'; P_BIND_REASON='紐付け理由'

REQUIRED_PROPERTY_TYPES={P_TITLE:"title",P_ENTITY:"rich_text",P_TECH_PAGE:"rich_text",P_URL:"url",P_IMMUTABLE:"url",P_RESOLVED:"url",P_VERSION:"rich_text",
P_SOURCE:"rich_text",P_ROLE:"rich_text",P_RETRIEVED:"date",P_VERIFIED:"date",P_HEALTH:"select",P_DOC_HASH:"rich_text",P_EXTRACT_HASH:"rich_text",
P_EXTRACT:"rich_text",P_ID:"rich_text",P_ACTIVE:"checkbox",P_TRIGGER:"checkbox",P_AUTHORITY:"rich_text",P_ELIGIBLE:"checkbox",P_AUTH_REASON:"rich_text",P_BINDING:"rich_text",P_BIND_REASON:"rich_text"}


def _headers(token:str)->dict:
    return {"Authorization":f"Bearer {token}","Notion-Version":NOTION_API_VERSION,"Content-Type":"application/json"}

def _schema_url()->str:
    if NOTION_EVIDENCE_DATA_SOURCE_ID:
        return f"https://api.notion.com/v1/data_sources/{NOTION_EVIDENCE_DATA_SOURCE_ID}"
    return f"https://api.notion.com/v1/databases/{NOTION_EVIDENCE_DATABASE_ID}"

def _query_url()->str:
    if NOTION_EVIDENCE_DATA_SOURCE_ID:
        return f"https://api.notion.com/v1/data_sources/{NOTION_EVIDENCE_DATA_SOURCE_ID}/query"
    return f"https://api.notion.com/v1/databases/{NOTION_EVIDENCE_DATABASE_ID}/query"

def _parent()->dict:
    return {"type":"data_source_id","data_source_id":NOTION_EVIDENCE_DATA_SOURCE_ID} if NOTION_EVIDENCE_DATA_SOURCE_ID else {"database_id":NOTION_EVIDENCE_DATABASE_ID}

def _rt(v:Any)->dict:
    s=str(v or "")[:2000]; return {"rich_text":[{"text":{"content":s}}]} if s else {"rich_text":[]}

def _title(v:Any)->dict:
    return {"title":[{"text":{"content":str(v or "")[:2000]}}]}

def _date(v:str|None)->dict: return {"date":{"start":v}} if v else {"date":None}

def _select(v:str|None)->dict: return {"select":{"name":v}} if v else {"select":None}

def _rich(prop:dict)->str:
    return "".join(x.get("plain_text") or ((x.get("text") or {}).get("content")) or "" for x in (prop.get("rich_text") or prop.get("title") or [])).strip()

def normalize_text(text:str)->str:
    s=unicodedata.normalize("NFKC", text or "")
    s=re.sub(r"\s+"," ",s).strip().lower()
    return s

def content_hash(text:str)->str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest() if text else ""

def compact_extract(text:str)->str:
    return re.sub(r"\s+"," ",unicodedata.normalize("NFKC",text or "")).strip()[:EVIDENCE_EXTRACT_MAX_CHARS]

def canonical_url(url:str)->str:
    try:
        p=urlparse(url or "")
        if p.scheme not in {"http","https"} or not p.netloc: return ""
        return urlunparse((p.scheme.lower(),p.netloc.lower(),p.path.rstrip("/") or "/","",p.query,""))
    except Exception: return ""

def same_first_party(a:str,b:str)->bool:
    ah=(urlparse(a or "").hostname or "").lower().removeprefix("www."); bh=(urlparse(b or "").hostname or "").lower().removeprefix("www.")
    return bool(ah and bh and (ah==bh or ah.endswith("."+bh) or bh.endswith("."+ah)))

def evidence_identity(entity_id:str,url:str,version:str,retrieved_at:str)->str:
    raw="|".join([entity_id,canonical_url(url),version or "",(retrieved_at or "")[:19]])
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def preflight(token:str)->None:
    if not ENABLE_EVIDENCE_LEDGER: return
    if not token or not (NOTION_EVIDENCE_DATA_SOURCE_ID or NOTION_EVIDENCE_DATABASE_ID):
        raise ValueError("Evidence Ledger enabled but token/database ID is missing")
    r=requests.get(_schema_url(),headers=_headers(token),timeout=15); r.raise_for_status(); props=r.json().get("properties",{})
    missing=[k for k in REQUIRED_PROPERTY_TYPES if k not in props]
    mismatch=[f"{k}:{(props.get(k) or {}).get('type')}!={t}" for k,t in REQUIRED_PROPERTY_TYPES.items() if k in props and (props.get(k) or {}).get('type') not in {None,t}]
    if missing or mismatch: raise ValueError("Evidence Ledger schema incompatible: "+"; ".join(["missing="+",".join(missing) if missing else "","mismatch="+",".join(mismatch) if mismatch else ""]).strip("; "))



def ensure_authority_schema(token:str)->dict:
    """Idempotently add Run118/Run119 authority and entity-binding columns."""
    if not token or not NOTION_EVIDENCE_DATA_SOURCE_ID:
        raise ValueError("Run118 schema migration requires NOTION_EVIDENCE_DATA_SOURCE_ID and token")
    r=requests.get(_schema_url(),headers=_headers(token),timeout=15); r.raise_for_status(); props=r.json().get("properties",{})
    additions={}
    if P_AUTHORITY not in props: additions[P_AUTHORITY]={"rich_text":{}}
    if P_ELIGIBLE not in props: additions[P_ELIGIBLE]={"checkbox":{}}
    if P_AUTH_REASON not in props: additions[P_AUTH_REASON]={"rich_text":{}}
    if not additions: return {"changed":False,"added":[]}
    u=requests.patch(_schema_url(),headers=_headers(token),json={"properties":additions},timeout=20); u.raise_for_status()
    return {"changed":True,"added":list(additions)}


def ensure_entity_binding_schema(token:str)->dict:
    """Idempotently add Run119 entity-binding audit columns."""
    if not token or not NOTION_EVIDENCE_DATA_SOURCE_ID:
        raise ValueError("Run119 schema migration requires NOTION_EVIDENCE_DATA_SOURCE_ID and token")
    r=requests.get(_schema_url(),headers=_headers(token),timeout=15); r.raise_for_status(); props=r.json().get("properties",{})
    additions={}
    if P_BINDING not in props: additions[P_BINDING]={"rich_text":{}}
    if P_BIND_REASON not in props: additions[P_BIND_REASON]={"rich_text":{}}
    if not additions: return {"changed":False,"added":[]}
    u=requests.patch(_schema_url(),headers=_headers(token),json={"properties":additions},timeout=20); u.raise_for_status()
    return {"changed":True,"added":list(additions)}

def build_snapshots(entity_id:str, tech_page_id:str, source_info:dict, retrieved_at:str, source_version:str="", immutable_url:str="")->list[dict]:
    docs=[]; seen=set(); verification=source_info.get("verification_context") or source_info.get("context") or ""
    for doc in source_info.get("evidence_documents",[]) or []:
        if not doc.get("retrieved"): continue
        url=doc.get("url") or ""; key=canonical_url(url)
        if not key or key in seen: continue
        seen.add(key)
        extract=compact_extract(doc.get("evidence_extract") or (verification if key==canonical_url(source_info.get("primary_url") or "") else ""))
        if not extract: continue
        version=doc.get("source_version") or (source_version if key==canonical_url(source_info.get("primary_url") or "") else "")
        resolved=doc.get("resolved_url") or url
        immutable = immutable_url if immutable_url and key==canonical_url(source_info.get("primary_url") or "") else ""
        authority=classify_evidence(
            url=url, role=doc.get("role") or "PRIMARY_SOURCE", raw_source_type=doc.get("source_type") or "",
            label=doc.get("label") or "", origin=doc.get("origin") or "", pipeline_source=source_info.get("source") or "",
            primary_url=source_info.get("primary_url") or "", entity_id=entity_id,
            source_details=source_info.get("source_details") or {}, evidence_extract=extract,
        )
        docs.append({"entity_id":entity_id,"tech_page_id":tech_page_id,"url":url,"immutable_url":immutable,"resolved_url":resolved,"source_version":version,
                     "source_type":authority["source_type"],"role":doc.get("role") or "PRIMARY_SOURCE",
                     "authority_class":authority["authority_class"],"decision_eligible":bool(authority["decision_eligible"]),"authority_reason":authority["reason"],
                     "entity_binding":authority.get("entity_binding","UNKNOWN"),"entity_binding_reason":authority.get("entity_binding_reason",""),
                     "retrieved_at":retrieved_at,"last_verified_at":retrieved_at,"source_health":"VERIFIED",
                     "document_hash":content_hash(doc.get("document_text") or extract),"extract_hash":content_hash(extract),"extract":extract})
    return docs


def _props(s:dict)->dict:
    eid=evidence_identity(s['entity_id'],s['url'],s.get('source_version',''),s['retrieved_at'])
    return {P_TITLE:_title(f"{s['entity_id']} — {s.get('source_type','evidence')} — {s['retrieved_at'][:10]}"),P_ENTITY:_rt(s['entity_id']),P_TECH_PAGE:_rt(s.get('tech_page_id')),
            P_URL:{"url":s['url'] or None},P_IMMUTABLE:{"url":s.get('immutable_url') or None},P_RESOLVED:{"url":s.get('resolved_url') or None},P_VERSION:_rt(s.get('source_version')),P_SOURCE:_rt(s.get('source_type')),P_ROLE:_rt(s.get('role')),
            P_RETRIEVED:_date(s['retrieved_at']),P_VERIFIED:_date(s.get('last_verified_at')),P_HEALTH:_select(s.get('source_health') or 'VERIFIED'),P_DOC_HASH:_rt(s.get('document_hash')),
            P_EXTRACT_HASH:_rt(s.get('extract_hash')),P_EXTRACT:_rt(s.get('extract')),P_ID:_rt(eid),P_ACTIVE:{"checkbox":True},P_TRIGGER:{"checkbox":False},
            P_AUTHORITY:_rt(s.get('authority_class')),P_ELIGIBLE:{"checkbox":bool(s.get('decision_eligible'))},P_AUTH_REASON:_rt(s.get('authority_reason')),
            P_BINDING:_rt(s.get('entity_binding')),P_BIND_REASON:_rt(s.get('entity_binding_reason'))}


def persist_snapshots(snapshots:list[dict], token:str)->dict:
    if not ENABLE_EVIDENCE_LEDGER: return {"enabled":False,"saved":0}
    saved=0
    for s in snapshots:
        eid=evidence_identity(s['entity_id'],s['url'],s.get('source_version',''),s['retrieved_at'])
        q=requests.post(_query_url(),headers=_headers(token),json={"filter":{"property":P_ID,"rich_text":{"equals":eid}},"page_size":1},timeout=15); q.raise_for_status()
        if q.json().get('results'): continue
        r=requests.post("https://api.notion.com/v1/pages",headers=_headers(token),json={"parent":_parent(),"properties":_props(s)},timeout=20); r.raise_for_status(); new_page_id=(r.json() or {}).get("id"); saved+=1
        # Keep history append-only but health-check only the newest snapshot per entity+live URL.
        active_q={"filter":{"and":[{"property":P_ENTITY,"rich_text":{"equals":s['entity_id']}},{"property":P_URL,"url":{"equals":s['url']}},{"property":P_ACTIVE,"checkbox":{"equals":True}}]},"page_size":100}
        aq=requests.post(_query_url(),headers=_headers(token),json=active_q,timeout=15); aq.raise_for_status()
        for old_page in aq.json().get("results",[]):
            if old_page.get("id")==new_page_id: continue
            off=requests.patch(f"https://api.notion.com/v1/pages/{old_page['id']}",headers=_headers(token),json={"properties":{P_ACTIVE:{"checkbox":False}}},timeout=15); off.raise_for_status()
    return {"enabled":True,"saved":saved}


def page_to_state(page:dict)->dict:
    p=page.get('properties',{})
    return {"page_id":page.get('id'),"entity_id":_rich(p.get(P_ENTITY,{})),"tech_page_id":_rich(p.get(P_TECH_PAGE,{})),"url":(p.get(P_URL) or {}).get('url') or "","immutable_url":(p.get(P_IMMUTABLE) or {}).get('url') or "",
            "resolved_url":(p.get(P_RESOLVED) or {}).get('url') or "","source_version":_rich(p.get(P_VERSION,{})),"source_type":_rich(p.get(P_SOURCE,{})),"source_health":((p.get(P_HEALTH) or {}).get('select') or {}).get('name') or "",
            "authority_class":_rich(p.get(P_AUTHORITY,{})),"decision_eligible":bool((p.get(P_ELIGIBLE) or {}).get('checkbox')),"authority_reason":_rich(p.get(P_AUTH_REASON,{})),
            "entity_binding":_rich(p.get(P_BINDING,{})),"entity_binding_reason":_rich(p.get(P_BIND_REASON,{})),
            "document_hash":_rich(p.get(P_DOC_HASH,{})),"extract_hash":_rich(p.get(P_EXTRACT_HASH,{})),"extract":_rich(p.get(P_EXTRACT,{}))}


def check_health(state:dict, fetcher)->dict:
    """Fetcher(url)->(status_code, text, final_url).  Never calls Gemini."""
    try: status,text,final_url=fetcher(state['url'])
    except Exception as exc: return {"health":"FETCH_ERROR","error":str(exc),"material":False}
    now=datetime.now(timezone.utc).isoformat()
    if status in {404,410}: return {"health":"MISSING","material":True,"verified_at":now,"final_url":final_url or state['url']}
    if status < 200 or status >= 400: return {"health":"FETCH_ERROR","material":False,"verified_at":now,"final_url":final_url or state['url']}
    if final_url and not same_first_party(state['url'],final_url): return {"health":"MISSING","material":True,"verified_at":now,"final_url":final_url}
    current_norm=normalize_text(text); extract_norm=normalize_text(state.get('extract') or '')
    new_doc=content_hash(text)
    moved=bool(final_url and canonical_url(final_url)!=canonical_url(state['url']))
    if extract_norm and extract_norm in current_norm:
        health="MOVED" if moved else ("VERIFIED" if new_doc==state.get('document_hash') else "COSMETIC_CHANGE")
        return {"health":health,"material":False,"verified_at":now,"final_url":final_url or state['url'],"document_hash":new_doc}
    return {"health":"MATERIAL_CHANGE","material":True,"verified_at":now,"final_url":final_url or state['url'],"document_hash":new_doc}


def query_health_candidates(token:str, limit:int|None=None)->list[dict]:
    if not ENABLE_EVIDENCE_LEDGER: return []
    cap=EVIDENCE_HEALTH_MAX_CHECKS_PER_RUN if limit is None else max(0,int(limit))
    if cap<=0: return []
    payload={"filter":{"property":P_ACTIVE,"checkbox":{"equals":True}},"sorts":[{"property":P_VERIFIED,"direction":"ascending"}],"page_size":min(100,cap)}
    r=requests.post(_query_url(),headers=_headers(token),json=payload,timeout=20); r.raise_for_status()
    return [page_to_state(x) for x in (r.json().get('results') or [])[:cap]]


def update_health(page_id:str, result:dict, token:str, rereview_triggered:bool=False)->None:
    props={P_HEALTH:_select(result.get('health')),P_VERIFIED:_date(result.get('verified_at') or datetime.now(timezone.utc).isoformat()),P_TRIGGER:{"checkbox":bool(rereview_triggered)}}
    if result.get('final_url'): props[P_RESOLVED]={"url":result.get('final_url')}
    if result.get('document_hash'): props[P_DOC_HASH]=_rt(result.get('document_hash'))
    r=requests.patch(f"https://api.notion.com/v1/pages/{page_id}",headers=_headers(token),json={"properties":props},timeout=15); r.raise_for_status()
