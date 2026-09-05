import ast
import inspect
import unittest
from types import SimpleNamespace

import candidate_identity as ci
import note_manuscript as nm
import gate_reasoning as gr
import screening_protocol as sp
import source_roi_policy as sr


class Run241BatchedModuleTests(unittest.TestCase):
    def test_candidate_identity_keeps_meaningful_query_and_drops_tracking(self):
        self.assertEqual(ci.canonicalize_url('HTTPS://Example.COM:443/a/?b=2&utm_source=x&a=1#frag'), 'https://example.com/a?a=1&b=2')
        self.assertEqual(ci.canonicalize_url('https://arxiv.org/pdf/2601.12345v2.pdf'), 'https://arxiv.org/abs/2601.12345')

    def test_candidate_identity_collects_only_explicit_urls(self):
        row = {'url':'https://x.test/a?utm_source=n', 'primaryUrl':'https://x.test/a', 'sourceDetails':{'official_url':'https://official.test/p','official_external_links':['https://docs.test/x']}}
        self.assertEqual(ci.candidate_identity_urls(row), {'https://x.test/a','https://official.test/p','https://docs.test/x'})

    def test_note_markdown_normalization_contract(self):
        value = nm.normalize_markdown_for_note('```md\n=== NOTE_DRAFT_START ===\n・ **「重要」**\n=== NOTE_DRAFT_END ===\n```')
        self.assertEqual(value, '- 「**重要**」')
        self.assertEqual(nm._normalize_note_title('「新機能」'), '新機能。')

    def test_subscription_tracking_is_fail_closed_and_idempotent(self):
        self.assertEqual(nm.build_subscription_tracking_url('x', enabled=False, default_landing_url='https://a.test', campaign_id='c'), '')
        url = nm.build_subscription_tracking_url('aif-1', 'https://a.test/lp?utm_source=old&keep=1', enabled=True, default_landing_url='', campaign_id='camp')
        self.assertIn('keep=1', url)
        self.assertIn('utm_source=note', url)
        self.assertEqual(url.count('utm_source='), 1)
        self.assertIn('aif_article_id=aif-1', url)

    def test_reader_first_summary_uses_callbacks_without_provider(self):
        def extract(text, aliases):
            return {'intro':'公式が新機能を公開しました。現場で何が変わる？', 'conclusion':'導入判断に影響します。', 'final':'まず小さく試します。'}.get(aliases[0], '')
        def aliases(key): return [key]
        def replace(text, mapping): return text, []
        parsed={'note_draft':'x','source_summary_text':'新機能が公開されました。','why_important_text':'運用コストの判断に影響します。','decision_text':'TRY'}
        out=nm.build_reader_first_summary(parsed, extract_section=extract, display_heading_aliases=aliases, replace_public_decision_code_leaks=replace)
        self.assertTrue(out['what'])
        self.assertIn('判断', out['why'])
        self.assertIn('試', out['decision'])

    def test_note_module_has_no_network_provider_or_persistence_imports(self):
        tree=ast.parse(inspect.getsource(nm))
        imports={n.names[0].name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) and n.names}
        imports |= {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertTrue({'requests','google','notion_client','github'}.isdisjoint(imports))

    def test_gate_reason_mapping_and_severity_boundaries(self):
        self.assertEqual(gr.reason_code('numeric mismatch', 'fact'), gr.REASON_CODE_FACT_NUMERICAL_MISMATCH)
        self.assertEqual(gr.classify_gate_reason_severity('fact','anything'), gr.GATE_SEVERITY_HARD)
        self.assertEqual(gr.classify_gate_reason_severity('human_appeal','headline_flattened'), gr.GATE_SEVERITY_SOFT)
        self.assertEqual(gr.classify_gate_reason_severity('human_appeal','ai_style_composite_high'), gr.GATE_SEVERITY_REVIEW)
        rows=gr.map_gate_reasons('publication',['headline_overclaim'])
        self.assertEqual(gr.gate_reason_disposition(rows), gr.GATE_DISPOSITION_BLOCK)

    def test_gate_candidate_record_preserves_evidence_fields(self):
        rec=gr.build_candidate_gate_record(1,'n','u',88,'generated',reason_codes=[{'reason_code':gr.REASON_CODE_PENDING_RETRY,'message':'p','gate':'operational'}], evidence_result={'state':'SUFFICIENT','documents_checked':2}, analyzed_at_now_iso=lambda:'NOW')
        self.assertEqual(rec['recorded_at'],'NOW')
        self.assertEqual(rec['evidence_sufficiency'],'SUFFICIENT')
        self.assertEqual(rec['evidence_documents_checked'],2)

    def test_screening_round_robin_and_profit_math(self):
        groups={'GitHub':[{'i':1},{'i':2}], 'ArXiv':[{'i':3}]}
        self.assertEqual([x['i'] for x in sp.round_robin_candidates(groups,3)],[1,3,2])
        self.assertEqual(sp.deep_dive_priority_score(80,60,neutral_score=50,decision_weight=.7,commercial_weight=.3),74.0)
        self.assertEqual(sp.shelf_life_label(70,neutral_score=50),'EVERGREEN')

    def test_screening_parser_salvages_and_preserves_missing_diagnostics(self):
        text='noise {"id":"a","score":70,"commercial_score":60,"shelf_life_score":80,"topic":"AGENT","tracking_eligible":true,"reason":"ok"} broken'
        parsed, missing, diag=sp.parse_batch_screening_response(text, {'a','b'}, True, tracking_eligibility_min_score=60, portfolio_topics={'MODEL','AGENT','DEVTOOLS','INFRA','DATA','SECURITY','MULTIMODAL','PRODUCT','OTHER'})
        self.assertEqual(parsed['a']['score'],70)
        self.assertEqual(missing,['b'])
        self.assertIn('json_decode_error',diag)

    def test_screening_module_has_no_model_call_site(self):
        source=inspect.getsource(sp)
        for token in ('google.genai','genai.Client','send_message(','requests.get(','requests.post('):
            self.assertNotIn(token, source)

    def test_source_roi_provider_failure_is_excluded_from_attempt_denominator(self):
        funnel=SimpleNamespace(records=[{'source':'GitHub','reason_codes':[{'reason_code':'MODEL_UNAVAILABLE'}],'generation_request_count':1,'final_status':'Pending Retry'}, {'source':'GitHub','reason_codes':[],'generation_request_count':2,'final_status':'Ready'}])
        out=sr.build_source_roi_run_metrics([], funnel, sources=('GitHub',), reason_code_model_unavailable='MODEL_UNAVAILABLE', reason_code_budget_exhausted='BUDGET', article_status_ready='Ready', article_status_needs_editorial_review='Review', content_status_quality_failed='Quality Failed', content_status_pending_retry='Pending Retry')
        self.assertEqual(out['GitHub']['deep_dive_attempted'],1)
        self.assertEqual(out['GitHub']['generation_requests'],2)
        self.assertEqual(out['GitHub']['ready'],1)

    def test_source_roi_learning_stays_off_until_maturity(self):
        state={'runs':[{'sources':{'GitHub':{'screened':100,'stock_saved':60,'deep_dive_attempted':5,'generation_requests':5,'ready':3}, 'ArXiv':{'screened':1,'stock_saved':1,'deep_dive_attempted':0,'generation_requests':0,'ready':0}}}]}
        profile=sr.compute_source_roi_profile(state,sources=('GitHub','ArXiv'),history_runs=10,recency_decay=.9,stock_weight=.4,ready_weight=.4,efficiency_weight=.2,min_screened=10,min_deep_dive_attempts=2,exploration_weight=.2,enable_learning=True,min_mature_sources=2)
        self.assertFalse(profile['GitHub']['learning_active'])

    def test_source_roi_allocator_returns_base_when_learning_inactive(self):
        base={'GitHub':50,'ArXiv':50}
        out=sr.allocate_source_fetch_limits({'GitHub':{'learning_active':False}},100,base=base,enable_learning=True,max_screening_candidates=100,max_fetch_by_source={'GitHub':80,'ArXiv':80},sources=('GitHub','ArXiv'),min_fetch_per_source=10)
        self.assertEqual(out,base)

    def test_all_run241_modules_are_stdlib_or_declared_local_only(self):
        for module in (ci,nm,gr,sp,sr):
            source=inspect.getsource(module).lower()
            self.assertNotIn('gemini_api_key',source)
            self.assertNotIn('notion_api_key',source)
            self.assertNotIn('requests.',source)


if __name__ == '__main__':
    unittest.main()
