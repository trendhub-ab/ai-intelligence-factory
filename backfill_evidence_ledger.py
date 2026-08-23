#!/usr/bin/env python3
"""Zero-Gemini Evidence Ledger backfill for already-assessed Technology rows.

This creates *current verification snapshots* at backfill time. It never pretends to recreate
historical page contents that were not stored before Run117.
"""
from __future__ import annotations
import argparse, json
from datetime import datetime, timezone
import decision_intelligence, evidence_ledger, pipeline


def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('--limit',type=int,default=50); ap.add_argument('--dry-run',action='store_true'); ap.add_argument('--migrate-authority-schema',action='store_true'); args=ap.parse_args()
    decision_intelligence.preflight_decision_intelligence_schema()
    if args.migrate_authority_schema:
        token=decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY
        out={'authority':evidence_ledger.ensure_authority_schema(token),'entity_binding':evidence_ledger.ensure_entity_binding_schema(token),'zero_gemini_calls':True}
        print(json.dumps(out,ensure_ascii=False,indent=2)); return 0
    evidence_ledger.preflight(decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY)
    pages=decision_intelligence.query_technology_records(max_records=5000)
    result={'scanned':0,'eligible':0,'snapshots':0,'saved':0,'failed':0,'dry_run':args.dry_run,'zero_gemini_calls':True}
    now=datetime.now(timezone.utc).isoformat()
    for page in pages:
        if result['eligible']>=max(0,args.limit): break
        result['scanned']+=1; state=decision_intelligence.technology_page_to_state(page)
        if state.get('assessment_state')!='ASSESSED' or not state.get('primary_url'): continue
        result['eligible']+=1
        try:
            sources=state.get('sources') or []
            repo={'nameWithOwner':state.get('technology_name') or state.get('canonical_entity_id'),'url':state.get('primary_url'),'primaryUrl':state.get('primary_url'),
                  'source':sources[0] if sources else ('ArXiv' if str(state.get('canonical_entity_id','')).startswith('arxiv:') else 'GitHub'),
                  'canonicalEntityId':state.get('canonical_entity_id'),'sourceContext':'','sourceContextVerified':False,'sourceDetails':{}}
            info=pipeline.prepare_source_context(repo)
            evidence=pipeline.assess_evidence_sufficiency(info)
            if evidence.get('state')==pipeline.EVIDENCE_SUPPLEMENT_REQUIRED:
                info=pipeline.supplement_source_evidence(info)
            version,immutable=pipeline._resolve_evidence_source_version(repo,info)
            snaps=evidence_ledger.build_snapshots(state.get('canonical_entity_id') or '',page.get('id') or '',info,now,version,immutable)
            result['snapshots']+=len(snaps)
            if not args.dry_run:
                result['saved']+=evidence_ledger.persist_snapshots(snaps,decision_intelligence.NOTION_DECISION_INTELLIGENCE_API_KEY).get('saved',0)
        except Exception as exc:
            result['failed']+=1; print(f'[BACKFILL FAILED] {state.get("canonical_entity_id")}: {exc}')
    print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if result['failed']==0 else 1
if __name__=='__main__': raise SystemExit(main())
