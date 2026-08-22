import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault('GEMINI_API_KEY', 'test-key')
os.environ.setdefault('GH_PAT', 'test-token')
os.environ.setdefault('GEMINI_DEEP_DIVE_CALL_PACING_SECONDS', '0')

try:
    import requests  # noqa: F401
except ImportError:
    requests = types.ModuleType('requests')
    for name in ('get','post','put','patch','delete'):
        setattr(requests, name, lambda *args, **kwargs: None)
    sys.modules['requests'] = requests

try:
    from google import genai  # noqa: F401
except ImportError:
    google_mod = sys.modules.get('google') or types.ModuleType('google')
    genai_mod = types.ModuleType('google.genai')
    errors_mod = types.ModuleType('google.genai.errors')
    class APIError(Exception):
        pass
    class Client:
        def __init__(self, **_kwargs):
            self.chats = types.SimpleNamespace(create=lambda **_kw: None)
    genai_mod.Client = Client
    errors_mod.APIError = APIError
    google_mod.genai = genai_mod
    sys.modules.setdefault('google', google_mod)
    sys.modules['google.genai'] = genai_mod
    sys.modules['google.genai.errors'] = errors_mod

try:
    from PIL import Image as _PillowImage  # noqa: F401
except ImportError:
    pil_mod = types.ModuleType('PIL')
    image_mod = types.ModuleType('PIL.Image')
    draw_mod = types.ModuleType('PIL.ImageDraw')
    font_mod = types.ModuleType('PIL.ImageFont')
    class DummyImage:
        def convert(self,*_a): return self
        def resize(self,*_a): return self
        def crop(self,*_a): return self
        def save(self,*_a,**_k): pass
    image_mod.Image = DummyImage
    image_mod.Resampling = types.SimpleNamespace(LANCZOS=1)
    image_mod.new = lambda *_a,**_k: DummyImage()
    image_mod.open = lambda *_a,**_k: DummyImage()
    image_mod.alpha_composite = lambda image,_overlay: image
    draw_mod.Draw = lambda *_a,**_k: types.SimpleNamespace(line=lambda *_a,**_k:None, rounded_rectangle=lambda *_a,**_k:None, text=lambda *_a,**_k:None)
    font_mod.truetype = lambda *_a,**_k: object()
    font_mod.load_default = lambda: object()
    pil_mod.Image, pil_mod.ImageDraw, pil_mod.ImageFont = image_mod, draw_mod, font_mod
    sys.modules.update({'PIL':pil_mod,'PIL.Image':image_mod,'PIL.ImageDraw':draw_mod,'PIL.ImageFont':font_mod})

spec = importlib.util.spec_from_file_location('pipeline_adversarial_under_test', ROOT / 'pipeline.py')
pipeline = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(pipeline)


class TestEvidenceMetadataWordBoundaries(unittest.TestCase):
    def _info(self, text):
        return {
            'primary_source_resolved': True,
            'context': text,
            'source_details': {},
            'supplement_candidates': [],
            'checked_urls': set(),
            'evidence_documents': [{'url':'https://example.com','retrieved':True}],
            'evidence_metadata': pipeline._build_evidence_metadata(text, False),
        }

    def test_rapid_does_not_fake_api_method_evidence(self):
        md = pipeline._build_evidence_metadata('rapid deployment improves team workflow', False)
        self.assertNotEqual('FOUND', md['coverage']['method'])

    def test_capital_does_not_fake_api_method_evidence(self):
        md = pipeline._build_evidence_metadata('capital allocation remains uncertain', False)
        self.assertNotEqual('FOUND', md['coverage']['method'])

    def test_latest_does_not_fake_test_benchmark_evidence(self):
        md = pipeline._build_evidence_metadata('latest release announcement', False)
        self.assertNotEqual('FOUND', md['coverage']['benchmark'])

    def test_authorization_does_not_fake_actor_attribution(self):
        result = pipeline.assess_evidence_sufficiency(self._info('Method: token routing. authorization header required.'))
        self.assertFalse(result['checks']['actor_attribution_available'])

    def test_legacy_and_organic_do_not_fake_ga_current_state(self):
        for text in ('Method: legacy system migration.', 'Method: organic growth model.'):
            result = pipeline.assess_evidence_sufficiency(self._info(text))
            self.assertFalse(result['current_state_claim'], text)
            self.assertNotIn('freshness_status_available_if_time_sensitive', result['blocking_missing'], text)

    def test_real_ga_and_current_pricing_still_require_freshness(self):
        for text in ('Method: hosted API. GA release is available.', 'Method: hosted API. Current pricing is 20 USD.'):
            result = pipeline.assess_evidence_sufficiency(self._info(text))
            self.assertTrue(result['current_state_claim'], text)
            self.assertIn('freshness_status_available_if_time_sensitive', result['blocking_missing'], text)

    def test_stage_one_counts_as_method_evidence(self):
        md = pipeline._build_evidence_metadata('Stage 1 routes tokens to experts.', False)
        self.assertEqual('FOUND', md['coverage']['method'])

    def test_sec_abbreviation_counts_as_runtime_evidence(self):
        md = pipeline._build_evidence_metadata('The operation completes in 12 sec.', False)
        self.assertEqual('FOUND', md['coverage']['runtime'])


class TestNumericClaimAdversarial(unittest.TestCase):
    def test_multiplier_x_and_bai_are_equivalent(self):
        self.assertEqual([], pipeline._find_unsupported_numeric_claims('性能は3.4倍。', 'Benchmark shows 3.4x speedup.'))

    def test_multiplier_symbol_and_bai_are_equivalent(self):
        self.assertEqual([], pipeline._find_unsupported_numeric_claims('性能は2.7倍。', 'Benchmark shows 2.7× speedup.'))

    def test_fraction_bun_no_ichi_is_not_minutes(self):
        failures = pipeline._find_unsupported_numeric_claims('メモリ使用量は40分の1になった。', 'Memory use became 1/40 of baseline.')
        self.assertNotIn('unsupported numeric claim: 40分', failures)

    def test_same_percentage_wrong_metric_is_rejected(self):
        failures = pipeline._find_unsupported_numeric_claims('速度が20%向上した。', 'Memory usage decreased by 20%.')
        self.assertTrue(any('20%' in row for row in failures), failures)

    def test_same_multiplier_wrong_hardware_is_rejected(self):
        failures = pipeline._find_unsupported_numeric_claims('H100では1.8倍高速だった。', 'A100 benchmark: 1.8x speedup.')
        self.assertTrue(any('1.8' in row for row in failures), failures)

    def test_same_number_matching_metric_and_hardware_passes(self):
        failures = pipeline._find_unsupported_numeric_claims('A100では速度が1.8倍だった。', 'On A100, throughput speed was 1.8x baseline.')
        self.assertEqual([], failures)

    def test_same_percentage_wrong_dataset_is_rejected(self):
        failures = pipeline._find_unsupported_numeric_claims('Dataset Bでは精度が85%だった。', 'Dataset A accuracy was 85%.')
        self.assertTrue(any('85%' in row for row in failures), failures)

    def test_comma_separated_token_count_is_checked_as_full_number(self):
        self.assertEqual([], pipeline._find_unsupported_numeric_claims('上限は2,000トークン。', 'Limit is 2,000 tokens.'))
        failures = pipeline._find_unsupported_numeric_claims('上限は2,000トークン。', 'Limit is 1,500 tokens.')
        self.assertTrue(any('2,000' in row for row in failures), failures)

    def test_seconds_and_sec_are_equivalent(self):
        self.assertEqual([], pipeline._find_unsupported_numeric_claims('処理は10秒。', 'Runtime is 10 sec.'))

    def test_milliseconds_and_ms_are_equivalent(self):
        self.assertEqual([], pipeline._find_unsupported_numeric_claims('処理は10ミリ秒。', 'Runtime is 10 ms.'))


    def test_minutes_cross_language_equivalence(self):
        self.assertEqual([], pipeline._find_unsupported_numeric_claims('処理は40分。', 'Runtime is 40 minutes.'))

    def test_days_cross_language_equivalence(self):
        self.assertEqual([], pipeline._find_unsupported_numeric_claims('検証期間は7日。', 'Evaluation takes 7 days.'))

    def test_calendar_date_is_not_treated_as_duration_claim(self):
        failures = pipeline._find_unsupported_numeric_claims('公開日は2026年8月20日。', 'Published on August 20, 2026.')
        self.assertFalse(any('20日' in row for row in failures), failures)

    def test_coming_months_does_not_support_half_year_specificity(self):
        failures = pipeline._find_unsupported_numeric_claims(
            '今後数ヶ月から半年の間に仕様が進む。',
            'The working groups will continue this work over the coming months.',
        )
        self.assertFalse(any('数ヶ月' in row for row in failures), failures)
        self.assertTrue(any('半年' in row for row in failures), failures)

    def test_explicit_six_months_supports_half_year(self):
        failures = pipeline._find_unsupported_numeric_claims(
            '半年を目安に確認する。',
            'The evaluation period is six months.',
        )
        self.assertFalse(any('半年' in row for row in failures), failures)



class TestPrimarySourceResolution(unittest.TestCase):
    def test_github_url_without_retrieved_content_is_not_resolved(self):
        repo = {'source':'GitHub','nameWithOwner':'octo/example','url':'https://github.com/octo/example','description':'Method: routing algorithm.'}
        with patch.object(pipeline, 'fetch_github_readme_context', return_value=''), \
             patch.object(pipeline, '_fetch_html_document', return_value=('', [], repo['url'])):
            info = pipeline.prepare_source_context(repo)
        self.assertFalse(info['primary_source_resolved'])

    def test_github_readme_content_resolves_primary_source(self):
        repo = {'source':'GitHub','nameWithOwner':'octo/example','url':'https://github.com/octo/example','description':'desc'}
        with patch.object(pipeline, 'fetch_github_readme_context', return_value='Method: routing algorithm.'), \
             patch.object(pipeline, '_fetch_html_document', return_value=('', [], repo['url'])):
            info = pipeline.prepare_source_context(repo)
        self.assertTrue(info['primary_source_resolved'])

    def test_hn_external_article_failure_does_not_treat_hn_comment_as_primary(self):
        repo = {
            'source':'HackerNews','nameWithOwner':'Launch HN','url':'https://news.ycombinator.com/item?id=1',
            'primaryUrl':'https://example.com/article','sourceContext':'submitter comment',
            'sourceDetails':{'external_url':'https://example.com/article','hn_url':'https://news.ycombinator.com/item?id=1'},
        }
        with patch.object(pipeline, 'fetch_webpage_context', return_value=''), \
             patch.object(pipeline, '_fetch_html_document', return_value=('', [], repo['primaryUrl'])):
            info = pipeline.prepare_source_context(repo)
        self.assertFalse(info['primary_source_resolved'])

    def test_hn_self_post_text_can_be_primary(self):
        repo = {
            'source':'HackerNews','nameWithOwner':'Ask HN','url':'https://news.ycombinator.com/item?id=1',
            'primaryUrl':'https://news.ycombinator.com/item?id=1','sourceContext':'Method: detailed self-post implementation notes.',
            'sourceDetails':{'hn_url':'https://news.ycombinator.com/item?id=1'},
        }
        with patch.object(pipeline, '_fetch_html_document', return_value=('', [], repo['primaryUrl'])):
            info = pipeline.prepare_source_context(repo)
        self.assertTrue(info['primary_source_resolved'])


class TestCanonicalizationAdversarial(unittest.TestCase):
    def test_scheme_and_host_case_are_normalized(self):
        self.assertEqual(
            pipeline.canonicalize_url('HTTPS://Example.COM/Product/'),
            pipeline.canonicalize_url('https://example.com/Product'),
        )

    def test_query_order_does_not_create_duplicate_identity(self):
        self.assertEqual(
            pipeline.canonicalize_url('https://example.com/p?a=1&b=2'),
            pipeline.canonicalize_url('https://example.com/p?b=2&a=1'),
        )

    def test_default_https_port_is_normalized(self):
        self.assertEqual(
            pipeline.canonicalize_url('https://example.com:443/p'),
            pipeline.canonicalize_url('https://example.com/p'),
        )

    def test_meaningful_query_value_difference_is_preserved(self):
        self.assertNotEqual(
            pipeline.canonicalize_url('https://example.com/p?id=1'),
            pipeline.canonicalize_url('https://example.com/p?id=2'),
        )

    def test_arxiv_versions_and_pdf_abs_forms_are_same_identity(self):
        values = {
            pipeline.canonicalize_url('http://www.arxiv.org/abs/2608.19140v1'),
            pipeline.canonicalize_url('https://arxiv.org/abs/2608.19140v2'),
            pipeline.canonicalize_url('https://arxiv.org/pdf/2608.19140.pdf'),
        }
        self.assertEqual({'https://arxiv.org/abs/2608.19140'}, values)


class TestFailureIsolationAndLimits(unittest.TestCase):
    def test_failed_supplement_does_not_claim_deep_scan_success(self):
        info = {
            'context':'Method: routing algorithm.',
            'supplement_candidates':[{'url':'https://example.com/a','role':'PRIMARY_SOURCE','source_type':'official_docs'}],
            'checked_urls':set(), 'evidence_documents':[{'url':'https://example.com','retrieved':True}],
            'deep_source_urls':[], 'evidence_supplement_attempts':0,
        }
        with patch.object(pipeline, 'fetch_webpage_context', return_value=''):
            pipeline.supplement_source_evidence(info)
        self.assertFalse(info.get('deep_source_scanned', False))
        self.assertEqual([], info['deep_source_urls'])

    def test_document_limit_never_exceeds_configured_cap(self):
        info = {
            'context':'Method: routing algorithm.',
            'supplement_candidates':[{'url':f'https://example.com/{i}','role':'PRIMARY_SOURCE','source_type':'official_docs'} for i in range(10)],
            'checked_urls':set(), 'evidence_documents':[{'url':'https://example.com','retrieved':True}],
            'deep_source_urls':[], 'evidence_supplement_attempts':0,
        }
        with patch.object(pipeline, 'fetch_webpage_context', return_value='Limitation: test scope only. Benchmark: 10 ms.'):
            pipeline.supplement_source_evidence(info)
        self.assertLessEqual(len(info['evidence_documents']), pipeline.MAX_EVIDENCE_DOCUMENTS)
        self.assertLessEqual(info['evidence_supplement_attempts'], pipeline.MAX_EVIDENCE_SUPPLEMENT_ATTEMPTS)



class TestActorAttributionAdversarial(unittest.TestCase):
    def test_wrong_announcing_company_is_rejected(self):
        failures = pipeline._find_source_boundary_violations(
            'OpenAIがこの手法を発表した。',
            'Anthropic authors present the method.'
        )
        self.assertTrue(any('OpenAI' in row for row in failures), failures)

    def test_wrong_developing_company_is_rejected(self):
        failures = pipeline._find_source_boundary_violations(
            'OpenAIがこの手法を開発した。',
            'Anthropic authors present the method.'
        )
        self.assertTrue(any('OpenAI' in row for row in failures), failures)

    def test_supported_company_attribution_passes(self):
        failures = pipeline._find_source_boundary_violations(
            'Anthropicがこの手法を発表した。',
            'Anthropic authors present the method.'
        )
        self.assertEqual([], failures)


class _RedirectResponse:
    def __init__(self, status_code, url, headers=None, chunks=None):
        self.status_code = status_code
        self.url = url
        self.headers = headers or {}
        self._chunks = chunks or []
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def iter_content(self, chunk_size=32768):
        yield from self._chunks




class TestMonthlyDigestReviewIsolation(unittest.TestCase):
    def test_needs_editorial_review_is_not_listed_as_completed_deep_dive(self):
        items = [
            {"name":"Ready article","url":"https://example.com/ready","source":"ArXiv","status":pipeline.STATUS_DEEP_DIVE,"article_status":pipeline.ARTICLE_STATUS_READY,"score":90},
            {"name":"Review article","url":"https://example.com/review","source":"ArXiv","status":pipeline.STATUS_DEEP_DIVE,"article_status":pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW,"score":88},
        ]
        import datetime as dt
        markdown = pipeline.build_monthly_digest_markdown(dt.date(2026, 8, 31), items)
        deep_section = markdown.split("## Deep Dive記事一覧", 1)[1].split("## ストックのみ案件", 1)[0]
        stock_section = markdown.split("## ストックのみ案件", 1)[1]
        self.assertIn("Ready article", deep_section)
        self.assertNotIn("Review article", deep_section)
        self.assertIn("Review article", stock_section)

class TestPublicSyncDefenseInDepth(unittest.TestCase):
    def test_public_sync_requires_both_public_approved_and_ready(self):
        source_response = MagicMock()
        source_response.raise_for_status.return_value = None
        source_response.json.return_value = {"results": [], "has_more": False}
        with patch.object(pipeline, "NOTION_API_KEY", "test-key"), \
             patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "internal-ds"), \
             patch.object(pipeline, "NOTION_DATABASE_ID", None), \
             patch.object(pipeline, "NOTION_PUBLIC_DATA_SOURCE_ID", "public-ds"), \
             patch.object(pipeline, "NOTION_PUBLIC_DATABASE_ID", None), \
             patch.object(pipeline.requests, "post", return_value=source_response) as mock_post:
            # source resultsが0件なのでdestination schemaまでは到達する仕様だが、query payloadの確認が目的。
            schema = MagicMock(); schema.raise_for_status.return_value = None; schema.json.return_value = {"properties": {pipeline.PROP_URL: {"type": "url"}}}
            with patch.object(pipeline.requests, "get", return_value=schema):
                pipeline.sync_public_approved_to_member_db()
        payload = mock_post.call_args_list[0].kwargs["json"]
        filters = payload["filter"]["and"]
        self.assertIn({"property": pipeline.PROP_REVIEW_STATUS, "status": {"equals": pipeline.REVIEW_STATUS_PUBLIC_APPROVED}}, filters)
        self.assertIn({"property": pipeline.PROP_ARTICLE_STATUS, "select": {"equals": pipeline.ARTICLE_STATUS_READY}}, filters)

class TestRedirectSsrfAdversarial(unittest.TestCase):
    def test_redirect_to_private_destination_is_blocked_before_second_request(self):
        public = 'https://public.example/source'
        private = 'http://127.0.0.1/admin'
        first = _RedirectResponse(302, public, {'Location': private})
        with patch.object(pipeline, '_validate_public_http_url', side_effect=lambda u: (_ for _ in ()).throw(ValueError('private destination blocked')) if u == private else None), \
             patch.object(pipeline.requests, 'get', return_value=first) as mock_get:
            body, content_type, final = pipeline._http_get_limited(public, ('text/html',), 1024)
        self.assertEqual(b'', body)
        self.assertEqual(1, mock_get.call_count)
        self.assertEqual('', final)

    def test_safe_redirect_is_followed_with_validation_each_hop(self):
        first_url = 'https://public.example/source'
        second_url = 'https://docs.example/final'
        responses = [
            _RedirectResponse(302, first_url, {'Location': second_url}),
            _RedirectResponse(200, second_url, {'Content-Type': 'text/html'}, [b'hello']),
        ]
        validated = []
        with patch.object(pipeline, '_validate_public_http_url', side_effect=lambda u: validated.append(u)), \
             patch.object(pipeline.requests, 'get', side_effect=responses):
            body, content_type, final = pipeline._http_get_limited(first_url, ('text/html',), 1024)
        self.assertEqual(b'hello', body)
        self.assertEqual('https://docs.example/final', final)
        self.assertIn(second_url, validated)


class TestCrossSourceIdentityDedupe(unittest.TestCase):
    def test_hn_external_and_github_repo_share_identity(self):
        github = {
            "source": "GitHub", "url": "https://github.com/acme/tool",
            "primaryUrl": "https://github.com/acme/tool", "sourceDetails": {},
        }
        hn = {
            "source": "HackerNews", "url": "https://news.ycombinator.com/item?id=9",
            "primaryUrl": "https://github.com/acme/tool",
            "sourceDetails": {"hn_url": "https://news.ycombinator.com/item?id=9", "external_url": "https://github.com/acme/tool"},
        }
        self.assertTrue(pipeline.candidate_identity_urls(github) & pipeline.candidate_identity_urls(hn))

    def test_producthunt_tracking_url_and_official_site_share_identity(self):
        ph = {
            "source": "ProductHunt", "url": "https://vendor.example/product?utm_source=ph",
            "primaryUrl": "https://vendor.example/product?utm_source=ph",
            "sourceDetails": {"official_url": "https://vendor.example/product"},
        }
        direct = {"source": "HackerNews", "url": "https://vendor.example/product", "primaryUrl": "https://vendor.example/product", "sourceDetails": {}}
        self.assertTrue(pipeline.candidate_identity_urls(ph) & pipeline.candidate_identity_urls(direct))

    def test_similar_titles_without_shared_url_are_not_semantically_collapsed(self):
        a = {"source":"ArXiv", "url":"https://arxiv.org/abs/2608.10001", "primaryUrl":"https://arxiv.org/abs/2608.10001", "sourceDetails":{}}
        b = {"source":"ArXiv", "url":"https://arxiv.org/abs/2608.10002", "primaryUrl":"https://arxiv.org/abs/2608.10002", "sourceDetails":{}}
        self.assertFalse(pipeline.candidate_identity_urls(a) & pipeline.candidate_identity_urls(b))


class TestBudgetExhaustionAdversarial(unittest.TestCase):
    def test_deep_dive_model_budget_never_exceeds_cap(self):
        budget = pipeline.DeepDiveModelBudget(2)
        budget.consume("deep_dive")
        budget.consume("quality_retry")
        with self.assertRaises(pipeline.GeminiBudgetExceededError):
            budget.consume("deep_dive")
        self.assertEqual(2, budget.used)

    def test_transport_retry_budget_is_globally_bounded(self):
        budget = pipeline.GeminiBudget(50, 4, 1)
        budget.consume("deep_dive_retry")
        with self.assertRaises(pipeline.GeminiBudgetExceededError):
            budget.consume("deep_dive_retry")
        self.assertEqual(1, budget.deep_dive_retry_count)

    def test_local_budget_reserve_blocks_request_before_reserved_capacity(self):
        budget = pipeline.GeminiBudget(5, 1, 1)
        budget.request_count = 3
        self.assertFalse(budget.can_request(reserve=2))
        self.assertTrue(budget.can_request(reserve=1))


class TestRetryDegradationAdversarial(unittest.TestCase):
    def test_material_action_collapse_after_retry_is_detected(self):
        before = {
            "title_text":"導入判断。",
            "action_text":"CIで2構成を比較し、回帰テストを追加する。",
            "decision_text":"TRY",
            "note_draft":"## 筆者ならどうするか\nCIで2構成を比較し、回帰テストを追加する。",
        }
        after = {
            "title_text":"動向を確認。",
            "action_text":"今後の動向を注視する。",
            "decision_text":"WATCH",
            "note_draft":"## 筆者ならどうするか\n今後の動向を注視する。",
        }
        self.assertTrue(pipeline.human_appeal_materially_degraded(before, after))

    def test_retry_diagnostics_preserve_trigger_and_final_reasons_separately(self):
        initial = [{"reason_code": pipeline.REASON_CODE_FACT_NUMERICAL_MISMATCH, "message": "numeric"}]
        details = {"retry_attempted": True, "trigger_reason_codes": initial, "original_article": "first"}
        final = [{"reason_code": pipeline.REASON_CODE_APPEAL_DECISION_VOICE_LOSS, "message": "voice"}]
        result = pipeline.finalize_retry_diagnostics(details, final, "NEEDS_EDITORIAL_REVIEW", "retry")
        self.assertEqual(initial, result["trigger_reason_codes"])
        self.assertEqual(final, result["final_reason_codes"])
        self.assertFalse(result["retry_succeeded"])



class TestStateTransitionCombinationAdversarial(unittest.TestCase):
    def _repo(self):
        return {
            "nameWithOwner": "octo/fact-review",
            "url": "https://github.com/octo/fact-review",
            "source": "GitHub",
            "stargazerCount": 10,
            "publishedAt": "2026-08-01T00:00:00Z",
            "description": "desc",
            "licenseInfo": {"spdxId": "MIT"},
        }

    def test_fact_fail_plus_publication_review_becomes_quality_failed_not_editorial_review(self):
        parsed = {
            "note_draft": "本文", "title_text": "タイトル", "score": 80,
            "score_breakdown_text": "内訳", "source_summary_text": "概要",
            "what_text": "what", "why_important_text": "why", "paradigm_shift_text": "p",
            "alternative_comparison_text": "a", "migration_cost_text": "m",
            "decision_text": "TRY", "decision_reason_text": "dr", "why_not_important_text": "wn",
            "who_should_use_text": "wu", "who_should_not_use_text": "wnu", "action_text": "action",
            "future_scenario_text": "fs", "article_value": 50,
            "grounding_status": pipeline.GROUNDING_SOURCE_NATIVE, "evidence_urls_text": "",
        }
        response = MagicMock(); response.text = "dummy"
        pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "NOTION_API_KEY", "k"), \
             patch.object(pipeline, "legal_safety_gate", return_value=(True, "MIT")), \
             patch.object(pipeline, "prepare_source_context", return_value={
                 "primary_source_resolved": True, "primary_url": self._repo()["url"],
                 "context": "method implementation limitation author", "method": pipeline.GROUNDING_SOURCE_NATIVE,
                 "source": "GitHub", "deep_source_scanned": False,
             }), \
             patch.object(pipeline, "resolve_followup_freshness", return_value={"triggered": False, "followup_found": False, "context": ""}), \
             patch.object(pipeline, "assess_evidence_sufficiency", return_value={
                 "state": pipeline.EVIDENCE_SUFFICIENT, "initial_state": pipeline.EVIDENCE_SUFFICIENT,
                 "core_missing": [], "blocking_missing": [], "decision_scope_safe": True,
                 "action_risk_tier": "LOW", "supplement_attempted": False, "supplement_success": False,
             }), \
             patch.object(pipeline, "classify_action_risk_tier", return_value="LOW"), \
             patch.object(pipeline, "call_gemini_grounded_deep_dive", return_value=(response, {"grounding_status": pipeline.GROUNDING_SOURCE_NATIVE, "evidence_urls": []})), \
             patch.object(pipeline, "_response_was_truncated", return_value=False), \
             patch.object(pipeline, "_parse_gemini_response", return_value=parsed), \
             patch.object(pipeline, "validate_fact_gate", return_value=(False, ["unsupported claim"])), \
             patch.object(pipeline, "validate_editorial_gate", return_value=(True, [])), \
             patch.object(pipeline, "validate_publication_readiness_gate", return_value=("REVIEW", ["primary_evidence_insufficient"])), \
             patch.object(pipeline, "validate_human_appeal_gate", return_value=("ACCEPTABLE", [])), \
             patch.object(pipeline, "update_notion_quality_failed") as mock_qf, \
             patch.object(pipeline, "persist_notion_needs_editorial_review") as mock_review, \
             patch.object(pipeline, "save_quality_failed_article", return_value="path"), \
             patch.object(pipeline, "send_telegram_alert"):
            result = pipeline.generate_intelligence_report(
                self._repo(), notion_page_id="page-1", screening_score=80, screening_reason="r"
            )
        self.assertIsNone(result)
        mock_qf.assert_called_once()
        mock_review.assert_not_called()
        statuses = [r.get("final_status") for r in pipeline.DEEP_DIVE_GATE_FUNNEL.records]
        self.assertIn(pipeline.CONTENT_STATUS_QUALITY_FAILED, statuses)
        self.assertNotIn(pipeline.ARTICLE_STATUS_NEEDS_EDITORIAL_REVIEW, statuses)

    def test_publication_fail_does_not_falsely_mark_fact_gate_failed(self):
        parsed = {
            "note_draft": "本文", "title_text": "タイトル", "score": 80,
            "score_breakdown_text": "内訳", "source_summary_text": "概要",
            "what_text": "what", "why_important_text": "why", "paradigm_shift_text": "p",
            "alternative_comparison_text": "a", "migration_cost_text": "m",
            "decision_text": "TRY", "decision_reason_text": "dr", "why_not_important_text": "wn",
            "who_should_use_text": "wu", "who_should_not_use_text": "wnu", "action_text": "action",
            "future_scenario_text": "fs", "article_value": 50,
            "grounding_status": pipeline.GROUNDING_SOURCE_NATIVE, "evidence_urls_text": "",
        }
        response = MagicMock(); response.text = "dummy"
        pipeline.reset_deep_dive_gate_funnel()
        with patch.object(pipeline, "NOTION_API_KEY", "k"), \
             patch.object(pipeline, "legal_safety_gate", return_value=(True, "MIT")), \
             patch.object(pipeline, "prepare_source_context", return_value={
                 "primary_source_resolved": True, "primary_url": self._repo()["url"],
                 "context": "method implementation limitation author", "method": pipeline.GROUNDING_SOURCE_NATIVE,
                 "source": "GitHub", "deep_source_scanned": False,
             }), \
             patch.object(pipeline, "resolve_followup_freshness", return_value={"triggered": False, "followup_found": False, "context": ""}), \
             patch.object(pipeline, "assess_evidence_sufficiency", return_value={
                 "state": pipeline.EVIDENCE_SUFFICIENT, "initial_state": pipeline.EVIDENCE_SUFFICIENT,
                 "core_missing": [], "blocking_missing": [], "decision_scope_safe": True,
                 "action_risk_tier": "LOW", "supplement_attempted": False, "supplement_success": False,
             }), \
             patch.object(pipeline, "classify_action_risk_tier", return_value="LOW"), \
             patch.object(pipeline, "call_gemini_grounded_deep_dive", return_value=(response, {"grounding_status": pipeline.GROUNDING_SOURCE_NATIVE, "evidence_urls": []})), \
             patch.object(pipeline, "_response_was_truncated", return_value=False), \
             patch.object(pipeline, "_parse_gemini_response", return_value=parsed), \
             patch.object(pipeline, "validate_fact_gate", return_value=(True, [])), \
             patch.object(pipeline, "validate_editorial_gate", return_value=(True, [])), \
             patch.object(pipeline, "validate_publication_readiness_gate", return_value=("FAIL", ["research_to_production_leap"])), \
             patch.object(pipeline, "validate_human_appeal_gate", return_value=("ACCEPTABLE", [])), \
             patch.object(pipeline, "update_notion_quality_failed"), \
             patch.object(pipeline, "save_quality_failed_article", return_value="path"), \
             patch.object(pipeline, "send_telegram_alert"):
            pipeline.generate_intelligence_report(
                self._repo(), notion_page_id="page-1", screening_score=80, screening_reason="r"
            )
        record = pipeline.DEEP_DIVE_GATE_FUNNEL.records[-1]
        self.assertEqual(pipeline.GATE_STATUS_PASS, record["fact_gate"])
        self.assertEqual(pipeline.GATE_STATUS_FAIL, record["publication_readiness_gate"])
        self.assertEqual(pipeline.CONTENT_STATUS_QUALITY_FAILED, record["final_status"])


class TestPendingRetryFairness(unittest.TestCase):
    def test_oldest_last_edited_pending_retry_is_requested_first(self):
        captured = {}
        response = MagicMock(); response.json.return_value = {"results": []}
        def fake_query(_u, _h, payload):
            captured["payload"] = payload
            return response
        with patch.object(pipeline, "NOTION_API_KEY", "k"), \
             patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "ds"), \
             patch.object(pipeline, "_query_notion_db_with_retry", side_effect=fake_query):
            pipeline.get_pending_retry_items(limit=3)
        self.assertEqual(
            captured["payload"]["sorts"],
            [{"timestamp": "last_edited_time", "direction": "ascending"}],
        )


class TestGeminiReservationOrdering(unittest.TestCase):
    def test_local_budget_failure_does_not_reserve_persistent_counter(self):
        budget = pipeline.GeminiBudget(0, 0, 0)
        persistent = MagicMock()
        with patch.object(pipeline, "GEMINI_BUDGET", budget), \
             patch.object(pipeline, "PERSISTENT_GEMINI_COUNTER", persistent):
            with self.assertRaises(pipeline.GeminiBudgetExceededError):
                pipeline._consume_gemini_request("screening_batch", model_name="m")
        persistent.reserve.assert_not_called()


class TestProductHuntDailyFreshness(unittest.TestCase):
    def test_producthunt_uses_recent_window_and_newest_order(self):
        captured = {}
        response = MagicMock(); response.status_code = 200
        response.json.return_value = {"data": {"posts": {"edges": []}}}
        def fake_post(url, json=None, headers=None, timeout=None):
            captured.update(json)
            return response
        with patch.object(pipeline, "PRODUCTHUNT_DEVELOPER_TOKEN", "token"), \
             patch.object(pipeline.requests, "post", side_effect=fake_post):
            pipeline.fetch_producthunt_trending(20)
        self.assertIn("order: NEWEST", captured["query"])
        self.assertIn("postedAfter: $postedAfter", captured["query"])
        self.assertTrue(captured["variables"]["postedAfter"].endswith("Z"))


class TestMonthlyDigestPrivacy(unittest.TestCase):
    def test_public_github_digest_upload_is_hard_disabled(self):
        with patch.object(pipeline, "logger") as log:
            result = pipeline.upload_digest_to_github("/tmp/digest.md", "digest.md")
        self.assertIsNone(result)
        log.warning.assert_called_once()


class TestNotionPreflight(unittest.TestCase):
    def _schema(self):
        return {name: {"type": typ} for name, typ in pipeline.NOTION_REQUIRED_PROPERTY_TYPES.items()}

    def test_preflight_passes_with_complete_schema(self):
        response = MagicMock(); response.raise_for_status.return_value = None
        response.json.return_value = {"properties": self._schema()}
        with patch.object(pipeline, "NOTION_API_KEY", "k"), \
             patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "ds"), \
             patch.object(pipeline.requests, "get", return_value=response):
            pipeline.preflight_notion_schema()

    def test_preflight_fails_before_gemini_when_required_property_is_missing(self):
        schema = self._schema(); schema.pop(pipeline.PROP_URL)
        response = MagicMock(); response.raise_for_status.return_value = None
        response.json.return_value = {"properties": schema}
        with patch.object(pipeline, "NOTION_API_KEY", "k"), \
             patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "ds"), \
             patch.object(pipeline.requests, "get", return_value=response):
            with self.assertRaises(ValueError):
                pipeline.preflight_notion_schema()


class TestPublicSyncRevocation(unittest.TestCase):
    def test_internal_record_no_longer_eligible_archives_existing_member_copy(self):
        internal = {
            "id": "internal-1",
            "properties": {pipeline.PROP_URL: {"url": "https://example.com/item"}},
        }
        public = {
            "id": "public-1",
            "properties": {pipeline.PROP_URL: {"url": "https://example.com/item"}},
        }
        responses = []
        for body in (
            {"results": [], "has_more": False},          # eligible
            {"results": [internal], "has_more": False}, # all internal
            {"results": [public], "has_more": False},   # all public
        ):
            r = MagicMock(); r.raise_for_status.return_value = None; r.json.return_value = body; responses.append(r)
        schema = MagicMock(); schema.raise_for_status.return_value = None
        schema.json.return_value = {"properties": {pipeline.PROP_URL: {"type": "url"}}}
        patch_response = MagicMock(); patch_response.raise_for_status.return_value = None
        with patch.object(pipeline, "NOTION_API_KEY", "k"), \
             patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "internal-ds"), \
             patch.object(pipeline, "NOTION_PUBLIC_DATA_SOURCE_ID", "public-ds"), \
             patch.object(pipeline.requests, "post", side_effect=responses), \
             patch.object(pipeline.requests, "get", return_value=schema), \
             patch.object(pipeline.requests, "patch", return_value=patch_response) as mock_patch:
            pipeline.sync_public_approved_to_member_db()
        self.assertTrue(any(call.kwargs.get("json") == {"archived": True} for call in mock_patch.call_args_list))


class TestProductHuntMandatoryPreflight(unittest.TestCase):
    def test_normal_runtime_requires_producthunt_token_before_notion_preflight(self):
        with patch.object(pipeline, "PUBLIC_DB_SYNC_MODE", False), \
             patch.object(pipeline, "SYNTHETIC_REGRESSION_MODE", False), \
             patch.object(pipeline, "REGEN_TEST_MODE", False), \
             patch.object(pipeline, "GEMINI_API_KEY", "g"), \
             patch.object(pipeline, "GH_PAT", "gh"), \
             patch.object(pipeline, "PRODUCTHUNT_DEVELOPER_TOKEN", None), \
             patch.object(pipeline, "SCREENING_MODEL_POOL", ["s"]), \
             patch.object(pipeline, "DEEP_DIVE_MODEL_POOL", ["d"]), \
             patch.object(pipeline, "preflight_notion_schema") as preflight:
            with self.assertRaises(ValueError):
                pipeline.initialize_runtime()
        preflight.assert_not_called()


    def test_normal_runtime_falls_back_when_quota_project_id_is_not_injected(self):
        with patch.object(pipeline, "PUBLIC_DB_SYNC_MODE", False), \
             patch.object(pipeline, "SYNTHETIC_REGRESSION_MODE", False), \
             patch.object(pipeline, "REGEN_TEST_MODE", False), \
             patch.object(pipeline, "GEMINI_API_KEY", "g"), \
             patch.object(pipeline, "GH_PAT", "gh"), \
             patch.object(pipeline, "PRODUCTHUNT_DEVELOPER_TOKEN", "ph"), \
             patch.object(pipeline, "GEMINI_PERSISTENT_DAILY_COUNTER", True), \
             patch.object(pipeline, "GEMINI_QUOTA_PROJECT_ID", ""), \
             patch.object(pipeline, "GEMINI_COUNTER_SCOPE_ID", "owner/repo"), \
             patch.object(pipeline, "SCREENING_MODEL_POOL", ["s"]), \
             patch.object(pipeline, "DEEP_DIVE_MODEL_POOL", ["d"]), \
             patch.object(pipeline, "_register_gemini_usage_atexit"), \
             patch.object(pipeline, "preflight_notion_schema") as preflight:
            pipeline.initialize_runtime()
        preflight.assert_called_once()

    def test_normal_runtime_fails_only_when_no_stable_counter_scope_exists(self):
        with patch.object(pipeline, "PUBLIC_DB_SYNC_MODE", False), \
             patch.object(pipeline, "SYNTHETIC_REGRESSION_MODE", False), \
             patch.object(pipeline, "REGEN_TEST_MODE", False), \
             patch.object(pipeline, "GEMINI_API_KEY", "g"), \
             patch.object(pipeline, "GH_PAT", "gh"), \
             patch.object(pipeline, "PRODUCTHUNT_DEVELOPER_TOKEN", "ph"), \
             patch.object(pipeline, "GEMINI_PERSISTENT_DAILY_COUNTER", True), \
             patch.object(pipeline, "GEMINI_QUOTA_PROJECT_ID", ""), \
             patch.object(pipeline, "GEMINI_COUNTER_SCOPE_ID", ""), \
             patch.object(pipeline, "SCREENING_MODEL_POOL", ["s"]), \
             patch.object(pipeline, "DEEP_DIVE_MODEL_POOL", ["d"]), \
             patch.object(pipeline, "preflight_notion_schema") as preflight:
            with self.assertRaises(ValueError) as ctx:
                pipeline.initialize_runtime()
        self.assertIn("安定scope", str(ctx.exception))
        preflight.assert_not_called()


class TestGeminiUsageAudit(unittest.TestCase):
    def test_usage_audit_aggregates_model_kind_context_and_outcome(self):
        audit = pipeline.GeminiUsageAudit()
        a = audit.record_attempt("gemini-3.5-flash-lite", "screening_batch", "B0001-B0025")
        b = audit.record_attempt("gemini-3.6-flash", "deep_dive", "GitHub:owner/repo")
        audit.record_outcome(a, "success")
        audit.record_response_usage(
            a, types.SimpleNamespace(usage_metadata=types.SimpleNamespace(
                prompt_token_count=120, candidates_token_count=30, total_token_count=150
            ))
        )
        audit.record_outcome(b, "error", RuntimeError("boom"))
        agg = audit.aggregate()
        self.assertEqual(2, agg["attempts"])
        self.assertEqual(1, agg["success"])
        self.assertEqual(1, agg["error"])
        self.assertEqual(150, agg["total_tokens"])
        self.assertEqual(120, agg["prompt_tokens"])
        self.assertEqual(30, agg["output_tokens"])
        self.assertEqual(150, agg["by_model"]["gemini-3.5-flash-lite"]["total_tokens"])
        self.assertEqual(1, agg["by_model"]["gemini-3.5-flash-lite"]["by_kind"]["screening_batch"])
        self.assertEqual(1, agg["by_model"]["gemini-3.6-flash"]["by_kind"]["deep_dive"])
        self.assertEqual(1, agg["by_context"]["GitHub:owner/repo"])

    def test_consume_records_attempt_only_after_persistent_reservation_succeeds(self):
        budget = pipeline.GeminiBudget(5, 2, 1)
        persistent = MagicMock()
        audit = pipeline.GeminiUsageAudit()
        with patch.object(pipeline, "GEMINI_BUDGET", budget), \
             patch.object(pipeline, "PERSISTENT_GEMINI_COUNTER", persistent), \
             patch.object(pipeline, "GEMINI_USAGE_AUDIT", audit):
            record_id = pipeline._consume_gemini_request(
                "screening_batch", model_name="m", request_context="batch-1"
            )
        persistent.reserve.assert_called_once_with("screening_batch", reserve=0, model_name="m")
        self.assertEqual(0, record_id)
        self.assertEqual("batch-1", audit.records[0]["context"])

    def test_generate_wrapper_marks_failed_api_attempt(self):
        audit = pipeline.GeminiUsageAudit()
        fake_chat = MagicMock()
        fake_chat.send_message.side_effect = RuntimeError("transport")
        fake_client = MagicMock()
        fake_client.chats.create.return_value = fake_chat
        with patch.object(pipeline, "client", fake_client), \
             patch.object(pipeline, "GEMINI_USAGE_AUDIT", audit), \
             patch.object(pipeline, "_consume_gemini_request", side_effect=lambda kind, reserve=0, model_name="default", request_context="", **kwargs: audit.record_attempt(model_name, kind, request_context)):
            with self.assertRaises(RuntimeError):
                pipeline._generate_via_chat(
                    "m", "secret prompt body", request_kind="deep_dive", request_context="GitHub:owner/repo"
                )
        self.assertEqual("error", audit.records[0]["outcome"])
        self.assertEqual("RuntimeError", audit.records[0]["error_type"])
        self.assertNotIn("secret prompt body", str(audit.records))


class TestFreshnessSemanticRelevance(unittest.TestCase):
    def test_unrelated_same_domain_update_page_does_not_resolve_freshness(self):
        html = b'<html><a href="/blog/general-update">Update</a></html>'
        source_info = {
            "context": "A future version is planned.",
            "primary_url": "https://vendor.example/acme-quantum-engine",
            "source_name": "Acme Quantum Engine",
        }
        with patch.object(
            pipeline, "_http_get_limited",
            return_value=(html, "text/html", "https://vendor.example/acme-quantum-engine"),
        ), patch.object(
            pipeline, "fetch_webpage_context",
            return_value="General company update about office opening and hiring.",
        ):
            result = pipeline.resolve_followup_freshness(source_info)
        self.assertTrue(result["triggered"])
        self.assertFalse(result["followup_found"])


class TestPersistenceFunnelClassification(unittest.TestCase):
    def test_pending_retry_with_persistence_reason_counts_both_recovery_and_persistence_failure(self):
        funnel = pipeline.DeepDiveGateFunnel()
        funnel.record({
            "candidate_origin": "new",
            "generation_status": "pending_retry",
            "final_status": pipeline.CONTENT_STATUS_PENDING_RETRY,
            "reason_codes": [{"reason_code": pipeline.REASON_CODE_NOTION_PERSISTENCE_FAILED, "message": "x"}],
            "fact_gate": pipeline.GATE_STATUS_PASS,
            "editorial_gate": pipeline.GATE_STATUS_PASS,
            "publication_readiness_gate": pipeline.GATE_STATUS_REVIEW,
            "human_appeal_gate": pipeline.GATE_STATUS_PASS,
        })
        self.assertEqual(1, funnel.counters["pending_retry"])
        self.assertEqual(1, funnel.counters["notion_persistence_failed"])


class TestPublicSyncManualRecordSafety(unittest.TestCase):
    def test_member_record_without_internal_source_counterpart_is_not_archived(self):
        public = {"id": "manual-public", "properties": {pipeline.PROP_URL: {"url": "https://manual.example/item"}}}
        responses = []
        for body in (
            {"results": [], "has_more": False},  # eligible
            {"results": [], "has_more": False},  # internal all
            {"results": [public], "has_more": False},  # public all
        ):
            r = MagicMock(); r.raise_for_status.return_value = None; r.json.return_value = body; responses.append(r)
        schema = MagicMock(); schema.raise_for_status.return_value = None
        schema.json.return_value = {"properties": {pipeline.PROP_URL: {"type": "url"}}}
        with patch.object(pipeline, "NOTION_API_KEY", "k"), \
             patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "internal-ds"), \
             patch.object(pipeline, "NOTION_PUBLIC_DATA_SOURCE_ID", "public-ds"), \
             patch.object(pipeline.requests, "post", side_effect=responses), \
             patch.object(pipeline.requests, "get", return_value=schema), \
             patch.object(pipeline.requests, "patch") as mock_patch:
            pipeline.sync_public_approved_to_member_db()
        mock_patch.assert_not_called()


class TestWorkflowOperationalGuards(unittest.TestCase):
    def test_daily_timeout_covers_configured_deep_dive_budget(self):
        daily = (Path(pipeline.__file__).parent / ".github" / "workflows" / "daily.yml").read_text()
        self.assertIn("timeout-minutes: 45", daily)
        self.assertIn('GEMINI_SCREENING_CALL_TIMEOUT_SECONDS: "60"', daily)
        self.assertIn('GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET: "12"', daily)

    def test_real_regression_shares_gemini_concurrency_group(self):
        root = Path(pipeline.__file__).parent / ".github" / "workflows"
        daily = (root / "daily.yml").read_text()
        regen = (root / "regression-test.yml").read_text()
        self.assertIn("group: ai-intelligence-gemini-budget", daily)
        self.assertIn("group: ai-intelligence-gemini-budget", regen)
        self.assertIn("GEMINI_QUOTA_PROJECT_ID: ${{ vars.GEMINI_QUOTA_PROJECT_ID || secrets.GEMINI_QUOTA_PROJECT_ID }}", daily)
        self.assertIn("GEMINI_QUOTA_PROJECT_ID: ${{ vars.GEMINI_QUOTA_PROJECT_ID || secrets.GEMINI_QUOTA_PROJECT_ID }}", regen)
        self.assertIn("GEMINI_QUOTA_FALLBACK_ID: ${{ github.repository }}", daily)
        self.assertIn("GEMINI_QUOTA_FALLBACK_ID: ${{ github.repository }}", regen)
        self.assertIn("gate_history/", regen)

    def test_monthly_digest_is_private_artifact_not_public_raw_url(self):
        daily = (Path(pipeline.__file__).parent / ".github" / "workflows" / "daily.yml").read_text()
        self.assertIn("monthly_digests/", daily)
        self.assertIn("actions/upload-artifact@v7", daily)
        self.assertNotIn("raw.githubusercontent.com", pipeline.generate_monthly_digest.__doc__ or "")



class TestGeminiCallWatchdogs(unittest.TestCase):
    def test_screening_and_calibration_pool_calls_use_per_call_watchdog(self):
        pipeline.SESSION_EXHAUSTED_MODELS.clear()
        pipeline.SESSION_UNAVAILABLE_MODELS.clear()
        fake_response = MagicMock()
        watchdog = MagicMock()
        watchdog.return_value.__enter__.return_value = None
        watchdog.return_value.__exit__.return_value = False
        with patch.object(pipeline, "_gemini_call_timeout", watchdog), \
             patch.object(pipeline, "_generate_via_chat", return_value=fake_response):
            result, model = pipeline._call_model_pool(
                "prompt", {"max_output_tokens": 10}, "screening_batch", 0, ["screen-model"], deep_dive=False
            )
        self.assertIs(result, fake_response)
        self.assertEqual("screen-model", model)
        watchdog.assert_called_once_with(pipeline.GEMINI_SCREENING_CALL_TIMEOUT_SECONDS)


class TestPublicSyncWritablePayload(unittest.TestCase):
    def _query_response(self, results):
        r = MagicMock(); r.raise_for_status.return_value = None
        r.json.return_value = {"results": results, "has_more": False}
        return r

    def test_read_only_notion_fields_are_removed_before_member_db_write(self):
        internal = {
            "id": "internal-1",
            "properties": {
                pipeline.PROP_URL: {"id": "url-id", "type": "url", "url": "https://example.com/item"},
                pipeline.PROP_NAME: {
                    "id": "title-id", "type": "title",
                    "title": [{
                        "type": "text", "plain_text": "Example", "href": None,
                        "annotations": {"bold": False, "italic": False, "strikethrough": False, "underline": False, "code": False, "color": "default"},
                        "text": {"content": "Example", "link": None},
                    }],
                },
            },
        }
        schema = MagicMock(); schema.raise_for_status.return_value = None
        schema.json.return_value = {"properties": {
            pipeline.PROP_URL: {"type": "url"},
            pipeline.PROP_NAME: {"type": "title"},
        }}
        create = MagicMock(); create.raise_for_status.return_value = None
        posts = [
            self._query_response([internal]),  # eligible
            self._query_response([internal]),  # all internal
            self._query_response([]),          # member DB existing
            create,                            # create member record
        ]
        with patch.object(pipeline, "NOTION_API_KEY", "k"), \
             patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "internal-ds"), \
             patch.object(pipeline, "NOTION_DATABASE_ID", None), \
             patch.object(pipeline, "NOTION_PUBLIC_DATA_SOURCE_ID", "public-ds"), \
             patch.object(pipeline, "NOTION_PUBLIC_DATABASE_ID", None), \
             patch.object(pipeline.requests, "post", side_effect=posts) as mock_post, \
             patch.object(pipeline.requests, "get", return_value=schema):
            pipeline.sync_public_approved_to_member_db()
        payload = mock_post.call_args_list[-1].kwargs["json"]
        title_prop = payload["properties"][pipeline.PROP_NAME]
        url_prop = payload["properties"][pipeline.PROP_URL]
        self.assertEqual({"url": "https://example.com/item"}, url_prop)
        self.assertNotIn("id", title_prop)
        self.assertNotIn("type", title_prop)
        self.assertEqual("Example", title_prop["title"][0]["text"]["content"])
        self.assertNotIn("plain_text", title_prop["title"][0])

    def test_member_db_same_name_wrong_type_fails_before_create_or_update(self):
        internal = {"id": "internal-1", "properties": {pipeline.PROP_URL: {"url": "https://example.com/item"}}}
        schema = MagicMock(); schema.raise_for_status.return_value = None
        schema.json.return_value = {"properties": {
            pipeline.PROP_URL: {"type": "url"},
            pipeline.PROP_SCORE: {"type": "rich_text"},  # internal expectation is number
        }}
        posts = [self._query_response([]), self._query_response([internal])]
        with patch.object(pipeline, "NOTION_API_KEY", "k"), \
             patch.object(pipeline, "NOTION_DATA_SOURCE_ID", "internal-ds"), \
             patch.object(pipeline, "NOTION_PUBLIC_DATA_SOURCE_ID", "public-ds"), \
             patch.object(pipeline.requests, "post", side_effect=posts) as mock_post, \
             patch.object(pipeline.requests, "get", return_value=schema), \
             patch.object(pipeline.requests, "patch") as mock_patch:
            with self.assertRaises(ValueError):
                pipeline.sync_public_approved_to_member_db()
        self.assertEqual(2, mock_post.call_count)
        mock_patch.assert_not_called()


class TestBusinessModelPromptConsistency(unittest.TestCase):
    def test_legacy_single_item_screening_prompt_matches_free_note_plus_subscriber_db_model(self):
        prompt = pipeline.build_screening_prompt("x", "desc", 10, "GitHub")
        self.assertNotIn("有料note", prompt)
        self.assertIn("無料note", prompt)
        self.assertIn("会員向け意思決定DB", prompt)


class TestReviewEvidenceTraceability(unittest.TestCase):
    def test_final_evidence_collection_includes_retrieved_supplement_before_grounding(self):
        source_info = {
            "primary_url": "https://arxiv.org/abs/2608.12345",
            "evidence_documents": [
                {"url": "https://arxiv.org/pdf/2608.12345.pdf", "retrieved": True},
                {"url": "https://example.com/not-retrieved", "retrieved": False},
            ],
            "deep_source_urls": ["https://github.com/example/project"],
        }
        grounding = {"evidence_urls": ["https://example.com/grounded"]}
        with patch.object(pipeline, "MAX_EVIDENCE_DOCUMENTS", 3):
            urls = pipeline._collect_final_evidence_urls(source_info, grounding)
        self.assertEqual(
            urls,
            [
                "https://arxiv.org/abs/2608.12345",
                "https://arxiv.org/pdf/2608.12345.pdf",
                "https://example.com/grounded",
            ],
        )


class TestDeepDiveRequiresPersistedStock(unittest.TestCase):
    def test_score_pass_without_notion_stock_page_is_not_deep_dive_candidate(self):
        rows = [
            {"score": 90, "notion_page_id": None, "repo": {"nameWithOwner": "lost/high-score"}},
            {"score": 85, "notion_page_id": "page-85", "repo": {"nameWithOwner": "stocked/good"}},
            {"score": 59, "notion_page_id": "page-59", "repo": {"nameWithOwner": "below/threshold"}},
        ]
        with patch.object(pipeline, "NOTION_SAVE_THRESHOLD_SCORE", 60):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        self.assertEqual(["stocked/good"], [x["repo"]["nameWithOwner"] for x in selected])

class TestDiscoveryAliasIdentity(unittest.TestCase):
    def test_producthunt_and_hn_discovery_urls_are_explicit_identity_aliases(self):
        ph = {
            "url": "https://vendor.example/product", "primaryUrl": "https://vendor.example/product",
            "sourceDetails": {"producthunt_url": "https://www.producthunt.com/posts/product"},
        }
        hn = {
            "url": "https://vendor.example/post", "primaryUrl": "https://vendor.example/post",
            "sourceDetails": {"hn_url": "https://news.ycombinator.com/item?id=123"},
        }
        ph_ids = pipeline.candidate_identity_urls(ph)
        hn_ids = pipeline.candidate_identity_urls(hn)
        self.assertIn(pipeline.canonicalize_url("https://www.producthunt.com/posts/product"), ph_ids)
        self.assertIn(pipeline.canonicalize_url("https://news.ycombinator.com/item?id=123"), hn_ids)


class TestProfitOptimizationPriority(unittest.TestCase):
    def _row(self, name, decision, commercial, shelf, page_id=None, engagement=0, topic="OTHER"):
        return {
            "score": decision,
            "commercial_score": commercial,
            "shelf_life_score": shelf,
            "shelf_life": pipeline.shelf_life_label(shelf),
            "portfolio_topic": topic,
            "raw_portfolio_topic": topic,
            "notion_page_id": page_id or f"page-{name}",
            "repo": {"nameWithOwner": name, "stargazerCount": engagement},
        }

    def test_commercial_score_can_reorder_only_eligible_stock(self):
        rows = [
            self._row("quality-high-commercial-low", 85, 20, 50),
            self._row("quality-good-commercial-high", 80, 95, 50),
        ]
        with patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", True), \
             patch.object(pipeline, "EVERGREEN_PORTFOLIO_MIN", 0):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        self.assertEqual("quality-good-commercial-high", selected[0]["repo"]["nameWithOwner"])
        self.assertGreater(selected[0]["deep_dive_priority_score"], selected[1]["deep_dive_priority_score"])

    def test_high_commercial_value_never_bypasses_stock_threshold(self):
        rows = [
            self._row("below-threshold", 59, 100, 100),
            self._row("eligible", 60, 10, 10),
        ]
        with patch.object(pipeline, "NOTION_SAVE_THRESHOLD_SCORE", 60), \
             patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", True), \
             patch.object(pipeline, "EVERGREEN_PORTFOLIO_MIN", 0):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        self.assertEqual(["eligible"], [x["repo"]["nameWithOwner"] for x in selected])

    def test_unpersisted_high_profit_candidate_never_enters_deep_dive(self):
        rows = [
            self._row("not-persisted", 95, 100, 100, page_id=""),
            self._row("persisted", 70, 40, 50),
        ]
        rows[0]["notion_page_id"] = None
        with patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", True):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        self.assertEqual(["persisted"], [x["repo"]["nameWithOwner"] for x in selected])

    def test_evergreen_enters_top_slots_only_within_tolerance(self):
        rows = [
            self._row("flash-1", 90, 90, 10),
            self._row("flash-2", 86, 86, 20),
            self._row("trend-3", 82, 82, 50),
            self._row("evergreen-close", 80, 80, 90),
        ]
        with patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", True), \
             patch.object(pipeline, "TOP_N_FOR_DEEP_DIVE", 3), \
             patch.object(pipeline, "EVERGREEN_PORTFOLIO_MIN", 1), \
             patch.object(pipeline, "EVERGREEN_PRIORITY_TOLERANCE", 8):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        self.assertIn("evergreen-close", [x["repo"]["nameWithOwner"] for x in selected[:3]])
        self.assertEqual("trend-3", selected[3]["repo"]["nameWithOwner"])

    def test_weak_evergreen_does_not_displace_materially_stronger_candidate(self):
        rows = [
            self._row("flash-1", 95, 95, 10),
            self._row("flash-2", 90, 90, 20),
            self._row("trend-3", 85, 85, 50),
            self._row("evergreen-weak", 60, 10, 95),
        ]
        with patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", True), \
             patch.object(pipeline, "TOP_N_FOR_DEEP_DIVE", 3), \
             patch.object(pipeline, "EVERGREEN_PORTFOLIO_MIN", 1), \
             patch.object(pipeline, "EVERGREEN_PRIORITY_TOLERANCE", 8):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        self.assertNotIn("evergreen-weak", [x["repo"]["nameWithOwner"] for x in selected[:3]])

    def test_profit_priority_can_be_disabled_without_changing_quality_order(self):
        rows = [
            self._row("decision-90", 90, 0, 10),
            self._row("decision-80", 80, 100, 100),
        ]
        with patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", False):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        self.assertEqual(["decision-90", "decision-80"], [x["repo"]["nameWithOwner"] for x in selected])

    def test_parser_keeps_core_score_when_profit_fields_are_missing(self):
        payload = '[{"id":"B0001","score":72,"reason":"有望"}]'
        parsed, missing, diagnostic = pipeline._parse_batch_screening_response(payload, {"B0001"}, include_diagnostic=True)
        self.assertEqual([], missing)
        self.assertEqual(72, parsed["B0001"]["score"])
        self.assertIsNone(parsed["B0001"]["commercial_score"])
        self.assertIsNone(parsed["B0001"]["shelf_life_score"])
        self.assertIn("missing_commercial_score:B0001", diagnostic)

    def test_calibration_updates_profit_metadata_independently(self):
        items = [{
            "screening_id": "B0001", "repo": {"source": "GitHub", "nameWithOwner": "one"},
            "raw_score": 70, "final_score": 70, "score": 70, "reason": "raw",
            "commercial_score": 40, "shelf_life_score": 30, "shelf_life": "FLASH",
            "portfolio_topic": "DATA", "raw_portfolio_topic": "DATA",
            "calibrated": False, "screening_status": "completed",
        }]
        response = types.SimpleNamespace(text='[{"id":"B0001","score":72,"commercial_score":91,"shelf_life_score":84,"reason":"補正"}]')
        with patch.object(pipeline, "call_screening_provider", return_value=response):
            result, calls = pipeline.calibrate_candidates(items)
        self.assertEqual(1, calls)
        self.assertEqual(72, result[0]["score"])
        self.assertEqual(91, result[0]["commercial_score"])
        self.assertEqual(84, result[0]["shelf_life_score"])
        self.assertEqual("EVERGREEN", result[0]["shelf_life"])
        self.assertEqual("DATA", result[0]["portfolio_topic"])  # calibration topic欠落時は初回分類を保持
        self.assertEqual(pipeline.deep_dive_priority_score(72, 91), result[0]["deep_dive_priority_score"])

    def test_observed_history_persists_profit_metadata_without_notion_schema_change(self):
        import json, tempfile
        item = self._row("one", 80, 92, 88)
        item.update({
            "screening_id": "B0001", "raw_score": 80, "final_score": 80,
            "reason": "ok", "calibrated": True, "screening_status": "completed",
        })
        pipeline._attach_profit_metadata(item, 92, 88)
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(pipeline, "OBSERVED_HISTORY_DIR", directory), \
             patch.object(pipeline, "upload_observed_history_to_github", return_value=None):
            path = pipeline.save_observed_history([item], 1, 0, calibration_calls=1, total_collected=1)
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        row = payload["items"][0]
        self.assertEqual(92, row["commercial_value_score"])
        self.assertEqual(88, row["shelf_life_score"])
        self.assertEqual("EVERGREEN", row["shelf_life"])
        self.assertEqual(pipeline.deep_dive_priority_score(80, 92), row["deep_dive_priority_score"])

    def test_topic_parser_accepts_supported_topic_without_affecting_score(self):
        payload = '[{"id":"B0001","score":82,"commercial_score":77,"shelf_life_score":60,"topic":"AGENT","reason":"有望"}]'
        parsed, missing, diagnostic = pipeline._parse_batch_screening_response(payload, {"B0001"}, include_diagnostic=True)
        self.assertEqual([], missing)
        self.assertEqual(82, parsed["B0001"]["score"])
        self.assertEqual("AGENT", parsed["B0001"]["portfolio_topic"])
        self.assertNotIn("invalid_topic", diagnostic)

    def test_missing_topic_is_fail_safe_other_and_keeps_core_score(self):
        payload = '[{"id":"B0001","score":82,"commercial_score":77,"shelf_life_score":60,"reason":"有望"}]'
        parsed, missing, diagnostic = pipeline._parse_batch_screening_response(payload, {"B0001"}, include_diagnostic=True)
        self.assertEqual([], missing)
        self.assertEqual(82, parsed["B0001"]["score"])
        self.assertEqual("OTHER", parsed["B0001"]["portfolio_topic"])
        self.assertIn("missing_topic:B0001", diagnostic)

    def test_portfolio_balance_adds_second_topic_only_when_priority_is_close(self):
        rows = [
            self._row("agent-1", 90, 90, 50, topic="AGENT"),
            self._row("agent-2", 88, 88, 50, topic="AGENT"),
            self._row("agent-3", 86, 86, 50, topic="AGENT"),
            self._row("infra-close", 84, 84, 50, topic="INFRA"),
        ]
        with patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", True), \
             patch.object(pipeline, "EVERGREEN_PORTFOLIO_MIN", 0), \
             patch.object(pipeline, "ENABLE_PORTFOLIO_BALANCE", True), \
             patch.object(pipeline, "PORTFOLIO_MIN_DISTINCT_TOPICS", 2), \
             patch.object(pipeline, "PORTFOLIO_TOPIC_PRIORITY_TOLERANCE", 6), \
             patch.object(pipeline, "TOP_N_FOR_DEEP_DIVE", 3):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        topics = [x["portfolio_topic"] for x in selected[:3]]
        self.assertIn("AGENT", topics)
        self.assertIn("INFRA", topics)
        self.assertIn("infra-close", [x["repo"]["nameWithOwner"] for x in selected[:3]])

    def test_portfolio_balance_never_displaces_materially_stronger_same_topic_candidate(self):
        rows = [
            self._row("agent-1", 95, 95, 50, topic="AGENT"),
            self._row("agent-2", 92, 92, 50, topic="AGENT"),
            self._row("agent-3", 90, 90, 50, topic="AGENT"),
            self._row("infra-weak", 70, 70, 50, topic="INFRA"),
        ]
        with patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", True), \
             patch.object(pipeline, "EVERGREEN_PORTFOLIO_MIN", 0), \
             patch.object(pipeline, "ENABLE_PORTFOLIO_BALANCE", True), \
             patch.object(pipeline, "PORTFOLIO_MIN_DISTINCT_TOPICS", 2), \
             patch.object(pipeline, "PORTFOLIO_TOPIC_PRIORITY_TOLERANCE", 6), \
             patch.object(pipeline, "TOP_N_FOR_DEEP_DIVE", 3):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        self.assertNotIn("infra-weak", [x["repo"]["nameWithOwner"] for x in selected[:3]])

    def test_portfolio_balance_does_not_force_other_topic_metadata(self):
        rows = [
            self._row("unknown-1", 90, 90, 50, topic="OTHER"),
            self._row("unknown-2", 88, 88, 50, topic="OTHER"),
            self._row("unknown-3", 86, 86, 50, topic="OTHER"),
            self._row("infra-close", 84, 84, 50, topic="INFRA"),
        ]
        with patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", True), \
             patch.object(pipeline, "EVERGREEN_PORTFOLIO_MIN", 0), \
             patch.object(pipeline, "ENABLE_PORTFOLIO_BALANCE", True), \
             patch.object(pipeline, "PORTFOLIO_MIN_DISTINCT_TOPICS", 2), \
             patch.object(pipeline, "PORTFOLIO_TOPIC_PRIORITY_TOLERANCE", 6), \
             patch.object(pipeline, "TOP_N_FOR_DEEP_DIVE", 3):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        self.assertEqual(["unknown-1", "unknown-2", "unknown-3"], [x["repo"]["nameWithOwner"] for x in selected[:3]])

    def test_portfolio_balance_preserves_single_evergreen_slot(self):
        rows = [
            self._row("agent-flash-1", 90, 90, 10, topic="AGENT"),
            self._row("agent-evergreen", 86, 86, 90, topic="AGENT"),
            self._row("agent-flash-3", 84, 84, 10, topic="AGENT"),
            self._row("infra-close", 83, 83, 50, topic="INFRA"),
        ]
        with patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", True), \
             patch.object(pipeline, "EVERGREEN_PORTFOLIO_MIN", 1), \
             patch.object(pipeline, "EVERGREEN_PRIORITY_TOLERANCE", 8), \
             patch.object(pipeline, "ENABLE_PORTFOLIO_BALANCE", True), \
             patch.object(pipeline, "PORTFOLIO_MIN_DISTINCT_TOPICS", 2), \
             patch.object(pipeline, "PORTFOLIO_TOPIC_PRIORITY_TOLERANCE", 6), \
             patch.object(pipeline, "TOP_N_FOR_DEEP_DIVE", 3):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        visible = selected[:3]
        self.assertTrue(any(x["shelf_life"] == "EVERGREEN" for x in visible))
        self.assertTrue(any(x["portfolio_topic"] == "INFRA" for x in visible))

    def test_portfolio_balance_can_be_disabled(self):
        rows = [
            self._row("agent-1", 90, 90, 50, topic="AGENT"),
            self._row("agent-2", 88, 88, 50, topic="AGENT"),
            self._row("agent-3", 86, 86, 50, topic="AGENT"),
            self._row("infra-close", 84, 84, 50, topic="INFRA"),
        ]
        with patch.object(pipeline, "ENABLE_PROFIT_PRIORITY", True), \
             patch.object(pipeline, "EVERGREEN_PORTFOLIO_MIN", 0), \
             patch.object(pipeline, "ENABLE_PORTFOLIO_BALANCE", False), \
             patch.object(pipeline, "TOP_N_FOR_DEEP_DIVE", 3):
            selected = pipeline._select_stocked_deep_dive_candidates(rows)
        self.assertEqual(["agent-1", "agent-2", "agent-3"], [x["repo"]["nameWithOwner"] for x in selected[:3]])

    def test_observed_history_persists_portfolio_topic(self):
        import json, tempfile
        item = self._row("one", 80, 92, 88, topic="DATA")
        item.update({
            "screening_id": "B0001", "raw_score": 80, "final_score": 80,
            "reason": "ok", "calibrated": True, "screening_status": "completed",
        })
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(pipeline, "OBSERVED_HISTORY_DIR", directory), \
             patch.object(pipeline, "upload_observed_history_to_github", return_value=None):
            path = pipeline.save_observed_history([item], 1, 0, calibration_calls=1, total_collected=1)
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        row = payload["items"][0]
        self.assertEqual("DATA", row["portfolio_topic"])
        self.assertEqual("DATA", row["raw_portfolio_topic"])


class TestSourceROILearning(unittest.TestCase):
    def _state(self, github=None, hn=None, arxiv=None, ph=None):
        def row(value):
            return value or {"screened": 100, "stock_saved": 40, "deep_dive_attempted": 6,
                             "generation_requests": 9, "ready": 2, "review": 1}
        return {"version": 1, "runs": [{"run_id": "r1", "sources": {
            "GitHub": row(github), "HackerNews": row(hn), "ArXiv": row(arxiv), "ProductHunt": row(ph),
        }}]}

    def test_cold_start_preserves_existing_source_limits(self):
        profile = pipeline.compute_source_roi_profile({"version": 1, "runs": []})
        limits = pipeline.allocate_source_fetch_limits(profile, 200)
        self.assertEqual(pipeline.GITHUB_FETCH_LIMIT, limits["GitHub"])
        self.assertEqual(pipeline.HN_FETCH_LIMIT, limits["HackerNews"])
        self.assertEqual(pipeline.ARXIV_FETCH_LIMIT, limits["ArXiv"])
        self.assertEqual(pipeline.PRODUCTHUNT_FETCH_LIMIT, limits["ProductHunt"])

    def test_all_four_sources_share_identical_roi_cap(self):
        caps = pipeline.SOURCE_ROI_MAX_FETCH_BY_SOURCE
        self.assertEqual(set(pipeline.SOURCE_ROI_SOURCES), set(caps))
        self.assertEqual(1, len(set(caps.values())))
        self.assertEqual(pipeline.SOURCE_ROI_MAX_FETCH_PER_SOURCE, caps["ProductHunt"])

    def test_equal_roi_produces_equal_allocation_for_all_four_sources(self):
        profile = pipeline.compute_source_roi_profile(self._state())
        limits = pipeline.allocate_source_fetch_limits(profile, 200)
        self.assertTrue(any(row["learning_active"] for row in profile.values()))
        self.assertEqual({50}, set(limits.values()))

    def test_high_yield_source_receives_more_slots_after_maturity(self):
        high = {"screened": 120, "stock_saved": 80, "deep_dive_attempted": 12,
                "generation_requests": 15, "ready": 8, "review": 1}
        low = {"screened": 120, "stock_saved": 20, "deep_dive_attempted": 12,
               "generation_requests": 22, "ready": 1, "review": 2}
        profile = pipeline.compute_source_roi_profile(self._state(github=high, arxiv=low))
        limits = pipeline.allocate_source_fetch_limits(profile, 200)
        self.assertTrue(profile["GitHub"]["learning_active"])
        self.assertGreater(profile["GitHub"]["roi_score"], profile["ArXiv"]["roi_score"])
        self.assertGreater(limits["GitHub"], limits["ArXiv"])
        self.assertEqual(200, sum(limits.values()))

    def test_mandatory_source_floor_is_never_removed(self):
        terrible = {"screened": 300, "stock_saved": 0, "deep_dive_attempted": 20,
                    "generation_requests": 30, "ready": 0, "review": 0}
        strong = {"screened": 300, "stock_saved": 220, "deep_dive_attempted": 20,
                  "generation_requests": 22, "ready": 15, "review": 1}
        profile = pipeline.compute_source_roi_profile(self._state(github=strong, hn=strong, arxiv=terrible, ph=terrible))
        with patch.object(pipeline, "SOURCE_ROI_MIN_FETCH_PER_SOURCE", 25):
            limits = pipeline.allocate_source_fetch_limits(profile, 200)
        for source in pipeline.SOURCE_ROI_SOURCES:
            self.assertGreaterEqual(limits[source], 25)
        self.assertLessEqual(limits["ProductHunt"], pipeline.SOURCE_ROI_MAX_FETCH_BY_SOURCE["ProductHunt"])

    def test_insufficient_history_does_not_activate_learning(self):
        tiny = {"screened": 5, "stock_saved": 5, "deep_dive_attempted": 1,
                "generation_requests": 1, "ready": 1, "review": 0}
        state = self._state(github=tiny, hn=tiny, arxiv=tiny, ph=tiny)
        profile = pipeline.compute_source_roi_profile(state)
        self.assertFalse(any(row["learning_active"] for row in profile.values()))
        self.assertEqual(pipeline._source_base_fetch_limits(), pipeline.allocate_source_fetch_limits(profile, 200))

    def test_recent_runs_receive_more_weight_than_old_runs(self):
        bad = {"screened": 100, "stock_saved": 10, "deep_dive_attempted": 8,
               "generation_requests": 14, "ready": 0, "review": 1}
        good = {"screened": 100, "stock_saved": 75, "deep_dive_attempted": 8,
                "generation_requests": 9, "ready": 6, "review": 0}
        state = {"version": 1, "runs": [
            {"run_id": "old", "sources": {src: bad for src in pipeline.SOURCE_ROI_SOURCES}},
            {"run_id": "new", "sources": {"GitHub": good, "HackerNews": bad, "ArXiv": bad, "ProductHunt": bad}},
        ]}
        with patch.object(pipeline, "SOURCE_ROI_RECENCY_DECAY", 0.5):
            profile = pipeline.compute_source_roi_profile(state)
        self.assertGreater(profile["GitHub"]["roi_score"], profile["ArXiv"]["roi_score"])

    def test_corrupt_state_fails_safe_to_cold_start(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("{not-json", encoding="utf-8")
            state = pipeline.load_source_roi_state(str(path))
        self.assertEqual([], state["runs"])

    def test_run_metrics_count_only_actual_notion_stock_persistence(self):
        screened = [
            {"repo": {"source": "GitHub"}, "screening_status": "completed", "notion_page_id": "page-1"},
            {"repo": {"source": "GitHub"}, "screening_status": "completed", "notion_page_id": None},
            {"repo": {"source": "ArXiv"}, "screening_status": "failed", "notion_page_id": None},
        ]
        funnel = pipeline.DeepDiveGateFunnel()
        funnel.records = [
            {"source": "GitHub", "generation_request_count": 2, "final_status": pipeline.ARTICLE_STATUS_READY},
            {"source": "ArXiv", "generation_request_count": 1, "final_status": pipeline.CONTENT_STATUS_PENDING_RETRY},
        ]
        metrics = pipeline.build_source_roi_run_metrics(screened, funnel)
        self.assertEqual(2, metrics["GitHub"]["screened"])
        self.assertEqual(1, metrics["GitHub"]["stock_saved"])
        self.assertEqual(1, metrics["GitHub"]["ready"])
        self.assertEqual(2, metrics["GitHub"]["generation_requests"])
        self.assertEqual(1, metrics["ArXiv"]["pending_retry"])

    def test_gate_record_carries_source_and_generation_cost(self):
        row = pipeline.build_candidate_gate_record(
            1, "owner/repo", "https://example.com", 80, "completed",
            final_status=pipeline.ARTICLE_STATUS_READY, source="GitHub", generation_request_count=2,
        )
        self.assertEqual("GitHub", row["source"])
        self.assertEqual(2, row["generation_request_count"])

    def test_state_history_is_bounded(self):
        state = {"version": 1, "runs": [{"run_id": str(i), "sources": {}} for i in range(10)]}
        with patch.object(pipeline, "SOURCE_ROI_HISTORY_RUNS", 5):
            updated = pipeline.update_source_roi_state(state, [], None, persist=False)
        self.assertEqual(5, len(updated["runs"]))
        self.assertEqual("9", updated["runs"][-2]["run_id"])

    def test_feature_flag_restores_static_limits(self):
        profile = pipeline.compute_source_roi_profile(self._state())
        with patch.object(pipeline, "ENABLE_SOURCE_ROI_LEARNING", False):
            limits = pipeline.allocate_source_fetch_limits(profile, 200)
        self.assertEqual(pipeline._source_base_fetch_limits(), limits)

    def test_producthunt_remains_mandatory_even_when_roi_is_low(self):
        terrible = {"screened": 200, "stock_saved": 1, "deep_dive_attempted": 10,
                    "generation_requests": 18, "ready": 0, "review": 1}
        strong = {"screened": 200, "stock_saved": 150, "deep_dive_attempted": 10,
                  "generation_requests": 11, "ready": 8, "review": 0}
        profile = pipeline.compute_source_roi_profile(self._state(github=strong, hn=strong, arxiv=strong, ph=terrible))
        with patch.object(pipeline, "SOURCE_ROI_MIN_FETCH_PER_SOURCE", 25):
            limits = pipeline.allocate_source_fetch_limits(profile, 200)
        self.assertGreaterEqual(limits["ProductHunt"], 25)



    def test_observed_history_records_source_roi_allocation_context(self):
        import json, tempfile
        item = {"screening_id": "B0001", "repo": {"source": "GitHub", "nameWithOwner": "one", "url": "https://x"},
                "raw_score": 80, "final_score": 80, "score": 80, "reason": "ok",
                "screening_status": "completed", "calibrated": True, "notion_page_id": "page-1"}
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(pipeline, "OBSERVED_HISTORY_DIR", directory), \
             patch.object(pipeline, "upload_observed_history_to_github", return_value=None):
            path = pipeline.save_observed_history(
                [item], 1, 0, total_collected=1,
                source_roi_profile={"GitHub": {"roi_score": 72.5}},
                source_fetch_limits={"GitHub": 65, "HackerNews": 45, "ArXiv": 45, "ProductHunt": 45},
            )
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertTrue(payload["source_roi"]["enabled"])
        self.assertEqual(65, payload["source_roi"]["fetch_limits"]["GitHub"])
        self.assertEqual(72.5, payload["source_roi"]["profile"]["GitHub"]["roi_score"])


class TestGeminiEfficiencyGuardrails(unittest.TestCase):
    def test_persistent_rejection_does_not_consume_deep_dive_or_run_budget(self):
        run_budget = pipeline.GeminiBudget(50, 4, 1)
        deep_budget = pipeline.DeepDiveModelBudget(12)
        pending_budget = pipeline.PendingRetryRequestBudget(2)
        persistent = MagicMock()
        persistent.reserve.side_effect = pipeline.GeminiBudgetExceededError(
            "Persistent Gemini model budget exhausted: gemini-3.6-flash 18/18"
        )
        audit = pipeline.GeminiUsageAudit()
        with patch.object(pipeline, "GEMINI_BUDGET", run_budget), \
             patch.object(pipeline, "DEEP_DIVE_MODEL_BUDGET", deep_budget), \
             patch.object(pipeline, "PENDING_RETRY_REQUEST_BUDGET", pending_budget), \
             patch.object(pipeline, "PERSISTENT_GEMINI_COUNTER", persistent), \
             patch.object(pipeline, "GEMINI_USAGE_AUDIT", audit):
            with self.assertRaises(pipeline.GeminiBudgetExceededError):
                pipeline._consume_gemini_request(
                    "deep_dive", model_name="gemini-3.6-flash",
                    count_as_deep_dive=True, request_origin="new"
                )
        self.assertEqual(0, deep_budget.used)
        self.assertEqual(0, run_budget.request_count)
        self.assertEqual(0, pending_budget.used)
        self.assertEqual([], audit.records)

    def test_pending_retry_budget_caps_actual_deep_dive_sends_before_persistent_reserve(self):
        run_budget = pipeline.GeminiBudget(50, 4, 4)
        deep_budget = pipeline.DeepDiveModelBudget(12)
        pending_budget = pipeline.PendingRetryRequestBudget(2)
        persistent = MagicMock()
        audit = pipeline.GeminiUsageAudit()
        with patch.object(pipeline, "GEMINI_BUDGET", run_budget), \
             patch.object(pipeline, "DEEP_DIVE_MODEL_BUDGET", deep_budget), \
             patch.object(pipeline, "PENDING_RETRY_REQUEST_BUDGET", pending_budget), \
             patch.object(pipeline, "PERSISTENT_GEMINI_COUNTER", persistent), \
             patch.object(pipeline, "GEMINI_USAGE_AUDIT", audit):
            pipeline._consume_gemini_request(
                "deep_dive", model_name="m", count_as_deep_dive=True,
                request_origin="pending_retry"
            )
            pipeline._consume_gemini_request(
                "quality_retry", model_name="m", count_as_deep_dive=True,
                request_origin="pending_retry"
            )
            with self.assertRaises(pipeline.PendingRetryBudgetExceededError):
                pipeline._consume_gemini_request(
                    "deep_dive", model_name="m", count_as_deep_dive=True,
                    request_origin="pending_retry"
                )
        self.assertEqual(2, pending_budget.used)
        self.assertEqual(2, deep_budget.used)
        self.assertEqual(2, run_budget.request_count)
        self.assertEqual(2, persistent.reserve.call_count)
        self.assertEqual(2, len(audit.records))

    def test_persistent_exhausted_model_is_session_skipped_and_pool_falls_back(self):
        response = MagicMock()
        calls = []
        def fake_generate(model_name, *args, **kwargs):
            calls.append(model_name)
            if model_name == "m1":
                raise pipeline.GeminiBudgetExceededError(
                    "Persistent Gemini model budget exhausted: m1 18/18"
                )
            return response
        with patch.object(pipeline, "SESSION_EXHAUSTED_MODELS", set()), \
             patch.object(pipeline, "SESSION_UNAVAILABLE_MODELS", set()), \
             patch.object(pipeline, "GEMINI_DEEP_DIVE_CALL_PACING_SECONDS", 0), \
             patch.object(pipeline, "_generate_via_chat", side_effect=fake_generate):
            got, model = pipeline._call_model_pool(
                "p", None, "deep_dive", 0, ["m1", "m2"], deep_dive=True
            )
            self.assertIs(got, response)
            self.assertEqual("m2", model)
            self.assertIn("m1", pipeline.SESSION_EXHAUSTED_MODELS)
        self.assertEqual(["m1", "m2"], calls)

    def test_nonrepairable_evidence_reason_skips_dynamic_retry(self):
        ok, reason = pipeline.should_attempt_dynamic_retry(
            [{"reason_code": pipeline.REASON_CODE_PUB_SOURCE_SUFFICIENCY, "message": "primary_evidence_insufficient"}],
            {"state": pipeline.EVIDENCE_SUFFICIENT},
            candidate_origin="new",
        )
        self.assertFalse(ok)
        self.assertEqual("non_repairable_evidence_or_source_gap", reason)

    def test_repairable_fact_mismatch_can_retry(self):
        ok, reason = pipeline.should_attempt_dynamic_retry(
            [{"reason_code": pipeline.REASON_CODE_FACT_NUMERICAL_MISMATCH, "message": "numeric mismatch"}],
            {"state": pipeline.EVIDENCE_SUFFICIENT},
            candidate_origin="new",
        )
        self.assertTrue(ok)
        self.assertEqual("repairable", reason)

    def test_pending_retry_without_remaining_dedicated_budget_skips_quality_retry(self):
        pending_budget = pipeline.PendingRetryRequestBudget(1)
        pending_budget.consume("deep_dive")
        with patch.object(pipeline, "PENDING_RETRY_REQUEST_BUDGET", pending_budget):
            ok, reason = pipeline.should_attempt_dynamic_retry(
                [{"reason_code": pipeline.REASON_CODE_FACT_UNSUPPORTED_CLAIM, "message": "unsupported"}],
                {"state": pipeline.EVIDENCE_SUFFICIENT},
                candidate_origin="pending_retry",
            )
        self.assertFalse(ok)
        self.assertEqual("pending_retry_budget_exhausted", reason)

    def test_funnel_retains_max_tokens_event_even_if_final_reason_is_different(self):
        funnel = pipeline.DeepDiveGateFunnel()
        funnel.record({
            "candidate_origin": "new",
            "evidence_sufficiency": pipeline.EVIDENCE_SUFFICIENT,
            "evidence_initial_sufficiency": pipeline.EVIDENCE_SUFFICIENT,
            "generation_status": "completed",
            "reason_codes": [{"reason_code": pipeline.REASON_CODE_FACT_UNSUPPORTED_CLAIM, "message": "x"}],
            "any_generation_truncated": True,
            "fact_gate": pipeline.GATE_STATUS_FAIL,
            "editorial_gate": pipeline.GATE_STATUS_PASS,
            "publication_readiness_gate": pipeline.GATE_STATUS_REVIEW,
            "human_appeal_gate": pipeline.GATE_STATUS_PASS,
            "final_status": pipeline.CONTENT_STATUS_QUALITY_FAILED,
        })
        self.assertEqual(1, funnel.counters["max_tokens_failed"])


class TestRealArticleGateCalibration20260821(unittest.TestCase):
    """2026-08-21の実記事4本で見つかったGate false-positive / missを固定する。"""

    def test_post_training_ten_hours_matches_hyphenated_english_evidence(self):
        article = "各エージェントには10時間の計算予算を与えた。"
        evidence = "Each trajectory received a 10-hour compute budget on one NVIDIA H100 80GB GPU."
        self.assertEqual([], pipeline._find_unsupported_numeric_claims(article, evidence))

    def test_vla_range_and_multiplier_normalize_across_dash_styles(self):
        article = "LatentMASはトークン消費を約50〜80%削減し、推論を3〜7倍高速化した。"
        evidence = "LatentMAS uses approximately 50–80 percent fewer tokens and is 3–7x faster."
        self.assertEqual([], pipeline._find_unsupported_numeric_claims(article, evidence))

    def test_low_risk_cargo_lock_audit_is_not_named_fact_failure(self):
        article = (
            "今すぐ動く価値がある実務的な対応として、自社プロジェクトの Cargo.lock に"
            "arrayref 0.3.10 の履歴が残っていないか監査する必要があります。"
        )
        evidence = "The malicious release was arrayref 0.3.10 and proc-macro1 was used in the attack."
        self.assertEqual([], pipeline._find_source_boundary_violations(article, evidence))

    def test_unsupported_product_capability_is_still_rejected(self):
        article = "AcmeCloudはEnterprise Syncを標準でサポートしています。"
        evidence = "AcmeCloud documentation describes basic storage only."
        failures = pipeline._find_source_boundary_violations(article, evidence)
        self.assertTrue(any("Enterprise Sync" in row for row in failures), failures)

    def test_low_risk_action_does_not_whitelist_unknown_product_capability(self):
        article = "AcmeCloud Enterprise Syncを比較検証する必要があります。"
        evidence = "AcmeCloud documentation describes basic storage only."
        failures = pipeline._find_source_boundary_violations(article, evidence)
        self.assertTrue(failures, failures)
        self.assertTrue(any("AcmeCloud" in row or "Sync" in row for row in failures), failures)

    def test_generic_llm_api_phrase_is_not_treated_as_product_name(self):
        article = "監査ではLLM APIの利用を限定して検証します。"
        evidence = "The paper studies latent communication between large language model agents."
        self.assertEqual([], pipeline._find_source_boundary_violations(article, evidence))

    def test_fabricated_personal_experience_is_detected(self):
        article = (
            "現場でAI導入を進める立場として、この研究結果は非常に納得感があります。"
            "日常のコーディング支援でも同じ傾向を感じます。"
        )
        hits = pipeline._find_fabricated_personal_experience(article)
        self.assertTrue(hits)
        state, issues = pipeline.validate_human_appeal_gate({
            "note_draft": article,
            "title_text": "AI自動化の限界をどう見るか？",
            "action_text": "限定PoCで検証する。",
        })
        self.assertEqual("WEAK", state)
        self.assertIn("fabricated_personal_experience", issues)

    def test_editorial_opinion_without_claimed_experience_is_allowed(self):
        article = "私自身の見解としては、今は限定PoCで比較検証するのが妥当だと考えます。"
        self.assertEqual([], pipeline._find_fabricated_personal_experience(article))

    def test_omitted_subject_daily_experience_is_detected(self):
        article = "日常のコーディング支援でも同じ傾向を感じます。"
        self.assertTrue(pipeline._find_fabricated_personal_experience(article))

    def test_reader_rhetorical_experience_question_is_not_fabricated_persona(self):
        article = "設定を変えた途端に別のタスクが失敗した経験はないでしょうか。"
        self.assertEqual([], pipeline._find_fabricated_personal_experience(article))

    def test_arxiv_future_work_does_not_require_release_freshness(self):
        info = {
            "source": "ArXiv",
            "context": "This paper presents a method. Future work is planned.",
            "verification_context": "Authors: Lab. Method: routing algorithm. Benchmark: 30 ms. Future work is planned.",
            "primary_source_resolved": True,
            "source_details": {"authors": ["Lab"]},
            "supplement_candidates": [],
            "checked_urls": set(),
            "evidence_documents": [{"url": "https://arxiv.org/abs/1", "retrieved": True}],
            "freshness_status_available": False,
        }
        info["evidence_metadata"] = pipeline._build_evidence_metadata(info["verification_context"], True)
        result = pipeline.assess_evidence_sufficiency(info)
        self.assertEqual(pipeline.EVIDENCE_SUFFICIENT, result["state"])
        self.assertTrue(result["freshness_scope_limited"])

    def test_explicit_future_release_still_triggers_freshness(self):
        info = {
            "context": "A future version is planned for public release.",
            "primary_url": "https://vendor.example/product",
            "source_name": "Vendor Product",
        }
        with patch.object(pipeline, "_http_get_limited", return_value=(b"<html></html>", "text/html", info["primary_url"])):
            result = pipeline.resolve_followup_freshness(info)
        self.assertTrue(result["triggered"])

    def test_late_pdf_is_not_dropped_when_existing_verification_context_is_full(self):
        old = "landing " * 40000
        new = ("paper body " * 12000) + "\nLIMITATIONS marker-tail-xyz"
        merged = pipeline._merge_verification_context(old, new)
        self.assertLessEqual(len(merged), pipeline.VERIFICATION_CONTEXT_MAX_CHARS)
        self.assertIn("paper body", merged)
        self.assertIn("marker-tail-xyz", merged)

    def test_supplement_pdf_keeps_fact_evidence_beyond_prompt_context(self):
        info = {
            "context": "Abstract only.",
            "verification_context": "Abstract only.",
            "checked_urls": set(),
            "evidence_documents": [{"url": "https://arxiv.org/abs/1", "retrieved": True}],
            "supplement_candidates": [{
                "url": "https://arxiv.org/pdf/1.pdf", "role": "PRIMARY_SOURCE",
                "source_type": "arxiv_pdf", "label": "paper",
            }],
            "deep_source_urls": [],
        }
        raw = ("background text\n" * 1200) + "Each trajectory used a 10-hour compute budget on H100 80GB.\n"
        with patch.object(pipeline, "fetch_pdf_context", return_value=raw):
            pipeline.supplement_source_evidence(info)
        self.assertLessEqual(len(info["context"]), pipeline.SOURCE_CONTEXT_MAX_CHARS)
        self.assertIn("10-hour", info["verification_context"])
        self.assertGreater(info["verification_context_length"], len(info["context"]))
        self.assertEqual([], pipeline._find_unsupported_numeric_claims("計算予算は10時間。", info["verification_context"]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
