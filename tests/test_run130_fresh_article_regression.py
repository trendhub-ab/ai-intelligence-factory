import os, sys, types, unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('GEMINI_API_KEY','test-key')
os.environ.setdefault('GH_PAT','test-token')
os.environ.setdefault('GEMINI_QUOTA_PROJECT_ID','test-project')
try:
    from google import genai  # noqa
except ImportError:
    google_mod = sys.modules.get('google') or types.ModuleType('google')
    genai_mod = types.ModuleType('google.genai')
    errors_mod = types.ModuleType('google.genai.errors')
    class APIError(Exception): pass
    class Client:
        def __init__(self, **_kwargs): self.chats = types.SimpleNamespace(create=lambda **_kw: None)
    genai_mod.Client = Client; errors_mod.APIError = APIError; google_mod.genai = genai_mod
    sys.modules.update({'google':google_mod,'google.genai':genai_mod,'google.genai.errors':errors_mod})
import pipeline


def repo(source, name, url, engagement=1):
    return {
        'source': source,
        'nameWithOwner': name,
        'url': url,
        'primaryUrl': url,
        'description': 'primary source description ' * 10,
        'stargazerCount': engagement,
        'publishedAt': '2026-08-25T00:00:00Z',
        'licenseInfo': {'spdxId':'MIT'} if source == 'GitHub' else None,
    }


class Run130FreshArticleRegressionTests(unittest.TestCase):
    def test_workflow_exposes_fixed_and_fresh_choice(self):
        txt = Path('.github/workflows/regression-test.yml').read_text(encoding='utf-8')
        self.assertIn('article_set:', txt)
        self.assertIn('- fixed', txt)
        self.assertIn('- fresh', txt)
        self.assertIn('REGEN_TEST_ARTICLE_SET: ${{ inputs.article_set }}', txt)

    def test_fresh_selector_excludes_known_and_diversifies_sources(self):
        gh_known = repo('GitHub','known/repo','https://github.com/known/repo',999)
        gh_new = repo('GitHub','new/repo','https://github.com/new/repo',100)
        hn_new = repo('HackerNews','HN New','https://example.com/hn-new',50)
        arxiv_new = repo('ArXiv','Paper New','https://arxiv.org/abs/2608.99999',10)
        ph_new = repo('ProductHunt','PH New','https://example.com/ph-new',5)
        with patch.object(pipeline,'fetch_github_trending',return_value=[gh_known,gh_new]), \
             patch.object(pipeline,'fetch_hackernews_top',return_value=[hn_new]), \
             patch.object(pipeline,'fetch_arxiv_ai_ml',return_value=[arxiv_new]), \
             patch.object(pipeline,'fetch_producthunt_trending',return_value=[ph_new]), \
             patch.object(pipeline,'get_existing_repo_urls',return_value={'https://github.com/known/repo'}), \
             patch.object(pipeline,'legal_safety_gate',return_value=(True,'OK')):
            items = pipeline.get_fresh_regen_test_items(3,'')
        self.assertEqual(3,len(items))
        urls=[x['repo']['url'] for x in items]
        self.assertNotIn(gh_known['url'],urls)
        self.assertEqual(3,len({x['repo']['source'] for x in items}))
        self.assertTrue(all(x['notion_page_id'] is None for x in items))
        self.assertTrue(all('0-API' in x['screening_reason'] for x in items))

    def test_fresh_selector_fails_closed_when_dedupe_read_fails(self):
        with patch.object(pipeline,'fetch_github_trending',return_value=[]), \
             patch.object(pipeline,'fetch_hackernews_top',return_value=[]), \
             patch.object(pipeline,'fetch_arxiv_ai_ml',return_value=[]), \
             patch.object(pipeline,'fetch_producthunt_trending',return_value=[]), \
             patch.object(pipeline,'get_existing_repo_urls',return_value=None):
            self.assertIsNone(pipeline.get_fresh_regen_test_items(3,''))

    def test_fixed_mode_preserves_existing_selector(self):
        fixed=[{'repo':repo('HackerNews','fixed','https://example.com/fixed')}]
        with patch.object(pipeline,'REGEN_TEST_ARTICLE_SET','fixed'), \
             patch.object(pipeline,'get_regen_test_items',return_value=fixed) as old, \
             patch.object(pipeline,'get_fresh_regen_test_items') as fresh, \
             patch.object(pipeline,'GEMINI_BUDGET') as budget, \
             patch.object(pipeline,'legal_safety_gate',return_value=(False,'SKIP')):
            budget.can_request.return_value=True
            pipeline.run_regen_test_mode()
        old.assert_called_once()
        fresh.assert_not_called()

    def test_fresh_mode_uses_fresh_selector(self):
        fresh_items=[{'repo':repo('HackerNews','fresh','https://example.com/fresh')}]
        with patch.object(pipeline,'REGEN_TEST_ARTICLE_SET','fresh'), \
             patch.object(pipeline,'get_fresh_regen_test_items',return_value=fresh_items) as fresh, \
             patch.object(pipeline,'get_regen_test_items') as old, \
             patch.object(pipeline,'GEMINI_BUDGET') as budget, \
             patch.object(pipeline,'legal_safety_gate',return_value=(False,'SKIP')):
            budget.can_request.return_value=True
            pipeline.run_regen_test_mode()
        fresh.assert_called_once()
        old.assert_not_called()

    def test_no_new_gemini_call_site_or_client(self):
        py=Path(pipeline.__file__).read_text(encoding='utf-8')
        self.assertEqual(7,py.count('_generate_via_chat('))
        self.assertEqual(1,py.count('genai.Client('))

if __name__=='__main__': unittest.main()
