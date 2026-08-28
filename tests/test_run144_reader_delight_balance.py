import inspect
import unittest
import pipeline


DEBUG_KEYS = [
    'reader_delight','reader_delight_positive_signals','reader_delight_overclaim','repetitive_insight',
    'narrative_understanding_progression','narrative_progression_hits','causal_explanation_hits',
    'factual_substance_hits','reader_proximity','reader_proximity_moment_count','plain_language_bridge',
    'opening_non_engineer_access','article_specific_angle','warm_hook_cold_body','analogy_substance_thin',
    'enjoyment_issues','accessibility_issues'
]

def debug(name, sig):
    print(name, {k:sig.get(k) for k in DEBUG_KEYS})


class Run144ReaderDelightBalanceTests(unittest.TestCase):
    def test_calm_security_article_can_be_good_without_chatty_markers(self):
        article = '''AIエージェントに社内システムを触らせるとき、便利さより先に気になることがあります。「どこまで触らせる？」です。人に合鍵を渡すとき、家じゅう全部の鍵を束で渡さないのと同じです。\n\n最小権限は、そのAIが今の仕事に必要な範囲だけアクセスできるようにする考え方です。権限を狭くすると、誤操作や侵害が起きたときの被害範囲も狭めやすくなります。ただし、権限を絞れば安全が保証されるわけではありません。ログ監視や承認フローなど別の対策も必要です。\n\n私なら、まず機密情報を扱わない作業だけで試し、実際に必要だった権限を記録してから範囲を広げます。便利さを先に最大化するより、必要な鍵を一つずつ増やす方が現実的です。'''
        sig = pipeline._reader_experience_signals(article); debug('security', sig)
        self.assertEqual('GOOD', sig['reader_delight'])

    def test_hardware_article_can_be_good_without_proximity_catchphrase(self):
        article = '''AI向けチップのニュースで大きな性能数字を見ると、「前より速いのは分かった。でも自分には何が変わるの？」となりがちです。\n\nたとえば演算性能が上がっても、モデルがメモリからデータを待つ時間が長ければ、その数字をそのまま体感速度にはできません。だからチップを見るときは演算性能だけでなく、メモリ容量や帯域、消費電力、実際に使うモデルでのベンチマークまで一緒に見る必要があります。\n\n私なら“最大何PFLOPS”だけでは判断しません。自分のモデルが載るか、電力と冷却を含めて運用できるか、既存環境より総コストが下がるかまで揃って初めて比較対象にします。'''
        sig = pipeline._reader_experience_signals(article); debug('hardware', sig)
        self.assertEqual('GOOD', sig['reader_delight'])

    def test_overconfident_smooth_story_remains_review(self):
        article = '''AIの中身を開けば答えが見える、と思いたくなりますよね。ところがSuperpositionのせいで、意味は一つのニューロンにきれいに収まりません。\n\n理由はシンプルです。モデルは限られた空間を効率よく使いたい。そのため複数の特徴を重ねます。すると解読が難しくなる。そこで研究者は特徴をほどく方法を使います。\n\nだからこの研究はAI安全性にとても重要です。内部を完全に理解できれば、危険な挙動も事前に見抜けます。私なら企業導入ではこの技術を必須条件にします。'''
        sig = pipeline._reader_experience_signals(article); debug('overclaim', sig)
        self.assertEqual('REVIEW', sig['reader_delight'])
        self.assertTrue(sig['reader_delight_overclaim'])

    def test_repetitive_insight_remains_review(self):
        article = '''AIの中身を読むのは、意外と難しいんです。Superpositionで複数の特徴が重なるからです。だから一つのニューロンを見ても意味が分かりません。\n\nなぜ分からないのか。複数の特徴が重なるからです。すると一つのニューロンだけでは意味が決まりません。そこで特徴を分けて読む必要があります。\n\n何が困るのか。複数の特徴が重なるので、内部を読むのが難しくなります。だから研究者はSparse Autoencoderなどを使います。\n\n私ならこの研究を重要だと見ます。'''
        sig = pipeline._reader_experience_signals(article); debug('repetitive', sig)
        self.assertEqual('REVIEW', sig['reader_delight'])

    def test_no_new_gemini_call_site(self):
        src = inspect.getsource(pipeline)
        self.assertEqual(7, src.count('_generate_via_chat('))
        self.assertEqual(1, src.count('genai.Client('))


if __name__ == '__main__':
    unittest.main()
