import unittest
from unittest import mock

import run362_ready_provenance_audit as p
import run365_historical_ready_rebase as r


class Run365Tests(unittest.TestCase):
    def test_run362_requires_valid_body_hash_for_historical_match(self):
        history = {'policy': {'commit': 'abc'}}
        meta = {'caption_policy_sha256': 'policy', 'body_sha_valid': False}
        self.assertFalse(p._is_historical_main_ready(meta, history))
        meta['body_sha_valid'] = True
        self.assertTrue(p._is_historical_main_ready(meta, history))

    def test_allowlist_is_exactly_seven_and_false_positive_is_excluded(self):
        self.assertEqual(7, len(r.ALLOWLIST))
        self.assertEqual(r.EXPECTED_ALLOWLIST_FINGERPRINT, r._allowlist_fingerprint())
        self.assertNotIn(r.EXCLUDED_FALSE_POSITIVE['page_id'], r.ALLOWLIST)

    def test_apply_confirmation_is_hard_required(self):
        with self.assertRaises(ValueError):
            r.run(mode='apply', confirmation='wrong')

    def test_dry_run_never_patches(self):
        class Resp:
            status_code = 200
            text = ''
            def __init__(self, payload=None): self._payload = payload or {}
            def json(self): return self._payload

        def req(method, url, **kwargs):
            self.assertEqual('GET', method)
            page_id = url.rsplit('/', 1)[-1]
            expected = r.ALLOWLIST[page_id]
            state = {
                'title': expected['title'],
                'source': expected['source'],
                'primary_url': expected['primary_url'],
                'eyecatch_url': 'https://img.example/x.png',
            }
            return Resp({'id': page_id, '_state': state})

        def state(payload): return payload['_state']
        eligible = r.base.Decision('eligible', 'ok', body='body', manuscript_sha256='sha', historical_policy_sha256='policy')
        with mock.patch.object(r.sync, 'NOTION_API_KEY', 'x'), \
             mock.patch.object(r, '_verify_allowlist_history'), \
             mock.patch.object(r.sync, '_request', side_effect=req) as request, \
             mock.patch.object(r.sync, '_source_state', side_effect=state), \
             mock.patch.object(r.sync, '_block_children', return_value=[]), \
             mock.patch.object(r.base, 'classify_page', return_value=eligible):
            result = r.run(mode='dry_run')
        self.assertEqual(7, result['eligible'])
        self.assertEqual(0, result['blocked'])
        self.assertEqual(0, result['applied'])
        self.assertTrue(all(call.args[0] == 'GET' for call in request.call_args_list))

    def test_one_drift_fails_closed_for_entire_batch(self):
        class Resp:
            status_code = 200
            text = ''
            def __init__(self, payload=None): self._payload = payload or {}
            def json(self): return self._payload

        first = next(iter(r.ALLOWLIST))
        def req(method, url, **kwargs):
            self.assertEqual('GET', method)
            page_id = url.rsplit('/', 1)[-1]
            expected = r.ALLOWLIST[page_id]
            state = {
                'title': expected['title'] + (' DRIFT' if page_id == first else ''),
                'source': expected['source'],
                'primary_url': expected['primary_url'],
                'eyecatch_url': 'https://img.example/x.png',
            }
            return Resp({'id': page_id, '_state': state})

        def state(payload): return payload['_state']
        eligible = r.base.Decision('eligible', 'ok', body='body', manuscript_sha256='sha', historical_policy_sha256='policy')
        with mock.patch.object(r.sync, 'NOTION_API_KEY', 'x'), \
             mock.patch.object(r, '_verify_allowlist_history'), \
             mock.patch.object(r.sync, '_request', side_effect=req), \
             mock.patch.object(r.sync, '_source_state', side_effect=state), \
             mock.patch.object(r.sync, '_block_children', return_value=[]), \
             mock.patch.object(r.base, 'classify_page', return_value=eligible):
            result = r.run(mode='dry_run')
        self.assertTrue(result['batch_fail_closed'])
        self.assertEqual(1, result['blocked'])
        self.assertEqual(0, result['applied'])


if __name__ == '__main__':
    unittest.main()
