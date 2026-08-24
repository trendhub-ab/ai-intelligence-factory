#!/usr/bin/env python3
"""Zero-Gemini, idempotent schema migration for Japanese Display Label.

Adds one RICH_TEXT property to the internal Technology Intelligence data source and the
sanitized Subscriber Technology data source. It never touches History because display labels
are UI metadata, not decision history.
"""
from __future__ import annotations
import json, os, sys
import requests

NOTION_API_VERSION=os.environ.get('NOTION_API_VERSION','2026-03-11')
TOKEN=os.environ.get('NOTION_DECISION_INTELLIGENCE_API_KEY','').strip()
TECH_DS=os.environ.get('NOTION_TECH_DATA_SOURCE_ID','').strip()
SUB_DS=os.environ.get('NOTION_SUBSCRIBER_TECH_DATA_SOURCE_ID','').strip()
PROP='Japanese Display Label'

def headers():
    return {'Authorization':f'Bearer {TOKEN}','Content-Type':'application/json','Notion-Version':NOTION_API_VERSION}

def ensure(ds: str, label: str) -> dict:
    if not ds: raise ValueError(f'{label} data source id missing')
    url=f'https://api.notion.com/v1/data_sources/{ds}'
    r=requests.get(url,headers=headers(),timeout=15); r.raise_for_status()
    props=r.json().get('properties',{})
    if PROP in props:
        actual=(props.get(PROP) or {}).get('type')
        if actual!='rich_text': raise ValueError(f'{label} {PROP} type mismatch: {actual}')
        return {'database':label,'changed':False,'added':[]}
    u=requests.patch(url,headers=headers(),json={'properties':{PROP:{'rich_text':{}}}},timeout=20); u.raise_for_status()
    return {'database':label,'changed':True,'added':[PROP]}

def main() -> int:
    if not TOKEN: raise ValueError('NOTION_DECISION_INTELLIGENCE_API_KEY missing')
    out={'technology':ensure(TECH_DS,'Technology Intelligence'),'subscriber':ensure(SUB_DS,'Subscriber Technology'),'zero_gemini_calls':True,
         'next_step':'Set repository variable ENABLE_JAPANESE_DISPLAY_LABEL=true after this migration succeeds.'}
    print(json.dumps(out,ensure_ascii=False,indent=2)); return 0

if __name__=='__main__':
    raise SystemExit(main())
