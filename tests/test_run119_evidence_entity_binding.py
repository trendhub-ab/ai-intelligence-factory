import sys, unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from evidence_authority import classify_evidence
import evidence_ledger

class Run119EvidenceEntityBindingTests(unittest.TestCase):
    def test_exact_github_repo_is_identity_bound(self):
        out=classify_evidence(url='https://github.com/mlflow/mlflow', role='PRIMARY_SOURCE', pipeline_source='GitHub', entity_id='github:mlflow/mlflow')
        self.assertEqual('IDENTITY_ANCHOR',out['entity_binding']); self.assertTrue(out['decision_eligible'])

    def test_other_github_repo_cannot_bind(self):
        out=classify_evidence(url='https://github.com/other/tool', role='PRIMARY_SOURCE', pipeline_source='GitHub', entity_id='github:mlflow/mlflow')
        self.assertEqual('UNBOUND',out['entity_binding']); self.assertFalse(out['decision_eligible'])

    def test_exact_arxiv_identity_is_bound_but_replicate_docs_are_not(self):
        ax=classify_evidence(url='https://arxiv.org/pdf/2608.13495.pdf', role='PRIMARY_SOURCE', pipeline_source='ArXiv', entity_id='arxiv:2608.13495')
        rp=classify_evidence(url='https://replicate.com/docs/arxiv/about', role='PRIMARY_SOURCE', raw_source_type='official_docs', pipeline_source='ArXiv', entity_id='arxiv:2608.13495')
        self.assertTrue(ax['decision_eligible']); self.assertEqual('IDENTITY_ANCHOR',ax['entity_binding'])
        self.assertEqual('OFFICIAL_DOCS',rp['source_type']); self.assertEqual('UNBOUND',rp['entity_binding']); self.assertFalse(rp['decision_eligible'])

    def test_arxiv_external_zenodo_is_not_same_paper_by_default(self):
        out=classify_evidence(url='https://doi.org/10.5281/zenodo.21878428', role='PRIMARY_SOURCE', raw_source_type='official_docs', pipeline_source='ArXiv', entity_id='arxiv:2608.16813')
        self.assertFalse(out['decision_eligible']); self.assertEqual('UNBOUND',out['entity_binding'])

    def test_github_homepage_from_repository_metadata_is_bound(self):
        details={'homepage':'https://mlflow.org'}
        out=classify_evidence(url='https://mlflow.org/docs/latest/genai/tracing', role='PRIMARY_SOURCE', raw_source_type='official_docs', origin='github_readme', pipeline_source='GitHub', entity_id='github:mlflow/mlflow', source_details=details)
        self.assertEqual('OFFICIAL_METADATA',out['entity_binding']); self.assertTrue(out['decision_eligible'])

    def test_unrelated_official_document_linked_from_readme_is_not_bound(self):
        details={'homepage':'https://aiengineer.co'}
        out=classify_evidence(url='https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf', role='PRIMARY_SOURCE', raw_source_type='official_docs', origin='github_readme', pipeline_source='GitHub', entity_id='github:owainlewis/awesome-artificial-intelligence', source_details=details)
        self.assertFalse(out['decision_eligible']); self.assertEqual('UNBOUND',out['entity_binding'])

    def test_producthunt_resolved_primary_site_remains_bound(self):
        out=classify_evidence(url='https://tool.example/docs', role='PRIMARY_SOURCE', raw_source_type='official_docs', origin='landing', pipeline_source='ProductHunt', primary_url='https://tool.example', entity_id='web:tool')
        self.assertTrue(out['decision_eligible']); self.assertEqual('SAME_PRIMARY_SITE',out['entity_binding'])

    def test_secondary_news_never_eligible_even_when_entity_binding_unknown(self):
        out=classify_evidence(url='https://reuters.com/technology/tool', role='PRIMARY_SOURCE', pipeline_source='HackerNews', primary_url='https://reuters.com/technology/tool', entity_id='web:tool')
        self.assertFalse(out['decision_eligible']); self.assertEqual('SECONDARY_NEWS',out['source_type'])

    def test_ledger_persists_binding_fields(self):
        info={'source':'ArXiv','primary_url':'https://arxiv.org/abs/2608.13495','canonical_entity_id':'arxiv:2608.13495','source_details':{},'verification_context':'paper',
              'evidence_documents':[{'url':'https://replicate.com/docs/arxiv/about','retrieved':True,'role':'PRIMARY_SOURCE','source_type':'official_docs','evidence_extract':'docs','document_text':'docs'}]}
        row=evidence_ledger.build_snapshots('arxiv:2608.13495','p1',info,'2026-08-24T00:00:00+00:00')[0]
        self.assertEqual('UNBOUND',row['entity_binding']); self.assertFalse(row['decision_eligible'])
        props=evidence_ledger._props(row); self.assertIn(evidence_ledger.P_BINDING,props); self.assertIn(evidence_ledger.P_BIND_REASON,props)

    def test_schema_migration_adds_binding_columns_idempotently(self):
        current=MagicMock(); current.raise_for_status.return_value=None; current.json.return_value={'properties':{
            evidence_ledger.P_AUTHORITY:{'type':'rich_text'}, evidence_ledger.P_ELIGIBLE:{'type':'checkbox'}, evidence_ledger.P_AUTH_REASON:{'type':'rich_text'}}}
        updated=MagicMock(); updated.raise_for_status.return_value=None
        with patch.object(evidence_ledger,'NOTION_EVIDENCE_DATA_SOURCE_ID','ds1'), patch.object(evidence_ledger.requests,'get',return_value=current), patch.object(evidence_ledger.requests,'patch',return_value=updated) as req:
            out=evidence_ledger.ensure_entity_binding_schema('token')
        self.assertEqual(set(out['added']),{evidence_ledger.P_BINDING,evidence_ledger.P_BIND_REASON})
        body=req.call_args.kwargs['json']['properties']; self.assertIn(evidence_ledger.P_BINDING,body)

if __name__=='__main__': unittest.main()
