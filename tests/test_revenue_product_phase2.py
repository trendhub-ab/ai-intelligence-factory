import os, sys, json, tempfile, unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
os.environ.setdefault('GEMINI_DEEP_DIVE_CALL_PACING_SECONDS','0')

# Minimal google-genai stub for offline unit environments.
try:
    import google.genai  # noqa
except Exception:
    import types
    google_pkg = sys.modules.get('google') or types.ModuleType('google'); google_pkg.__path__ = getattr(google_pkg,'__path__',[])
    genai_mod = types.ModuleType('google.genai'); errors_mod = types.ModuleType('google.genai.errors')
    class _Client:
        def __init__(self,*a,**k): self.chats = MagicMock()
    class _APIError(Exception):
        def __init__(self,*a,code=None,**k): super().__init__(*a); self.code=code
    genai_mod.Client=_Client; errors_mod.APIError=_APIError; google_pkg.genai=genai_mod
    sys.modules['google']=google_pkg; sys.modules['google.genai']=genai_mod; sys.modules['google.genai.errors']=errors_mod

import decision_intelligence as di
import pipeline


def resp(status=200, data=None, text=''):
    r=MagicMock(); r.status_code=status; r.json.return_value=data or {}; r.text=text
    r.raise_for_status.side_effect = None if status < 400 else RuntimeError(text or str(status))
    return r


def rt(v): return {'rich_text':[{'plain_text':v, 'text':{'content':v}}]} if v else {'rich_text':[]}
def title(v): return {'title':[{'plain_text':v, 'text':{'content':v}}]} if v else {'title':[]}
def sel(v): return {'select':{'name':v}} if v else {'select':None}
def date(v): return {'date':{'start':v}} if v else {'date':None}


def tech_page(eid='github:o/r', state='ASSESSED', eligible=True, tracking='ACTIVE', score=70, status='TEST'):
    return {'id':'tech-'+eid.replace(':','-').replace('/','-'), 'properties':{
        di.TECH_PROP_NAME:title('o/r'), di.TECH_PROP_PRIMARY_URL:{'url':'https://github.com/o/r'},
        di.TECH_PROP_SOURCE:{'multi_select':[{'name':'GitHub'}]}, di.TECH_PROP_CATEGORY:sel('DEVTOOLS'),
        di.TECH_PROP_ADOPTION_SCORE:{'number':score}, di.TECH_PROP_ADOPTION_STATUS:sel(status),
        di.TECH_PROP_EVIDENCE_CONFIDENCE:sel('MEDIUM'), di.TECH_PROP_PRODUCTION_READINESS:sel('MEDIUM'),
        di.TECH_PROP_MAIN_RISK:rt('互換性の確認が必要'), di.TECH_PROP_BEST_FOR:rt('検証チーム'),
        di.TECH_PROP_AVOID_FOR:rt('即時全面導入'), di.TECH_PROP_SHORT_RATIONALE:rt('限定検証向け'),
        di.TECH_PROP_FIRST_SEEN:date('2026-08-01T00:00:00+00:00'), di.TECH_PROP_LAST_REVIEWED:date('2026-08-01T00:00:00+00:00'),
        di.TECH_PROP_SCORE_CHANGE:{'number':5}, di.TECH_PROP_RELATED_ARTICLE:{'url':None},
        di.TECH_PROP_EVIDENCE_URLS:rt('https://github.com/o/r'), di.TECH_PROP_ENTITY_ID:rt(eid),
        di.TECH_PROP_ENTITY_STATUS:sel('RESOLVED'), di.TECH_PROP_ENTITY_ALIASES:rt('https://github.com/o/r'),
        di.TECH_PROP_TRACKING_STATUS:sel(tracking), di.TECH_PROP_TRACKING_ELIGIBILITY:{'checkbox':eligible},
        di.TECH_PROP_TRACKING_REASON:rt('継続監視'), di.TECH_PROP_ASSESSMENT_STATE:sel(state),
        di.TECH_PROP_NEXT_REVIEW:date('2026-08-01T00:00:00+00:00'), di.TECH_PROP_SCREENING_SCORE:{'number':80},
        di.TECH_PROP_SCREENING_REASON:rt('重要'), di.TECH_PROP_SOURCE_SUMMARY:rt('summary'),
    }}


def sub_page(eid='github:o/r', score=70):
    return {'id':'sub1','properties':{
        di.SUB_PROP_NAME:title('o/r'), di.SUB_PROP_PRIMARY_URL:{'url':'https://github.com/o/r'},
        di.SUB_PROP_SOURCE:{'multi_select':[{'name':'GitHub'}]}, di.SUB_PROP_CATEGORY:sel('DEVTOOLS'),
        di.SUB_PROP_ADOPTION_SCORE:{'number':score}, di.SUB_PROP_ADOPTION_STATUS:sel('TEST'),
        di.SUB_PROP_EVIDENCE_CONFIDENCE:sel('MEDIUM'), di.SUB_PROP_PRODUCTION_READINESS:sel('MEDIUM'),
        di.SUB_PROP_MAIN_RISK:rt('互換性の確認が必要'), di.SUB_PROP_BEST_FOR:rt('検証チーム'), di.SUB_PROP_AVOID_FOR:rt('即時全面導入'),
        di.SUB_PROP_SHORT_RATIONALE:rt('限定検証向け'), di.SUB_PROP_FIRST_SEEN:date('2026-08-01T00:00:00+00:00'),
        di.SUB_PROP_LAST_REVIEWED:date('2026-08-01T00:00:00+00:00'), di.SUB_PROP_SCORE_CHANGE:{'number':5},
        di.SUB_PROP_RELATED_ARTICLE:{'url':None}, di.SUB_PROP_EVIDENCE_URLS:rt('https://github.com/o/r'), di.SUB_PROP_ENTITY_ID:rt(eid)
    }}

class Phase2HistoryTests(unittest.TestCase):
    def test_small_score_change_not_meaningful(self):
        cur={'adoption_score':70,'adoption_status':'TEST','production_readiness':'MEDIUM','evidence_confidence':'MEDIUM','main_risk':'互換性の確認が必要','evidence_urls':['https://a'], 'last_change_at':'x'}
        a={'adoption_score':72,'adoption_status':'TEST','production_readiness':'MEDIUM','evidence_confidence':'MEDIUM','main_risk':'互換性の確認が必要','evidence_urls':['https://a']}
        self.assertFalse(di._diff_assessment(cur,a)['meaningful_change'])
    def test_large_score_change_is_meaningful(self):
        cur={'adoption_score':70,'adoption_status':'TEST','production_readiness':'MEDIUM','evidence_confidence':'MEDIUM','main_risk':'互換性','evidence_urls':[]}
        a={'adoption_score':76,'adoption_status':'TEST','production_readiness':'MEDIUM','evidence_confidence':'MEDIUM','main_risk':'互換性','evidence_urls':[]}
        self.assertTrue(di._diff_assessment(cur,a)['meaningful_change'])
    def test_similar_risk_paraphrase_is_not_change(self):
        self.assertFalse(di._risk_meaningfully_changed('既存環境との互換性リスクが高い','既存環境との互換性リスクが高い'))
    def test_watch_test_hysteresis(self):
        cur={'adoption_score':60,'adoption_status':'WATCH'}
        a={'adoption_score':62,'adoption_status':'TEST'}
        self.assertEqual(di._apply_status_hysteresis(cur,a)['adoption_status'],'WATCH')
    def test_watch_test_real_move_allowed(self):
        cur={'adoption_score':60,'adoption_status':'WATCH'}
        a={'adoption_score':66,'adoption_status':'TEST'}
        self.assertEqual(di._apply_status_hysteresis(cur,a)['adoption_status'],'TEST')

class TrackingTests(unittest.TestCase):
    def test_batch_parser_reads_tracking_signal(self):
        text=json.dumps([{'id':'B1','score':52,'commercial_score':50,'shelf_life_score':60,'topic':'SECURITY','tracking_eligible':True,'tracking_reason':'AVOID判断に重要','reason':'記事性は低い'}])
        parsed, missing = pipeline._parse_batch_screening_response(text, {'B1'})
        self.assertFalse(missing); self.assertTrue(parsed['B1']['tracking_eligible'])
    def test_missing_tracking_falls_back_to_score(self):
        text=json.dumps([{'id':'B1','score':70,'commercial_score':50,'shelf_life_score':60,'topic':'MODEL','reason':'x'}])
        parsed, _ = pipeline._parse_batch_screening_response(text, {'B1'})
        self.assertTrue(parsed['B1']['tracking_eligible'])
    def test_tracking_seed_does_not_downgrade_assessed(self):
        old_enabled=di.ENABLE_DECISION_INTELLIGENCE_DB; di.ENABLE_DECISION_INTELLIGENCE_DB=True
        existing=tech_page(state='ASSESSED')
        resolution=di.EntityResolution('github:o/r','RESOLVED','https://github.com/o/r',('https://github.com/o/r',),'x')
        with patch.object(di,'get_technology_record_by_entity_id',return_value=existing), patch.object(di.requests,'patch',return_value=resp(200)) as px:
            di.upsert_tracking_seed({'name':'o/r','source':'GitHub','screening_score':80,'tracking_eligibility':True,'analyzed_at':'2026-08-22T00:00:00+00:00'},resolution)
            props=px.call_args.kwargs['json']['properties']
            self.assertNotIn(di.TECH_PROP_ASSESSMENT_STATE,props)
        di.ENABLE_DECISION_INTELLIGENCE_DB=old_enabled

class SourceRoiTests(unittest.TestCase):
    def test_provider_failure_excluded_from_denominator(self):
        funnel=MagicMock(); funnel.records=[{'source':'ArXiv','generation_request_count':2,'final_status':pipeline.CONTENT_STATUS_PENDING_RETRY,'reason_codes':[{'reason_code':pipeline.REASON_CODE_MODEL_UNAVAILABLE}]}]
        m=pipeline.build_source_roi_run_metrics([],funnel)
        self.assertEqual(m['ArXiv']['deep_dive_attempted'],0); self.assertEqual(m['ArXiv']['generation_requests'],0)
    def test_quality_failure_still_counts(self):
        funnel=MagicMock(); funnel.records=[{'source':'ArXiv','generation_request_count':2,'final_status':pipeline.CONTENT_STATUS_QUALITY_FAILED,'reason_codes':[]}]
        m=pipeline.build_source_roi_run_metrics([],funnel)
        self.assertEqual(m['ArXiv']['deep_dive_attempted'],1); self.assertEqual(m['ArXiv']['generation_requests'],2)
    def test_v1_state_is_discarded(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'s.json'; p.write_text(json.dumps({'version':1,'runs':[{'sources':{}}]}))
            old=pipeline.ENABLE_SOURCE_ROI_LEARNING; pipeline.ENABLE_SOURCE_ROI_LEARNING=True
            self.assertEqual(pipeline.load_source_roi_state(str(p))['version'],2)
            pipeline.ENABLE_SOURCE_ROI_LEARNING=old

class DeferredTests(unittest.TestCase):
    def test_expired_queue_item_removed(self):
        old_path=pipeline.DEFERRED_DEEP_DIVE_STATE_PATH; old_repo=pipeline.EYECATCH_GITHUB_REPO; old_pat=pipeline.GH_PAT
        with tempfile.TemporaryDirectory() as td:
            pipeline.DEFERRED_DEEP_DIVE_STATE_PATH=str(Path(td)/'q.json'); pipeline.EYECATCH_GITHUB_REPO=''; pipeline.GH_PAT=''
            Path(pipeline.DEFERRED_DEEP_DIVE_STATE_PATH).write_text(json.dumps({'items':[{'key':'x','expires_at':(datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),'repo':{}}]}))
            self.assertEqual(pipeline.load_deferred_deep_dive_queue(),[])
        pipeline.DEFERRED_DEEP_DIVE_STATE_PATH=old_path; pipeline.EYECATCH_GITHUB_REPO=old_repo; pipeline.GH_PAT=old_pat
    def test_persistence_failure_falls_back_to_notion_pending(self):
        c={'repo':{'source':'GitHub','nameWithOwner':'o/r','url':'https://github.com/o/r'},'notion_page_id':'p1','score':80,'shelf_life':'EVERGREEN'}
        with patch.object(pipeline,'load_deferred_deep_dive_queue',return_value=[]), patch.object(pipeline,'save_deferred_deep_dive_queue',return_value=False), patch.object(pipeline,'_mark_pending_retry_or_escalate') as mark:
            pipeline.enqueue_deferred_candidates([c]); mark.assert_called_once()
    def test_queue_dedupes_by_identity(self):
        c={'repo':{'source':'GitHub','nameWithOwner':'o/r','url':'https://github.com/o/r'},'notion_page_id':'p1','score':80,'shelf_life':'EVERGREEN'}
        captured={}
        def save(rows): captured['rows']=rows; return True
        with patch.object(pipeline,'load_deferred_deep_dive_queue',return_value=[pipeline._deferred_serializable(c)]), patch.object(pipeline,'save_deferred_deep_dive_queue',side_effect=save):
            pipeline.enqueue_deferred_candidates([c]); self.assertEqual(len(captured['rows']),1)

class BudgetTests(unittest.TestCase):
    def test_product_budget_is_separate(self):
        b=pipeline.ProductReviewRequestBudget(2); b.consume('product_review'); b.consume('product_review')
        self.assertFalse(b.can_request()); self.assertEqual(b.used,2)
    def test_product_budget_does_not_consume_deep_dive_counter(self):
        old_pr=pipeline.PRODUCT_REVIEW_REQUEST_BUDGET; old_dd=pipeline.DEEP_DIVE_MODEL_BUDGET
        pipeline.PRODUCT_REVIEW_REQUEST_BUDGET=pipeline.ProductReviewRequestBudget(1); pipeline.DEEP_DIVE_MODEL_BUDGET=pipeline.DeepDiveModelBudget(12)
        with patch.object(pipeline.PERSISTENT_GEMINI_COUNTER,'reserve'), patch.object(pipeline.GEMINI_BUDGET,'can_request',return_value=True), patch.object(pipeline.GEMINI_BUDGET,'consume'):
            with patch.object(pipeline.GEMINI_USAGE_AUDIT,'record_attempt',return_value=1):
                pipeline._consume_gemini_request('product_review',model_name='m',request_origin='product_review')
        self.assertEqual(pipeline.PRODUCT_REVIEW_REQUEST_BUDGET.used,1); self.assertEqual(pipeline.DEEP_DIVE_MODEL_BUDGET.used,0)
        pipeline.PRODUCT_REVIEW_REQUEST_BUDGET=old_pr; pipeline.DEEP_DIVE_MODEL_BUDGET=old_dd

class SubscriberTests(unittest.TestCase):
    def setUp(self):
        self.old=(di.ENABLE_DECISION_INTELLIGENCE_DB,di.ENABLE_SUBSCRIBER_TECH_SYNC)
        di.ENABLE_DECISION_INTELLIGENCE_DB=True; di.ENABLE_SUBSCRIBER_TECH_SYNC=True
    def tearDown(self): di.ENABLE_DECISION_INTELLIGENCE_DB,di.ENABLE_SUBSCRIBER_TECH_SYNC=self.old
    def test_assessed_only_sync_unchanged_no_patch(self):
        with patch.object(di,'query_technology_records',return_value=[tech_page()]), patch.object(di,'_query_external_db',return_value=[sub_page()]), patch.object(di.requests,'patch') as px, patch.object(di.requests,'post') as po:
            r=di.sync_subscriber_technology_db(); self.assertEqual(r['unchanged'],1); px.assert_not_called(); po.assert_not_called()
    def test_unassessed_internal_archives_existing_subscriber(self):
        with patch.object(di,'query_technology_records',return_value=[tech_page(state='LEGACY_PENDING',eligible=False,score=None)]), patch.object(di,'_query_external_db',return_value=[sub_page()]), patch.object(di.requests,'patch',return_value=resp(200)) as px:
            r=di.sync_subscriber_technology_db(); self.assertEqual(r['archived'],1); self.assertTrue(px.call_args.kwargs['json']['archived'])
    def test_unknown_manual_subscriber_row_not_archived(self):
        with patch.object(di,'query_technology_records',return_value=[]), patch.object(di,'_query_external_db',return_value=[sub_page('manual:x')]), patch.object(di.requests,'patch') as px:
            r=di.sync_subscriber_technology_db(); self.assertEqual(r['archived'],0); px.assert_not_called()

class MonthlyTests(unittest.TestCase):
    def setUp(self):
        self.old=(di.ENABLE_DECISION_INTELLIGENCE_DB,di.ENABLE_DECISION_MONTHLY_DIGEST)
        di.ENABLE_DECISION_INTELLIGENCE_DB=True; di.ENABLE_DECISION_MONTHLY_DIGEST=True
    def tearDown(self): di.ENABLE_DECISION_INTELLIGENCE_DB,di.ENABLE_DECISION_MONTHLY_DIGEST=self.old
    def test_existing_period_is_idempotent(self):
        with patch.object(di,'_monthly_exists',return_value=True), patch.object(di,'query_history_records') as q:
            r=di.create_history_monthly_digest('2026-08'); self.assertFalse(r['created']); q.assert_not_called()
    def test_pagination_reads_all_history(self):
        pages=[resp(200,{'results':[{'id':'1'}],'has_more':True,'next_cursor':'c'}), resp(200,{'results':[{'id':'2'}],'has_more':False})]
        with patch.object(di.requests,'post',side_effect=pages):
            self.assertEqual(len(di.query_history_records(max_records=10)),2)
    def test_history_safety_limit_fails_closed(self):
        with patch.object(di.requests,'post',return_value=resp(200,{'results':[{'id':'1'},{'id':'2'}],'has_more':False})):
            with self.assertRaises(RuntimeError): di.query_history_records(max_records=1)
    def test_month_bounds_use_japan_month(self):
        start,end=di._month_bounds('2026-08'); self.assertIn('2026-07-31T15:00:00',start); self.assertIn('2026-08-31T15:00:00',end)

class SchemaTests(unittest.TestCase):
    def test_subscriber_and_monthly_schema_validation(self):
        di._validate_schema({k:{'type':v} for k,v in di.SUBSCRIBER_REQUIRED_PROPERTY_TYPES.items()},di.SUBSCRIBER_REQUIRED_PROPERTY_TYPES,'subscriber')
        di._validate_schema({k:{'type':v} for k,v in di.MONTHLY_REQUIRED_PROPERTY_TYPES.items()},di.MONTHLY_REQUIRED_PROPERTY_TYPES,'monthly')
    def test_schema_missing_fails(self):
        with self.assertRaises(ValueError): di._validate_schema({},di.SUBSCRIBER_REQUIRED_PROPERTY_TYPES,'subscriber')

if __name__=='__main__': unittest.main()

class Phase2ReleaseEdgeTests(unittest.TestCase):
    def test_subscriber_compare_ignores_list_order(self):
        internal = tech_page()
        internal['properties'][di.TECH_PROP_SOURCE]={'multi_select':[{'name':'ArXiv'},{'name':'GitHub'}]}
        internal['properties'][di.TECH_PROP_EVIDENCE_URLS]=rt('https://b\nhttps://a')
        dest = sub_page()
        dest['properties'][di.SUB_PROP_SOURCE]={'multi_select':[{'name':'GitHub'},{'name':'ArXiv'}]}
        dest['properties'][di.SUB_PROP_EVIDENCE_URLS]=rt('https://a\nhttps://b')
        i=di._subscriber_values_from_internal(internal); d=di._subscriber_values_from_destination(dest)
        for k in ('assessment_state','tracking_eligibility','tracking_status'): i.pop(k,None)
        self.assertEqual(i,d)

    def test_legacy_bootstrap_slot_is_reserved(self):
        old=(pipeline.PRODUCT_REVIEW_MAX_PER_RUN,pipeline.LEGACY_BOOTSTRAP_MAX_PER_RUN,pipeline.ENABLE_REVENUE_PRODUCT_PHASE2,di.ENABLE_DECISION_INTELLIGENCE_DB)
        pipeline.PRODUCT_REVIEW_MAX_PER_RUN=2; pipeline.LEGACY_BOOTSTRAP_MAX_PER_RUN=1; pipeline.ENABLE_REVENUE_PRODUCT_PHASE2=True; di.ENABLE_DECISION_INTELLIGENCE_DB=True
        active1=tech_page('github:a/one',state='SCREENED'); active2=tech_page('github:a/two',state='SCREENED')
        legacy=tech_page('github:l/old',state='LEGACY_PENDING',eligible=False,score=None)
        with patch.object(di,'query_technology_records',return_value=[active1,active2,legacy]):
            selected=pipeline.select_product_review_candidates()
        self.assertEqual(len(selected),2); self.assertTrue(any(x.get('assessment_state')=='LEGACY_PENDING' for x in selected))
        pipeline.PRODUCT_REVIEW_MAX_PER_RUN,pipeline.LEGACY_BOOTSTRAP_MAX_PER_RUN,pipeline.ENABLE_REVENUE_PRODUCT_PHASE2,di.ENABLE_DECISION_INTELLIGENCE_DB=old

    def test_persistent_reject_does_not_consume_product_budget(self):
        old_pr=pipeline.PRODUCT_REVIEW_REQUEST_BUDGET
        pipeline.PRODUCT_REVIEW_REQUEST_BUDGET=pipeline.ProductReviewRequestBudget(1)
        with patch.object(pipeline.GEMINI_BUDGET,'can_request',return_value=True), patch.object(pipeline.PERSISTENT_GEMINI_COUNTER,'reserve',side_effect=RuntimeError('provider cap')):
            with self.assertRaises(RuntimeError):
                pipeline._consume_gemini_request('product_review',model_name='m',request_origin='product_review')
        self.assertEqual(pipeline.PRODUCT_REVIEW_REQUEST_BUDGET.used,0)
        pipeline.PRODUCT_REVIEW_REQUEST_BUDGET=old_pr

    def test_monthly_maintenance_recovers_three_completed_months(self):
        old=(pipeline.ENABLE_REVENUE_PRODUCT_PHASE2,di.ENABLE_DECISION_INTELLIGENCE_DB,di.ENABLE_DECISION_MONTHLY_DIGEST)
        pipeline.ENABLE_REVENUE_PRODUCT_PHASE2=True; di.ENABLE_DECISION_INTELLIGENCE_DB=True; di.ENABLE_DECISION_MONTHLY_DIGEST=True
        seen=[]
        with patch.object(di,'sync_subscriber_technology_db',return_value={'enabled':False}), patch.object(di,'create_history_monthly_digest',side_effect=lambda p: seen.append(p) or {'created':False,'period_id':p}):
            pipeline.run_product_delivery_maintenance(today=datetime(2026,8,22).date())
        self.assertEqual(seen,['2026-07','2026-06','2026-05'])
        pipeline.ENABLE_REVENUE_PRODUCT_PHASE2,di.ENABLE_DECISION_INTELLIGENCE_DB,di.ENABLE_DECISION_MONTHLY_DIGEST=old

    def test_preflight_checks_all_four_enabled_schemas(self):
        old=(di.ENABLE_DECISION_INTELLIGENCE_DB,di.ENABLE_SUBSCRIBER_TECH_SYNC,di.ENABLE_DECISION_MONTHLY_DIGEST,di.NOTION_DECISION_INTELLIGENCE_API_KEY,di.NOTION_TECH_DATABASE_ID,di.NOTION_HISTORY_DATABASE_ID,di.NOTION_SUBSCRIBER_TECH_DATABASE_ID,di.NOTION_MONTHLY_DATABASE_ID)
        di.ENABLE_DECISION_INTELLIGENCE_DB=True; di.ENABLE_SUBSCRIBER_TECH_SYNC=True; di.ENABLE_DECISION_MONTHLY_DIGEST=True
        di.NOTION_DECISION_INTELLIGENCE_API_KEY='x'; di.NOTION_TECH_DATABASE_ID='t'; di.NOTION_HISTORY_DATABASE_ID='h'; di.NOTION_SUBSCRIBER_TECH_DATABASE_ID='s'; di.NOTION_MONTHLY_DATABASE_ID='m'
        payloads=[{'properties':{k:{'type':v} for k,v in spec.items()}} for spec in (di.TECH_REQUIRED_PROPERTY_TYPES,di.HISTORY_REQUIRED_PROPERTY_TYPES,di.SUBSCRIBER_REQUIRED_PROPERTY_TYPES,di.MONTHLY_REQUIRED_PROPERTY_TYPES)]
        with patch.object(di.requests,'get',side_effect=[resp(200,x) for x in payloads]) as gx:
            di.preflight_decision_intelligence_schema(); self.assertEqual(gx.call_count,4)
        (di.ENABLE_DECISION_INTELLIGENCE_DB,di.ENABLE_SUBSCRIBER_TECH_SYNC,di.ENABLE_DECISION_MONTHLY_DIGEST,di.NOTION_DECISION_INTELLIGENCE_API_KEY,di.NOTION_TECH_DATABASE_ID,di.NOTION_HISTORY_DATABASE_ID,di.NOTION_SUBSCRIBER_TECH_DATABASE_ID,di.NOTION_MONTHLY_DATABASE_ID)=old

class Phase2FailSafeExtraTests(unittest.TestCase):
    def test_ambiguous_legacy_is_not_sent_to_product_review(self):
        old=(pipeline.PRODUCT_REVIEW_MAX_PER_RUN,pipeline.LEGACY_BOOTSTRAP_MAX_PER_RUN,pipeline.ENABLE_REVENUE_PRODUCT_PHASE2,di.ENABLE_DECISION_INTELLIGENCE_DB)
        pipeline.PRODUCT_REVIEW_MAX_PER_RUN=2; pipeline.LEGACY_BOOTSTRAP_MAX_PER_RUN=1; pipeline.ENABLE_REVENUE_PRODUCT_PHASE2=True; di.ENABLE_DECISION_INTELLIGENCE_DB=True
        resolved=tech_page('github:r/ok',state='LEGACY_PENDING',eligible=False,score=None)
        ambiguous=tech_page('legacy:amb',state='LEGACY_PENDING',eligible=False,score=None)
        resolved['properties'][di.TECH_PROP_ENTITY_STATUS]=sel('RESOLVED')
        ambiguous['properties'][di.TECH_PROP_ENTITY_STATUS]=sel('AMBIGUOUS')
        with patch.object(di,'query_technology_records',return_value=[ambiguous,resolved]):
            selected=pipeline.select_product_review_candidates()
        self.assertEqual(len(selected),1); self.assertEqual(selected[0]['canonical_entity_id'],'github:r/ok')
        pipeline.PRODUCT_REVIEW_MAX_PER_RUN,pipeline.LEGACY_BOOTSTRAP_MAX_PER_RUN,pipeline.ENABLE_REVENUE_PRODUCT_PHASE2,di.ENABLE_DECISION_INTELLIGENCE_DB=old

    def test_screened_future_next_review_is_cooled_down(self):
        old=(pipeline.PRODUCT_REVIEW_MAX_PER_RUN,pipeline.ENABLE_REVENUE_PRODUCT_PHASE2,di.ENABLE_DECISION_INTELLIGENCE_DB)
        pipeline.PRODUCT_REVIEW_MAX_PER_RUN=2; pipeline.ENABLE_REVENUE_PRODUCT_PHASE2=True; di.ENABLE_DECISION_INTELLIGENCE_DB=True
        pg=tech_page('github:c/cool',state='SCREENED',eligible=True)
        pg['properties'][di.TECH_PROP_NEXT_REVIEW]=date((datetime.now(timezone.utc)+timedelta(days=5)).isoformat())
        with patch.object(di,'query_technology_records',return_value=[pg]):
            self.assertEqual(pipeline.select_product_review_candidates(),[])
        pipeline.PRODUCT_REVIEW_MAX_PER_RUN,pipeline.ENABLE_REVENUE_PRODUCT_PHASE2,di.ENABLE_DECISION_INTELLIGENCE_DB=old

    def test_deferred_queue_overflow_moves_evicted_to_pending(self):
        old=pipeline.DEFERRED_DEEP_DIVE_MAX_QUEUE; pipeline.DEFERRED_DEEP_DIVE_MAX_QUEUE=1
        a={'repo':{'source':'GitHub','nameWithOwner':'a/high','url':'https://github.com/a/high'},'notion_page_id':'p-high','score':90,'deep_dive_priority_score':90,'shelf_life':'EVERGREEN'}
        b={'repo':{'source':'GitHub','nameWithOwner':'b/low','url':'https://github.com/b/low'},'notion_page_id':'p-low','score':60,'deep_dive_priority_score':60,'shelf_life':'EVERGREEN'}
        with patch.object(pipeline,'load_deferred_deep_dive_queue',return_value=[]), patch.object(pipeline,'save_deferred_deep_dive_queue',return_value=True), patch.object(pipeline,'_mark_pending_retry_or_escalate') as mark:
            pipeline.enqueue_deferred_candidates([a,b])
            self.assertEqual(mark.call_count,1); self.assertEqual(mark.call_args.args[0],'p-low')
        pipeline.DEFERRED_DEEP_DIVE_MAX_QUEUE=old

class SubscriberAndMonthlyWriteTests(unittest.TestCase):
    def setUp(self):
        self.old=(di.ENABLE_DECISION_INTELLIGENCE_DB,di.ENABLE_SUBSCRIBER_TECH_SYNC,di.ENABLE_DECISION_MONTHLY_DIGEST)
        di.ENABLE_DECISION_INTELLIGENCE_DB=True; di.ENABLE_SUBSCRIBER_TECH_SYNC=True; di.ENABLE_DECISION_MONTHLY_DIGEST=True
    def tearDown(self):
        di.ENABLE_DECISION_INTELLIGENCE_DB,di.ENABLE_SUBSCRIBER_TECH_SYNC,di.ENABLE_DECISION_MONTHLY_DIGEST=self.old

    def test_subscriber_create_only_sanitized_properties(self):
        with patch.object(di,'query_technology_records',return_value=[tech_page()]), patch.object(di,'_query_external_db',return_value=[]), patch.object(di.requests,'post',return_value=resp(200,{'id':'new'})) as po:
            r=di.sync_subscriber_technology_db(); self.assertEqual(r['created'],1)
            props=po.call_args.kwargs['json']['properties']
            self.assertEqual(set(props),set(di.SUBSCRIBER_REQUIRED_PROPERTY_TYPES))
            self.assertNotIn(di.TECH_PROP_TRACKING_REASON,props)

    def test_subscriber_changed_record_is_patched_once(self):
        dest=sub_page(score=60)
        with patch.object(di,'query_technology_records',return_value=[tech_page(score=70)]), patch.object(di,'_query_external_db',return_value=[dest]), patch.object(di.requests,'patch',return_value=resp(200)) as px:
            r=di.sync_subscriber_technology_db(); self.assertEqual(r['updated'],1); self.assertEqual(px.call_count,1)

    def test_internal_entity_collision_fails_closed(self):
        with patch.object(di,'query_technology_records',return_value=[tech_page(),tech_page()]), patch.object(di,'_query_external_db',return_value=[]):
            with self.assertRaises(RuntimeError): di.sync_subscriber_technology_db()

    def test_monthly_create_writes_period_once(self):
        with patch.object(di,'_monthly_exists',return_value=False), patch.object(di,'query_history_records',return_value=[]), patch.object(di.requests,'post',return_value=resp(200,{'id':'month1'})) as po:
            r=di.create_history_monthly_digest('2026-07',generated_at='2026-08-01T00:00:00Z')
            self.assertTrue(r['created']); self.assertEqual(r['events'],0)
            props=po.call_args.kwargs['json']['properties']
            self.assertEqual(props[di.MONTHLY_PROP_PERIOD_ID]['rich_text'][0]['text']['content'],'2026-07')
