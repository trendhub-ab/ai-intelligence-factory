#!/usr/bin/env python3
import os, requests, json
PAGE="3d0479ff-dca9-81de-b614-fef528d2f32c"
headers={
 "Authorization":f"Bearer {os.environ['NOTION_DECISION_INTELLIGENCE_API_KEY']}",
 "Content-Type":"application/json",
 "Notion-Version":os.environ.get("NOTION_API_VERSION","2026-03-11"),
}
r=requests.get(f"https://api.notion.com/v1/pages/{PAGE}",headers=headers,timeout=10)
print(json.dumps({"status":r.status_code,"object":(r.json().get("object") if "application/json" in r.headers.get("content-type","") else None)}))
raise SystemExit(0 if r.status_code==200 else 1)
