import os, sys, unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
try:
    import google.genai  # noqa: F401
except Exception:
    import types
    google_pkg=sys.modules.get("google") or types.ModuleType("google"); google_pkg.__path__=getattr(google_pkg,"__path__",[])
    genai_mod=types.ModuleType("google.genai"); errors_mod=types.ModuleType("google.genai.errors")
    class _Client:
        def __init__(self,*a,**k): self.chats=MagicMock()
    class _APIError(Exception):
        def __init__(self,*a,code=None,**k): super().__init__(*a); self.code=code
    genai_mod.Client=_Client; errors_mod.APIError=_APIError; google_pkg.genai=genai_mod
    sys.modules["google"]=google_pkg; sys.modules["google.genai"]=genai_mod; sys.modules["google.genai.errors"]=errors_mod
import pipeline, decision_intelligence, migrate_japanese_display_label as migration


def valid_payload(**overrides):
    p={
        'category':'MODEL','adoption_score':75,
        'components':{
            'Evidence Quality':20,'Production Maturity':20,'Use-case Utility / Fit':15,
            'Reliability / Security Risk':10,'Integration / Migration Feasibility':7,
            'Ecosystem / Support Durability':3,
        },
        'adoption_status':'TEST','evidence_confidence':'HIGH','production_readiness':'MEDIUM',
        'main_risk':'運用条件の追加検証が必要','best_for':'限定PoC','avoid_for':'即時全面移行',
        'short_rationale':'一次資料に基づき限定検証が妥当','next_review_days':30,
    }
    p.update(overrides); return p

class Run120JapaneseDisplayLabelTests(unittest.TestCase):
    def test_optional_label_missing_never_invalidates_product_review(self):
        parsed=pipeline._parse_product_review_response(valid_payload())
        self.assertEqual('',parsed['japanese_display_label'])
        self.assertEqual(75,parsed['adoption_score'])

    def test_valid_label_is_preserved(self):
        parsed=pipeline._parse_product_review_response(valid_payload(japanese_display_label='MLflow — AI・MLの実験管理基盤'))
        self.assertEqual('MLflow — AI・MLの実験管理基盤',parsed['japanese_display_label'])

    def test_bad_label_is_soft_dropped_not_schema_failure(self):
        for label in ('MLflow experiment tracking','MLflow — 今すぐ導入を推奨','MLflow — ADOPT 95/100'):
            parsed=pipeline._parse_product_review_response(valid_payload(japanese_display_label=label))
            self.assertEqual('',parsed['japanese_display_label'])

    def test_unknown_structured_field_still_fails_closed(self):
        with self.assertRaises(ValueError):
            pipeline._parse_product_review_response(valid_payload(unknown_field='x'))

    def test_label_not_in_required_schema(self):
        self.assertIn('japanese_display_label',pipeline._PRODUCT_REVIEW_RESPONSE_SCHEMA['properties'])
        self.assertNotIn('japanese_display_label',pipeline._PRODUCT_REVIEW_RESPONSE_SCHEMA['required'])

    def test_label_does_not_change_meaningful_decision_diff(self):
        current={'adoption_score':70,'adoption_status':'TEST','production_readiness':'MEDIUM','evidence_confidence':'HIGH','main_risk':'運用リスク','evidence_urls':[],'last_change_at':''}
        assessment={'adoption_score':70,'adoption_status':'TEST','production_readiness':'MEDIUM','evidence_confidence':'HIGH','main_risk':'運用リスク','evidence_urls':[], 'japanese_display_label':'X — 新しい表示'}
        self.assertFalse(decision_intelligence._diff_assessment(current,assessment)['meaningful_change'])

    def test_existing_label_survives_missing_future_model_output(self):
        assessment={'technology_name':'MLflow','adoption_score':70,'adoption_status':'TEST','evidence_confidence':'HIGH','production_readiness':'MEDIUM','main_risk':'r','best_for':'b','avoid_for':'a','short_rationale':'s','reviewed_at':'2026-08-24T00:00:00+00:00','sources':['GitHub']}
        resolution=decision_intelligence.EntityResolution('github:mlflow/mlflow','RESOLVED','https://github.com/mlflow/mlflow',[], 'test')
        with patch.object(decision_intelligence,'ENABLE_JAPANESE_DISPLAY_LABEL',True):
            props=decision_intelligence._build_technology_properties(assessment,resolution,{'japanese_display_label':'MLflow — AI・MLの実験管理基盤'})
        self.assertIn(decision_intelligence.TECH_PROP_JAPANESE_DISPLAY_LABEL,props)

    def test_feature_disabled_never_writes_new_notion_property(self):
        assessment={'technology_name':'MLflow','japanese_display_label':'MLflow — AI・MLの実験管理基盤','adoption_score':70,'adoption_status':'TEST','evidence_confidence':'HIGH','production_readiness':'MEDIUM','main_risk':'r','best_for':'b','avoid_for':'a','short_rationale':'s','reviewed_at':'2026-08-24T00:00:00+00:00','sources':['GitHub']}
        resolution=decision_intelligence.EntityResolution('github:mlflow/mlflow','RESOLVED','https://github.com/mlflow/mlflow',[], 'test')
        with patch.object(decision_intelligence,'ENABLE_JAPANESE_DISPLAY_LABEL',False):
            props=decision_intelligence._build_technology_properties(assessment,resolution,{})
        self.assertNotIn(decision_intelligence.TECH_PROP_JAPANESE_DISPLAY_LABEL,props)

    def test_subscriber_sync_copies_only_display_field_not_internal_identity_logic(self):
        values={'name':'MLflow','japanese_display_label':'MLflow — AI・MLの実験管理基盤','sources':['GitHub'],'category':'MODEL','entity_id':'github:mlflow/mlflow'}
        with patch.object(decision_intelligence,'ENABLE_JAPANESE_DISPLAY_LABEL',True):
            props=decision_intelligence._subscriber_props(values)
        self.assertEqual('MLflow — AI・MLの実験管理基盤',props[decision_intelligence.SUB_PROP_JAPANESE_DISPLAY_LABEL]['rich_text'][0]['text']['content'])
        self.assertEqual('github:mlflow/mlflow',props[decision_intelligence.SUB_PROP_ENTITY_ID]['rich_text'][0]['text']['content'])

    def test_migration_is_idempotent_and_zero_gemini(self):
        existing=MagicMock(); existing.raise_for_status.return_value=None; existing.json.return_value={'properties':{migration.PROP:{'type':'rich_text'}}}
        with patch.object(migration,'TOKEN','token'), patch.object(migration.requests,'get',return_value=existing), patch.object(migration.requests,'patch') as patch_req:
            out=migration.ensure('ds','Technology Intelligence')
        self.assertFalse(out['changed']); patch_req.assert_not_called()

    def test_migration_adds_rich_text_only(self):
        current=MagicMock(); current.raise_for_status.return_value=None; current.json.return_value={'properties':{}}
        updated=MagicMock(); updated.raise_for_status.return_value=None
        with patch.object(migration,'TOKEN','token'), patch.object(migration.requests,'get',return_value=current), patch.object(migration.requests,'patch',return_value=updated) as patch_req:
            out=migration.ensure('ds','Technology Intelligence')
        self.assertTrue(out['changed'])
        self.assertEqual({migration.PROP:{'rich_text':{}}},patch_req.call_args.kwargs['json']['properties'])

if __name__=='__main__': unittest.main()
