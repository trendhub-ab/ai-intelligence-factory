import unittest
from unittest import mock

import run364_historical_ready_rebase as r


class Run364Tests(unittest.TestCase):
    def test_allowlist_is_exactly_eight(self):
        self.assertEqual(8, len(r.ALLOWLIST))
        self.assertEqual(8, len({v['manuscript_sha256'] for v in r.ALLOWLIST.values()}))

    def test_classify_accepts_only_exact_historical_body_and_policy(self):
        expected = next(iter(r.ALLOWLIST.values()))
        body = 'exact body bytes\n'
        sha = r.contract.manuscript_sha256(body)
        expected = {**expected, 'manuscript_sha256': sha}
        caption = (
            r.contract.READY_CAPTION_PREFIX
            + f"contract={r.contract.CONTRACT_ID}|policy_sha256={expected['historical_policy_sha256']}|manuscript_sha256={sha}"
        )
        block = {'type':'code','code':{'rich_text':[{'plain_text':body}], 'caption':[{'plain_text':caption}]}}
        with mock.patch.object(r.sync, '_code_body', return_value=body), mock.patch.object(r.sync, '_code_caption', return_value=caption):
            d = r.classify_page([block], expected)
        self.assertEqual('eligible', d.status)
        self.assertEqual(body, d.body)

    def test_classify_blocks_body_sha_drift(self):
        expected = next(iter(r.ALLOWLIST.values()))
        body = 'changed body'
        caption = (
            r.contract.READY_CAPTION_PREFIX
            + f"contract={r.contract.CONTRACT_ID}|policy_sha256={expected['historical_policy_sha256']}|manuscript_sha256={expected['manuscript_sha256']}"
        )
        block = {'type':'code','code':{}}
        with mock.patch.object(r.sync, '_code_body', return_value=body), mock.patch.object(r.sync, '_code_caption', return_value=caption):
            d = r.classify_page([block], expected)
        self.assertEqual('blocked', d.status)

    def test_current_code_block_round_trips_body(self):
        body = ('abc日本語\n' * 700) + 'tail'
        block = r._current_code_block(body)
        pieces = [x['text']['content'] for x in block['code']['rich_text']]
        self.assertEqual(body, ''.join(pieces))
        caption = block['code']['caption'][0]['text']['content']
        self.assertTrue(r.contract.is_current_ready_block(body, caption))

    def test_apply_confirmation_is_hard_required(self):
        with self.assertRaises(ValueError):
            r.run(mode='apply', confirmation='wrong')

    def test_batch_drift_prevents_any_patch(self):
        class Resp:
            status_code = 200
            text = ''
            def __init__(self, payload=None): self._payload = payload or {}
            def json(self): return self._payload

        entries = list(r.ALLOWLIST.items())
        def req(method, url, **kwargs):
            self.assertEqual('GET', method)
            page_id = url.rsplit('/',1)[-1]
            e = r.ALLOWLIST[page_id]
            state = {'title':e['title'], 'source':e['source'], 'primary_url':e['primary_url'], 'eyecatch_url':'https://img'}
            if page_id == entries[0][0]: state['title'] += ' DRIFT'
            return Resp({'id':page_id, '_state':state})

        def state(payload): return payload['_state']
        with mock.patch.object(r.sync, 'NOTION_API_KEY', 'x'), \
             mock.patch.object(r, '_verify_allowlist_history'), \
             mock.patch.object(r.sync, '_request', side_effect=req) as request, \
             mock.patch.object(r.sync, '_source_state', side_effect=state), \
             mock.patch.object(r.sync, '_block_children', return_value=[]):
            result = r.run(mode='dry_run')
        self.assertTrue(result['batch_fail_closed'])
        self.assertGreaterEqual(result['blocked'], 1)
        self.assertTrue(all(c.args[0] == 'GET' for c in request.call_args_list))


if __name__ == '__main__':
    unittest.main()
