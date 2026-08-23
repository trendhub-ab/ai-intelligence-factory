import sys, unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from evidence_authority import classify_evidence, authority_rank
import evidence_ledger

try:
    import google.genai  # noqa
except Exception:
    import types
    google_pkg=sys.modules.get('google') or types.ModuleType('google'); google_pkg.__path__=getattr(google_pkg,'__path__',[])
    genai_mod=types.ModuleType('google.genai'); errors_mod=types.ModuleType('google.genai.errors')
    class _Client:
        def __init__(self,*a,**k): self.chats=MagicMock()
    class _APIError(Exception): pass
    genai_mod.Client=_Client; errors_mod.APIError=_APIError; google_pkg.genai=genai_mod
    sys.modules['google']=google_pkg; sys.modules['google.genai']=genai_mod; sys.modules['google.genai.errors']=errors_mod
import pipeline

class Run118EvidenceAuthorityTests(unittest.TestCase):
    def test_github_and_arxiv_are_decision_eligible_primary(self):
        gh=classify_evidence(url='https://github.com/org/repo',role='PRIMARY_SOURCE',pipeline_source='GitHub')
        ax=classify_evidence(url='https://arxiv.org/abs/2608.12345',role='PRIMARY_SOURCE',pipeline_source='ArXiv')
        self.assertEqual(('GITHUB','PRIMARY_FIRST_PARTY',True),(gh['source_type'],gh['authority_class'],gh['decision_eligible']))
        self.assertEqual(('ARXIV','PRIMARY_FIRST_PARTY',True),(ax['source_type'],ax['authority_class'],ax['decision_eligible']))

    def test_discovery_platforms_never_become_decision_evidence(self):
        for url in ('https://news.ycombinator.com/item?id=1','https://www.producthunt.com/posts/tool'):
            out=classify_evidence(url=url,role='PRIMARY_SOURCE',pipeline_source='HackerNews')
            self.assertEqual('DISCOVERY',out['source_type']); self.assertFalse(out['decision_eligible'])

    def test_secondary_news_never_becomes_decision_evidence_even_if_role_primary(self):
        out=classify_evidence(url='https://www.reuters.com/technology/vendor-change',role='PRIMARY_SOURCE',pipeline_source='HackerNews')
        self.assertEqual('SECONDARY_NEWS',out['source_type']); self.assertEqual('SECONDARY',out['authority_class']); self.assertFalse(out['decision_eligible'])

    def test_official_docs_changelog_blog_and_regulatory_are_typed(self):
        docs=classify_evidence(url='https://vendor.example/docs/api',role='PRIMARY_SOURCE',raw_source_type='official_docs',label='Documentation')
        changelog=classify_evidence(url='https://vendor.example/changelog/v2',role='PRIMARY_SOURCE',label='Release notes')
        blog=classify_evidence(url='https://vendor.example/blog/launch',role='PRIMARY_SOURCE',label='Official announcement',origin='metadata')
        reg=classify_evidence(url='https://www.sec.gov/news/press-release',role='PRIMARY_SOURCE')
        self.assertEqual('OFFICIAL_DOCS',docs['source_type'])
        self.assertEqual('OFFICIAL_CHANGELOG',changelog['source_type'])
        self.assertEqual('OFFICIAL_BLOG',blog['source_type'])
        self.assertEqual('REGULATORY',reg['source_type'])
        self.assertTrue(all(x['decision_eligible'] for x in (docs,changelog,blog,reg)))

    def test_hn_external_original_can_remain_primary_but_known_news_cannot(self):
        author=classify_evidence(url='https://alice.example/research/tool',role='PRIMARY_SOURCE',pipeline_source='HackerNews')
        news=classify_evidence(url='https://techcrunch.com/2026/08/24/tool',role='PRIMARY_SOURCE',pipeline_source='HackerNews')
        self.assertEqual('AUTHOR_ORIGINAL',author['source_type']); self.assertTrue(author['decision_eligible'])
        self.assertEqual('SECONDARY_NEWS',news['source_type']); self.assertFalse(news['decision_eligible'])

    def test_producthunt_external_official_site_is_eligible(self):
        out=classify_evidence(url='https://tool.example/',role='PRIMARY_SOURCE',pipeline_source='ProductHunt',origin='metadata')
        self.assertEqual('OFFICIAL_SITE',out['source_type']); self.assertTrue(out['decision_eligible'])

    def test_supplemental_source_cannot_independently_raise_authority(self):
        out=classify_evidence(url='https://vendor.example/analysis',role='SUPPLEMENTAL_SOURCE',pipeline_source='GitHub')
        self.assertFalse(out['decision_eligible']); self.assertLess(authority_rank(out['authority_class']),2)

    def test_primary_authority_gate_accepts_official_supplement_behind_hn_discovery(self):
        info={'source':'HackerNews','primary_url':'https://news.ycombinator.com/item?id=1','primary_source_resolved':True,
              'evidence_documents':[
                  {'url':'https://news.ycombinator.com/item?id=1','retrieved':True,'role':'PRIMARY_SOURCE','source_type':'hackernews'},
                  {'url':'https://vendor.example/docs/tool','retrieved':True,'role':'PRIMARY_SOURCE','source_type':'official_docs','label':'Documentation','origin':'landing'},
              ]}
        self.assertEqual([],pipeline._primary_source_authority_failures(info))

    def test_primary_authority_gate_rejects_secondary_only_hn_evidence(self):
        info={'source':'HackerNews','primary_url':'https://reuters.com/technology/tool','primary_source_resolved':True,
              'evidence_documents':[{'url':'https://reuters.com/technology/tool','retrieved':True,'role':'PRIMARY_SOURCE','source_type':'web'}]}
        failures=pipeline._primary_source_authority_failures(info)
        self.assertTrue(failures); self.assertIn('secondary news',failures[0])

    def test_ledger_persists_authority_without_exposing_it_as_decision_score(self):
        info={'primary_url':'https://reuters.com/technology/tool','source':'HackerNews','verification_context':'reported detail',
              'evidence_documents':[{'url':'https://reuters.com/technology/tool','retrieved':True,'role':'PRIMARY_SOURCE','source_type':'web','evidence_extract':'reported detail','document_text':'reported detail'}]}
        rows=evidence_ledger.build_snapshots('web:tool','p1',info,'2026-08-24T00:00:00+00:00')
        self.assertEqual(1,len(rows)); row=rows[0]
        self.assertEqual('SECONDARY_NEWS',row['source_type']); self.assertEqual('SECONDARY',row['authority_class']); self.assertFalse(row['decision_eligible'])
        props=evidence_ledger._props(row)
        self.assertFalse(props[evidence_ledger.P_ELIGIBLE]['checkbox'])
        self.assertEqual('SECONDARY',props[evidence_ledger.P_AUTHORITY]['rich_text'][0]['text']['content'])

    def test_authority_schema_migration_is_idempotent(self):
        current=MagicMock(); current.raise_for_status.return_value=None; current.json.return_value={'properties':{}}
        updated=MagicMock(); updated.raise_for_status.return_value=None
        with patch.object(evidence_ledger,'NOTION_EVIDENCE_DATA_SOURCE_ID','ds1'), \
             patch.object(evidence_ledger.requests,'get',return_value=current), \
             patch.object(evidence_ledger.requests,'patch',return_value=updated) as patch_req:
            out=evidence_ledger.ensure_authority_schema('token')
        self.assertTrue(out['changed']); self.assertEqual(3,len(out['added']))
        body=patch_req.call_args.kwargs['json']['properties']
        self.assertIn(evidence_ledger.P_AUTHORITY,body); self.assertIn(evidence_ledger.P_ELIGIBLE,body)

        current2=MagicMock(); current2.raise_for_status.return_value=None; current2.json.return_value={'properties':{
            evidence_ledger.P_AUTHORITY:{'type':'rich_text'}, evidence_ledger.P_ELIGIBLE:{'type':'checkbox'}, evidence_ledger.P_AUTH_REASON:{'type':'rich_text'}}}
        with patch.object(evidence_ledger,'NOTION_EVIDENCE_DATA_SOURCE_ID','ds1'), \
             patch.object(evidence_ledger.requests,'get',return_value=current2), \
             patch.object(evidence_ledger.requests,'patch') as patch2:
            out2=evidence_ledger.ensure_authority_schema('token')
        self.assertFalse(out2['changed']); patch2.assert_not_called()

    def test_authority_summary_counts_only_eligible_documents(self):
        info={'source':'ProductHunt','primary_url':'https://tool.example','primary_source_resolved':True,
              'evidence_documents':[
                  {'url':'https://www.producthunt.com/posts/tool','retrieved':True,'role':'PRIMARY_SOURCE'},
                  {'url':'https://tool.example/docs','retrieved':True,'role':'PRIMARY_SOURCE','source_type':'official_docs'},
                  {'url':'https://reuters.com/technology/tool','retrieved':True,'role':'PRIMARY_SOURCE'},
              ]}
        summary=pipeline._evidence_authority_summary(info)
        self.assertEqual(3,summary['retrieved_documents']); self.assertEqual(1,summary['decision_eligible_documents'])
        self.assertIn('OFFICIAL_DOCS',summary['source_types']); self.assertIn('SECONDARY_NEWS',summary['source_types']); self.assertIn('DISCOVERY',summary['source_types'])

if __name__=='__main__': unittest.main()
