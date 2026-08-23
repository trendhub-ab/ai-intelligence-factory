import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault('GEMINI_DEEP_DIVE_CALL_PACING_SECONDS', '0')

try:
    import google.genai  # noqa: F401
except Exception:
    import types
    from unittest.mock import MagicMock
    google_pkg = sys.modules.get('google') or types.ModuleType('google')
    google_pkg.__path__ = getattr(google_pkg, '__path__', [])
    genai_mod = types.ModuleType('google.genai')
    errors_mod = types.ModuleType('google.genai.errors')
    class _Client:
        def __init__(self, *a, **k): self.chats = MagicMock()
    class _APIError(Exception):
        def __init__(self, *a, code=None, **k): super().__init__(*a); self.code = code
    genai_mod.Client = _Client
    errors_mod.APIError = _APIError
    google_pkg.genai = genai_mod
    sys.modules['google'] = google_pkg
    sys.modules['google.genai'] = genai_mod
    sys.modules['google.genai.errors'] = errors_mod

import pipeline


class Run116BoundedFirstPartyDiscoveryTests(unittest.TestCase):
    def _source_info(self, seed):
        return {
            'source': 'GitHub',
            'primary_url': 'https://github.com/mlflow/mlflow',
            'source_details': {'homepage': seed},
            'supplement_candidates': [{'url': seed, 'role': 'PRIMARY_SOURCE'}],
            'verification_context': 'Verified MLflow repository context.',
            'context': 'Verified MLflow repository context.',
            'checked_urls': set(),
            'evidence_documents': [],
            'deep_source_urls': [],
        }

    def test_mlflow_tracking_server_is_recovered_from_versioned_docs_sitemap(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                port = self.server.server_port
                if self.path == '/docs/latest/genai/tracing':
                    body = b'<html><body>Tracing docs without the requested feature.</body></html>'
                    return self._send(200, 'text/html', body)
                if self.path == '/docs/latest/genai/sitemap.xml':
                    return self._send(404, 'text/plain', b'not found')
                if self.path == '/docs/latest/sitemap.xml':
                    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
                    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
                      <url><loc>http://127.0.0.1:{port}/docs/latest/self-hosting/architecture/tracking-server/</loc></url>
                      <url><loc>http://127.0.0.1:{port}/docs/latest/ml/tracking/</loc></url>
                      <url><loc>https://evil.example/tracking-server/</loc></url>
                    </urlset>'''.encode()
                    return self._send(200, 'application/xml', xml)
                if self.path.rstrip('/') == '/docs/latest/self-hosting/architecture/tracking-server':
                    body = b'<html><body><h1>MLflow Tracking Server</h1>Tracking Server is a stand-alone HTTP server.</body></html>'
                    return self._send(200, 'text/html', body)
                if self.path.rstrip('/') == '/docs/latest/ml/tracking':
                    return self._send(200, 'text/html', b'<html><body>MLflow Tracking overview.</body></html>')
                return self._send(404, 'text/plain', b'not found')

            def _send(self, code, ctype, body):
                self.send_response(code)
                self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers(); self.wfile.write(body)
            def log_message(self, *_args): pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            seed = f'http://127.0.0.1:{server.server_port}/docs/latest/genai/tracing'
            info = self._source_info(seed)
            with patch.object(pipeline, '_validate_public_http_url', return_value=None):
                result = pipeline.reconcile_product_review_source_boundary(
                    {}, info, ['source-boundary unsupported named fact: Tracking Server']
                )
            self.assertTrue(result['resolved'])
            self.assertEqual([], result['unresolved_names'])
            self.assertGreaterEqual(result['discovery_fetches'], 1)
            self.assertLessEqual(result['discovery_fetches'], pipeline._PRODUCT_REVIEW_BOUNDARY_MAX_DISCOVERY_FETCHES)
            self.assertLessEqual(result['body_fetches'], pipeline._PRODUCT_REVIEW_BOUNDARY_MAX_BODY_FETCHES)
            self.assertEqual(1, result['documents_added'])
            self.assertEqual(1, len(info['evidence_documents']))
            self.assertIn('tracking-server', info['deep_source_urls'][0])
            self.assertNotIn('evil.example', ' '.join(info['deep_source_urls']))
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_sitemap_candidate_url_does_not_prove_fact_without_exact_phrase_in_body(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                port = self.server.server_port
                if self.path == '/docs/latest/start':
                    return self._send(200, 'text/html', b'<html><body>Start docs.</body></html>')
                if self.path == '/docs/latest/start/sitemap.xml':
                    return self._send(404, 'text/plain', b'no')
                if self.path == '/docs/latest/sitemap.xml':
                    xml = f'<urlset><url><loc>http://127.0.0.1:{port}/docs/latest/tracking-server/</loc></url></urlset>'.encode()
                    return self._send(200, 'application/xml', xml)
                if self.path.rstrip('/') == '/docs/latest/tracking-server':
                    # Tokens/path look perfect, but the full named fact is absent from the body.
                    return self._send(200, 'text/html', b'<html><body>Remote experiment service documentation.</body></html>')
                return self._send(404, 'text/plain', b'no')
            def _send(self, code, ctype, body):
                self.send_response(code); self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self, *_args): pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            seed = f'http://127.0.0.1:{server.server_port}/docs/latest/start'
            info = self._source_info(seed)
            with patch.object(pipeline, '_validate_public_http_url', return_value=None):
                result = pipeline.reconcile_product_review_source_boundary(
                    {}, info, ['source-boundary unsupported named fact: Tracking Server']
                )
            self.assertFalse(result['resolved'])
            self.assertEqual(['Tracking Server'], result['unresolved_names'])
            self.assertEqual([], info['evidence_documents'])
            self.assertEqual([], info['deep_source_urls'])
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_sitemap_third_party_urls_are_never_ranked_or_fetched(self):
        xml = b'''<urlset>
          <url><loc>https://docs.tool.example/docs/tracking-server/</loc></url>
          <url><loc>https://evil.example/docs/tracking-server/</loc></url>
        </urlset>'''
        pages, children = pipeline._parse_boundary_sitemap(xml, 'https://docs.tool.example/sitemap.xml', 'docs.tool.example')
        self.assertEqual([], children)
        self.assertEqual(['https://docs.tool.example/docs/tracking-server/'], pages)

    def test_sitemap_index_following_is_bounded_and_first_party(self):
        calls = []
        def fake_get(url, _types, _limit):
            calls.append(url)
            if url.endswith('/docs/latest/sitemap.xml'):
                return (b'<sitemapindex><sitemap><loc>https://tool.example/docs/latest/sitemap-pages.xml</loc></sitemap>'
                        b'<sitemap><loc>https://evil.example/evil.xml</loc></sitemap></sitemapindex>',
                        'application/xml', url)
            if url.endswith('/docs/latest/sitemap-pages.xml'):
                return (b'<urlset><url><loc>https://tool.example/docs/latest/tracking-server/</loc></url></urlset>',
                        'application/xml', url)
            return b'', 'text/plain', url
        checked=set(); boundary=set()
        with patch.object(pipeline, '_http_get_limited', side_effect=fake_get):
            out = pipeline._discover_boundary_candidate_urls(
                ['https://tool.example/docs/latest/start'], ['Tracking Server'], boundary, checked
            )
        self.assertLessEqual(out['discovery_fetches'], pipeline._PRODUCT_REVIEW_BOUNDARY_MAX_DISCOVERY_FETCHES)
        self.assertIn('https://tool.example/docs/latest/tracking-server/', out['urls'])
        self.assertFalse(any('evil.example' in u for u in calls))

    def test_run_product_reviews_reconciles_mlflow_fixture_without_second_gemini(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                port = self.server.server_port
                if self.path == '/docs/latest/genai/tracing':
                    return self._send(200, 'text/html', b'<html><body>Tracing overview.</body></html>')
                if self.path == '/docs/latest/genai/sitemap.xml':
                    return self._send(404, 'text/plain', b'no')
                if self.path == '/docs/latest/sitemap.xml':
                    xml = f'<urlset><url><loc>http://127.0.0.1:{port}/docs/latest/self-hosting/architecture/tracking-server/</loc></url></urlset>'.encode()
                    return self._send(200, 'application/xml', xml)
                if self.path.rstrip('/') == '/docs/latest/self-hosting/architecture/tracking-server':
                    return self._send(200, 'text/html', b'<html><body><h1>MLflow Tracking Server</h1>Tracking Server is a stand-alone HTTP server.</body></html>')
                return self._send(404, 'text/plain', b'no')
            def _send(self, code, ctype, body):
                self.send_response(code); self.send_header('Content-Type', ctype)
                self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
            def log_message(self, *_args): pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            seed = f'http://127.0.0.1:{server.server_port}/docs/latest/genai/tracing'
            info = self._source_info(seed)
            state = {
                'canonical_entity_id': 'github:mlflow/mlflow', 'technology_name': 'mlflow/mlflow',
                'primary_url': 'https://github.com/mlflow/mlflow', 'sources': ['GitHub'],
                'screening_score': 85, 'screening_reason': 'MLOps', 'source_summary': 'legacy',
            }
            evidence = {
                'state': pipeline.EVIDENCE_SUFFICIENT, 'decision_scope_safe': True,
                'blocking_missing': [], 'limitations': [], 'checks': {'primary_source_resolved': True},
            }
            payload = {
                'category': 'DEVTOOLS', 'adoption_score': 80,
                'components': {
                    'Evidence Quality': 20, 'Production Maturity': 20, 'Use-case Utility / Fit': 16,
                    'Reliability / Security Risk': 12, 'Integration / Migration Feasibility': 8,
                    'Ecosystem / Support Durability': 4,
                },
                'adoption_status': 'TEST', 'evidence_confidence': 'HIGH',
                'production_readiness': 'HIGH', 'main_risk': 'Tracking Serverの運用設計が必要。',
                'best_for': 'ML運用チーム。', 'avoid_for': '運用基盤が不要な単発処理。',
                'short_rationale': 'Tracking Serverを含む公式一次情報で確認できる。',
                'next_review_days': 30,
            }
            call_model = MagicMock(return_value=(SimpleNamespace(text=json.dumps(payload, ensure_ascii=False), parsed=None), 'gemini-test'))
            persist = MagicMock(side_effect=[
                {'saved': False, 'reason': 'assessment_invalid', 'failures': ['source-boundary unsupported named fact: Tracking Server']},
                {'saved': True, 'page_id': None},
            ])
            pr_budget = pipeline.ProductReviewRequestBudget(2)
            global_budget = pipeline.GeminiBudget(10, 2, 2)
            with patch.object(pipeline, '_validate_public_http_url', return_value=None), \
                 patch.object(pipeline, 'PRODUCT_REVIEW_MAX_PER_RUN', 1), \
                 patch.object(pipeline, 'select_product_review_candidates', return_value=[state]), \
                 patch.object(pipeline, 'prepare_source_context', return_value=info), \
                 patch.object(pipeline, 'assess_evidence_sufficiency', return_value=evidence), \
                 patch.object(pipeline, '_primary_source_authority_failures', return_value=[]), \
                 patch.object(pipeline, '_model_pool_has_session_candidate', return_value=True), \
                 patch.object(pipeline, '_call_product_review_pool', call_model), \
                 patch.object(pipeline, 'persist_decision_intelligence_assessment', persist), \
                 patch.object(pipeline, 'PRODUCT_REVIEW_REQUEST_BUDGET', pr_budget), \
                 patch.object(pipeline, 'GEMINI_BUDGET', global_budget):
                result = pipeline.run_product_reviews()
            self.assertEqual(1, result['boundary_reconciliation_attempted'])
            self.assertEqual(1, result['boundary_reconciled'])
            self.assertEqual(1, result['saved'])
            self.assertEqual(1, call_model.call_count)
            self.assertEqual(2, persist.call_count)
            self.assertTrue(any('tracking-server' in u for u in info['deep_source_urls']))
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_body_fetch_ceiling_holds_with_many_high_scoring_candidates(self):
        candidates = [f'https://tool.example/docs/tracking-server/{i}' for i in range(50)]
        with patch.object(pipeline, '_fetch_boundary_html', return_value=('unrelated first party docs', [], 'https://tool.example/docs')) as fetch, \
             patch.object(pipeline, '_discover_boundary_candidate_urls', return_value={
                 'urls': candidates[:pipeline._PRODUCT_REVIEW_BOUNDARY_MAX_RANKED_CANDIDATES],
                 'discovery_fetches': 1, 'discovered_urls': 50, 'rejected_urls': []
             }):
            info = {
                'source': 'GitHub', 'primary_url': 'https://github.com/org/tool',
                'source_details': {'homepage': 'https://tool.example/docs'},
                'supplement_candidates': [{'url': 'https://tool.example/docs', 'role': 'PRIMARY_SOURCE'}],
                'verification_context': 'verified', 'context': 'verified',
                'checked_urls': set(), 'evidence_documents': [], 'deep_source_urls': [],
            }
            result = pipeline.reconcile_product_review_source_boundary(
                {}, info, ['source-boundary unsupported named fact: Tracking Server']
            )
        self.assertFalse(result['resolved'])
        self.assertLessEqual(result['body_fetches'], pipeline._PRODUCT_REVIEW_BOUNDARY_MAX_BODY_FETCHES)
        self.assertLessEqual(fetch.call_count, pipeline._PRODUCT_REVIEW_BOUNDARY_MAX_BODY_FETCHES)
        self.assertLessEqual(result['ranked_candidates_considered'], pipeline._PRODUCT_REVIEW_BOUNDARY_MAX_RANKED_CANDIDATES)

    def test_body_fetch_hard_cap_is_enforced_even_when_ranked_list_has_more(self):
        candidates = [f'https://tool.example/docs/tracking-server/{i}' for i in range(4)]
        info = {
            'source': 'GitHub', 'primary_url': 'https://github.com/org/tool',
            'source_details': {'homepage': 'https://tool.example/docs'},
            'supplement_candidates': [{'url': 'https://tool.example/docs', 'role': 'PRIMARY_SOURCE'}],
            'verification_context': 'verified', 'context': 'verified',
            'checked_urls': set(), 'evidence_documents': [], 'deep_source_urls': [],
        }
        with patch.object(pipeline, '_PRODUCT_REVIEW_BOUNDARY_MAX_BODY_FETCHES', 3), \
             patch.object(pipeline, '_fetch_boundary_html', return_value=('unrelated docs', [], 'https://tool.example/docs')) as fetch, \
             patch.object(pipeline, '_discover_boundary_candidate_urls', return_value={
                 'urls': candidates, 'discovery_fetches': 1, 'discovered_urls': 4, 'rejected_urls': []
             }):
            result = pipeline.reconcile_product_review_source_boundary(
                {}, info, ['source-boundary unsupported named fact: Tracking Server']
            )
        self.assertFalse(result['resolved'])
        self.assertEqual(3, result['body_fetches'])
        self.assertEqual(3, fetch.call_count)

    def test_discovery_xml_never_enters_evidence_documents(self):
        info = {
            'source': 'GitHub', 'primary_url': 'https://github.com/org/tool',
            'source_details': {'homepage': 'https://tool.example/docs'},
            'supplement_candidates': [{'url': 'https://tool.example/docs', 'role': 'PRIMARY_SOURCE'}],
            'verification_context': 'verified', 'context': 'verified',
            'checked_urls': set(), 'evidence_documents': [], 'deep_source_urls': [],
        }
        with patch.object(pipeline, '_fetch_boundary_html', return_value=('no support', [], 'https://tool.example/docs')), \
             patch.object(pipeline, '_discover_boundary_candidate_urls', return_value={
                 'urls': [], 'discovery_fetches': 1, 'discovered_urls': 1, 'rejected_urls': []
             }):
            result = pipeline.reconcile_product_review_source_boundary(
                {}, info, ['source-boundary unsupported named fact: Tracking Server']
            )
        self.assertFalse(result['resolved'])
        self.assertEqual([], info['evidence_documents'])
        self.assertEqual([], info['deep_source_urls'])

    def test_named_fact_support_requires_token_boundary_not_serverless_substring(self):
        self.assertTrue(pipeline._boundary_text_supports_name('MLflow Tracking-Server is available.', 'Tracking Server'))
        self.assertFalse(pipeline._boundary_text_supports_name('A tracking serverless architecture is available.', 'Tracking Server'))

    def test_current_mlflow_official_path_scores_as_topical_without_hardcoding_mlflow(self):
        url = 'https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/'
        score = pipeline._boundary_candidate_score(url, ['Tracking Server'])
        self.assertGreaterEqual(score, 60)
        # A generic unrelated docs page should rank lower.
        other = pipeline._boundary_candidate_score('https://mlflow.org/docs/latest/genai/tracing/', ['Tracking Server'])
        self.assertGreater(score, other)


if __name__ == '__main__':
    unittest.main()
