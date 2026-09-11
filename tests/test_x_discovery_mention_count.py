import unittest
from x_discovery.dedupe import cluster_candidates
from x_discovery.normalize import normalize_post
from x_discovery.handoff import build_primary_resolution_queue
from x_discovery.factory_adapter import adapt_primary_resolution_queue


class MentionCountTests(unittest.TestCase):
    def signal(self,post_id,urls,author='one'):
        return normalize_post({'id':post_id,'username':author,'text':' '.join(urls),
                               'tweet_url':f'https://x.com/{author}/status/{post_id}'},
                              provider='fixture',discovered_at='offline')

    def test_scheme_aliases_count_once_in_both_orders(self):
        for urls in [('http://github.com/example/repo','https://github.com/example/repo'),
                     ('https://github.com/example/repo','http://github.com/example/repo')]:
            with self.subTest(urls=urls):
                candidates=cluster_candidates([self.signal('1',urls)])
                self.assertEqual(len(candidates),1)
                self.assertEqual(candidates[0].mention_count,1)
                self.assertEqual(candidates[0].canonical_url,'https://github.com/example/repo')
                adapted=adapt_primary_resolution_queue(build_primary_resolution_queue(candidates))
                self.assertEqual(adapted['items'][0]['mention_count'],1)
                self.assertFalse(adapted['factory_write'])

    def test_repeated_signal_is_idempotent(self):
        a=self.signal('1',['http://github.com/example/repo'])
        b=self.signal('1',['https://github.com/example/repo'])
        c=cluster_candidates([a,a,b,b])[0]
        self.assertEqual(c.mention_count,1)
        self.assertEqual(c.post_ids,['1'])
        self.assertEqual(c.canonical_url,'https://github.com/example/repo')

    def test_distinct_posts_same_author_count_separately(self):
        c=cluster_candidates([self.signal('1',['http://github.com/example/repo','https://github.com/example/repo']),
                              self.signal('2',['https://github.com/example/repo'])])[0]
        self.assertEqual(c.mention_count,2)
        self.assertEqual(c.authors,['one'])
        self.assertEqual(c.post_ids,['1','2'])

    def test_distinct_targets_each_receive_a_mention(self):
        cs=cluster_candidates([self.signal('1',['https://github.com/example/a','https://github.com/example/b'])])
        self.assertEqual(len(cs),2)
        self.assertEqual([c.mention_count for c in cs],[1,1])

    def test_ranking_uses_posts_not_url_count(self):
        cs=cluster_candidates([self.signal('1',['http://github.com/example/a','https://github.com/example/a']),
                               self.signal('2',['https://github.com/example/z']),
                               self.signal('3',['https://github.com/example/z'])])
        self.assertEqual(cs[0].canonical_url,'https://github.com/example/z')
        self.assertEqual([c.mention_count for c in cs],[2,1])

if __name__=='__main__':unittest.main()
