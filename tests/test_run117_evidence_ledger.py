import os, sys, unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

import evidence_ledger

try:
    import google.genai  # noqa: F401
except Exception:
    import types
    google_pkg = sys.modules.get("google") or types.ModuleType("google")
    google_pkg.__path__ = getattr(google_pkg, "__path__", [])
    genai_mod = types.ModuleType("google.genai")
    errors_mod = types.ModuleType("google.genai.errors")
    class _Client:
        def __init__(self, *a, **k): self.chats = MagicMock()
    class _APIError(Exception):
        def __init__(self, *a, code=None, **k): super().__init__(*a); self.code = code
    genai_mod.Client = _Client
    errors_mod.APIError = _APIError
    google_pkg.genai = genai_mod
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_mod
    sys.modules["google.genai.errors"] = errors_mod
import pipeline

class Run117EvidenceLedgerTests(unittest.TestCase):
    def test_build_snapshot_keeps_live_and_immutable_url_separate(self):
        info={
            'primary_url':'https://github.com/org/repo', 'source':'GitHub',
            'verification_context':'README stable evidence',
            'evidence_documents':[{'url':'https://github.com/org/repo','retrieved':True,'role':'PRIMARY_SOURCE','source_type':'github','evidence_extract':'README stable evidence','document_text':'README stable evidence'}]
        }
        rows=evidence_ledger.build_snapshots('github:org/repo','page1',info,'2026-08-24T00:00:00+00:00',source_version='a'*40,immutable_url='https://github.com/org/repo/tree/'+'a'*40)
        self.assertEqual(1,len(rows)); r=rows[0]
        self.assertEqual('https://github.com/org/repo',r['url'])
        self.assertIn('/tree/',r['immutable_url'])
        self.assertEqual('a'*40,r['source_version'])
        self.assertTrue(r['extract_hash']); self.assertTrue(r['document_hash'])

    def test_cosmetic_change_does_not_trigger_material_review(self):
        state={'url':'https://docs.example/product','extract':'Feature Alpha is supported.','document_hash':evidence_ledger.content_hash('Feature Alpha is supported.')}
        out=evidence_ledger.check_health(state,lambda u:(200,'Header changed\nFeature Alpha is supported.\nFooter changed',u))
        self.assertEqual('COSMETIC_CHANGE',out['health']); self.assertFalse(out['material'])

    def test_material_change_triggers_review(self):
        state={'url':'https://docs.example/product','extract':'Feature Alpha is supported.','document_hash':'old'}
        out=evidence_ledger.check_health(state,lambda u:(200,'Feature Alpha has been removed.',u))
        self.assertEqual('MATERIAL_CHANGE',out['health']); self.assertTrue(out['material'])

    def test_404_is_missing_but_503_is_not_missing(self):
        state={'url':'https://docs.example/product','extract':'x','document_hash':'old'}
        missing=evidence_ledger.check_health(state,lambda u:(404,'',u))
        transient=evidence_ledger.check_health(state,lambda u:(503,'',u))
        self.assertEqual('MISSING',missing['health']); self.assertTrue(missing['material'])
        self.assertEqual('FETCH_ERROR',transient['health']); self.assertFalse(transient['material'])

    def test_cross_party_redirect_is_never_accepted_as_move(self):
        state={'url':'https://docs.example/product','extract':'Feature Alpha','document_hash':'old'}
        out=evidence_ledger.check_health(state,lambda u:(200,'Feature Alpha','https://evil.example/product'))
        self.assertEqual('MISSING',out['health']); self.assertTrue(out['material'])

    def test_same_party_redirect_is_moved_when_evidence_survives(self):
        state={'url':'https://docs.example/product','extract':'Feature Alpha','document_hash':evidence_ledger.content_hash('Feature Alpha')}
        out=evidence_ledger.check_health(state,lambda u:(200,'Feature Alpha','https://www.docs.example/product-v2'))
        self.assertEqual('MOVED',out['health']); self.assertFalse(out['material'])

    def test_health_maintenance_material_change_accelerates_next_review_without_gemini(self):
        state={'page_id':'ledger1','tech_page_id':'tech1','url':'https://docs.example/product','extract':'Old evidence','document_hash':'old'}
        fake_patch=MagicMock(); fake_patch.status_code=200
        with patch.object(evidence_ledger,'ENABLE_EVIDENCE_LEDGER',True), \
             patch.object(evidence_ledger,'query_health_candidates',return_value=[state]), \
             patch.object(evidence_ledger,'check_health',return_value={'health':'MATERIAL_CHANGE','material':True,'verified_at':'2026-08-24T00:00:00+00:00','final_url':state['url'],'document_hash':'new'}), \
             patch.object(evidence_ledger,'update_health') as upd, \
             patch.object(pipeline,'_http_get_health_limited') as fetch, \
             patch.object(pipeline.requests,'patch',return_value=fake_patch), \
             patch.object(pipeline.decision_intelligence,'NOTION_DECISION_INTELLIGENCE_API_KEY','token'):
            out=pipeline.run_evidence_health_maintenance()
        self.assertEqual(1,out['material']); self.assertEqual(1,out['checked'])
        fetch.assert_not_called()  # check_health was deliberately injected; proves maintenance adds no model/API generation path
        upd.assert_called_once(); self.assertTrue(upd.call_args.kwargs['rereview_triggered'])

    def test_github_version_resolver_returns_commit_permalink(self):
        resp=MagicMock(status_code=200); resp.json.return_value={'sha':'a'*40}
        info={'primary_url':'https://github.com/org/repo','source_details':{'default_branch':'main'}}
        with patch.object(pipeline,'GH_PAT','token'), patch.object(pipeline.requests,'get',return_value=resp):
            version,url=pipeline._resolve_evidence_source_version({'source':'GitHub','url':'https://github.com/org/repo','nameWithOwner':'org/repo'},info)
        self.assertEqual('a'*40,version); self.assertEqual('https://github.com/org/repo/tree/'+'a'*40,url)

    def test_arxiv_version_resolver_uses_versioned_url(self):
        info={'primary_url':'https://arxiv.org/abs/2608.12345','source_details':{'arxiv_version':'v2','arxiv_versioned_url':'https://arxiv.org/abs/2608.12345v2'}}
        version,url=pipeline._resolve_evidence_source_version({'source':'ArXiv','url':info['primary_url']},info)
        self.assertEqual('v2',version); self.assertTrue(url.endswith('v2'))

    def test_new_snapshot_deactivates_older_active_snapshot_after_create(self):
        snap={'entity_id':'github:org/repo','tech_page_id':'tech1','url':'https://github.com/org/repo','immutable_url':'https://github.com/org/repo/tree/'+'a'*40,
              'resolved_url':'https://github.com/org/repo','source_version':'a'*40,'source_type':'github','role':'PRIMARY_SOURCE',
              'retrieved_at':'2026-08-24T00:00:00+00:00','last_verified_at':'2026-08-24T00:00:00+00:00','source_health':'VERIFIED',
              'document_hash':'d','extract_hash':'e','extract':'evidence'}
        empty=MagicMock(); empty.raise_for_status.return_value=None; empty.json.return_value={'results':[]}
        created=MagicMock(); created.raise_for_status.return_value=None; created.json.return_value={'id':'new1'}
        active=MagicMock(); active.raise_for_status.return_value=None; active.json.return_value={'results':[{'id':'old1'},{'id':'new1'}]}
        off=MagicMock(); off.raise_for_status.return_value=None
        with patch.object(evidence_ledger,'ENABLE_EVIDENCE_LEDGER',True), \
             patch.object(evidence_ledger.requests,'post',side_effect=[empty,created,active]) as post, \
             patch.object(evidence_ledger.requests,'patch',return_value=off) as patch_req:
            out=evidence_ledger.persist_snapshots([snap],'token')
        self.assertEqual(1,out['saved']); self.assertEqual(3,post.call_count); self.assertEqual(1,patch_req.call_count)
        self.assertIn('/old1',patch_req.call_args.args[0]); self.assertFalse(patch_req.call_args.kwargs['json']['properties'][evidence_ledger.P_ACTIVE]['checkbox'])

    def test_ledger_disabled_is_zero_network(self):
        with patch.object(evidence_ledger,'ENABLE_EVIDENCE_LEDGER',False), patch.object(evidence_ledger.requests,'get') as get:
            evidence_ledger.preflight('')
            self.assertEqual({'enabled':False,'saved':0},evidence_ledger.persist_snapshots([],''))
            get.assert_not_called()

if __name__=='__main__': unittest.main()
