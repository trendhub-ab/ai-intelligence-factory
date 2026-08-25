import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

attrib = load('run134_attrib', 'subscription_attribution.py')
ib = load('run134_ib', 'inventory_bootstrap.py')
di = load('run134_di', 'decision_intelligence.py')

NOW = datetime(2026,8,25,tzinfo=timezone.utc)

def rec(**kw):
    base = dict(
        page_id='p', name='Tool', canonical_entity_id='github:org/tool', primary_url='https://github.com/org/tool',
        source=('GitHub',), category='DEVTOOLS', screening_score=80, source_summary='Useful tool', published_at=None,
        analyzed_at=None, next_review=None, assessment_state='ASSESSED', entity_resolution_status='RESOLVED',
        tracking_status='ACTIVE', tracking_eligibility=True, adoption_score=80, adoption_status='TEST',
        evidence_confidence='HIGH', production_readiness='MEDIUM',
        main_risk='Requires outbound network access and a dedicated service account in production.',
        best_for='Teams automating repeatable repository maintenance with controlled credentials.',
        avoid_for='Teams that cannot isolate credentials or audit automated repository changes.',
        short_rationale='Evidence supports a bounded production trial, but credential isolation remains mandatory.',
        primary_evidence_urls='https://github.com/org/tool', last_reviewed=NOW.isoformat(),
    )
    base.update(kw)
    return ib.TechnologyRecord(**base)

class Run134Tests(unittest.TestCase):
    def test_revenue_readiness_never_auto_enables_ranking(self):
        manifests = {}
        rows=[]
        for i in range(25):
            aid=f'a{i}'; manifests[aid]={'article_id':aid,'source':'GitHub','portfolio_topic':'AGENT'}
            rows.append({'article_id':aid,'attribution_method':'end_to_end','note_url':'','period_start':'','period_end':'',
                         'note_views':300.0,'cta_clicks':10.0,'new_subscribers':1.0,'retained_subscribers':1.0,'subscription_revenue_yen':1980.0})
        roll=attrib.build_rollup(manifests,rows)
        ready=roll['revenue_measurement_readiness']
        self.assertEqual('READY_FOR_HUMAN_REVENUE_REVIEW', ready['measurement_status'])
        self.assertFalse(ready['ranking_feedback_enabled'])
        self.assertFalse(ready['auto_feedback_permitted'])
        self.assertEqual('GitHub', roll['performance_by_source'][0]['source'])

    def test_revenue_readiness_reports_collection_blockers_on_small_sample(self):
        manifests={'a':{'article_id':'a','source':'ArXiv','portfolio_topic':'MODEL'}}
        rows=[{'article_id':'a','attribution_method':'note_dashboard_only','note_url':'','period_start':'','period_end':'',
               'note_views':100.0,'cta_clicks':None,'new_subscribers':None,'retained_subscribers':None,'subscription_revenue_yen':None}]
        ready=attrib.build_rollup(manifests,rows)['revenue_measurement_readiness']
        self.assertEqual('COLLECTING', ready['measurement_status'])
        self.assertTrue(any('new_subscribers' in x for x in ready['blockers']))

    def test_paid_product_utility_rewards_specific_decision_information(self):
        strong=ib.paid_product_utility(rec())
        weak=ib.paid_product_utility(rec(main_risk='導入には注意が必要です', best_for='AIを活用したい企業', avoid_for='慎重な企業', short_rationale='検討が必要です'))
        self.assertEqual('HIGH', strong['band'])
        self.assertGreater(strong['score'], weak['score'])
        self.assertIn(weak['band'], {'LOW','MEDIUM'})

    def test_paid_product_value_is_diagnostic_not_launch_blocker(self):
        rows=[]
        statuses=['ADOPT','TEST','WATCH','AVOID']; cats=['MODEL','AGENT','DEVTOOLS','SECURITY']
        for i in range(24):
            rows.append(rec(page_id=str(i), canonical_entity_id=f'e:{i}', adoption_status=statuses[i%4], category=cats[i%4],
                            source=('GitHub',) if i%2 else ('ArXiv',),
                            main_risk='導入には注意が必要です', best_for='AIを活用したい企業', avoid_for='慎重な企業', short_rationale='検討が必要です'))
        result=ib.evaluate_readiness(rows, subscriber_visible_count=24, now=NOW)
        self.assertTrue(result['launch_ready'])
        self.assertEqual('NEEDS_STRENGTHENING', result['paid_product_value']['status'])
        self.assertTrue(result['paid_product_value']['diagnostic_only'])

    def test_monthly_decision_brief_prioritizes_status_change(self):
        events=[
            {'technology_name':'A','adoption_status':'AVOID','previous_status':'AVOID','score_delta':20,'status_changed':False,'snapshot_type':'UPDATE'},
            {'technology_name':'B','adoption_status':'WATCH','previous_status':'TEST','score_delta':-4,'status_changed':True,'snapshot_type':'UPDATE'},
            {'technology_name':'C','adoption_status':'TEST','previous_status':'WATCH','score_delta':3,'status_changed':True,'snapshot_type':'UPDATE'},
        ]
        brief=di.build_monthly_decision_brief(events,limit=2)
        self.assertNotEqual('A',brief[0]['technology_name'])
        self.assertTrue(brief[0]['status_changed'])
        self.assertEqual(2,len(brief))

    def test_monthly_digest_writes_decision_brief_title_without_new_schema(self):
        fake=Mock(status_code=200); fake.json.return_value={'id':'m1'}
        with patch.object(di,'ENABLE_DECISION_MONTHLY_DIGEST',True), patch.object(di,'_monthly_exists',return_value=False), \
             patch.object(di,'query_history_records',return_value=[]), patch.object(di.requests,'post',return_value=fake) as post:
            out=di.create_history_monthly_digest('2026-08',generated_at='2026-09-01T00:00:00Z')
        props=post.call_args.kwargs['json']['properties']
        title=props[di.MONTHLY_PROP_TITLE]['title'][0]['text']['content']
        self.assertIn('何を再判断',title)
        self.assertEqual(0,out['decision_brief_count'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
