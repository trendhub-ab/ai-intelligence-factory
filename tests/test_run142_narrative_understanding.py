import inspect
import unittest
import pipeline


class Run142NarrativeUnderstandingTests(unittest.TestCase):
    def test_prompt_requires_understanding_progression(self):
        prompt = pipeline.build_decision_prompt('x','https://example.com',1,'desc',source_context='primary evidence')
        self.assertIn('読者の疑問 → 普通の言葉で理解 → なぜそうなるか → 何が面白い／困るか → 自分ならどう見る・判断するか', prompt)
        self.assertIn('比喩だけで分かった気にさせず', prompt)
        self.assertIn('技術的な芯や因果が薄ければ完成としない', prompt)

    def test_keyword_gamed_dry_report_is_review(self):
        article='''スマホで困ったことはありませんか。Superpositionも、実は私たちに関係するAIの仕組みです。\n\n## Superpositionで何が変わる？\nSuperpositionは複数の特徴を非直交方向へ表現する方式です。Polysemanticityが発生します。特徴量は活性化空間に分布します。Sparse Autoencoderで辞書表現を抽出します。\n\n## 仕組み\nモデル内部の重みと活性化を解析します。特徴方向を同定します。介入実験で因果関係を評価します。一次資料を確認します。\n\n## 判断\n私なら導入前に一次資料を確認します。'''
        sig=pipeline._reader_experience_signals(article)
        self.assertEqual('REVIEW',sig['reader_delight'])
        self.assertTrue(sig['warm_hook_cold_body'])

    def test_cute_analogy_without_substance_is_review(self):
        article='''押し入れに布団も旅行バッグも扇風機も詰め込んだこと、ありますよね。AIも同じなんです。Superpositionは、AIが頭の中の押し入れを上手に使う方法だと思えば簡単です。\n\n## AIの押し入れはすごい\n斜めに入れたり、隙間に入れたり、まるで収納上手な家族みたいです。なんだか親近感が湧きますよね。\n\n## だから面白い\nAIはたくさん覚えられます。私たちのスマホも容量を工夫します。似ていますよね。\n\n## 判断\n私なら面白い研究として見守ります。'''
        sig=pipeline._reader_experience_signals(article)
        self.assertEqual('REVIEW',sig['reader_delight'])
        self.assertTrue(sig['analogy_substance_thin'])

    def test_genuine_reader_story_is_good(self):
        article='''AIの中を開けば、「ここが英語担当、こっちがコード担当」と分かる。そんなふうに考えたくなりますよね。ところが実際には、1つのニューロンがまるで何役も兼任しているように見えることがあります。\n\n理由の一つがSuperpositionです。収納棚が足りないとき、箱を一列に並べるのではなく向きを変えて隙間まで使う。AIも似た発想で、限られた内部空間に多くの特徴を異なる方向として重ねて表現できます。\n\n効率は上がります。でも解読する側には困ったことが起きます。「このニューロンは何担当？」と1個ずつ見ても答えが出にくいのです。そこで研究者はSparse Autoencoderなどを使い、重なった特徴を人間が読める単位へほどこうとしています。\n\n私なら、この研究を単なる数学パズルではなくAIの安全性に関わる基礎技術として見ます。出力が正しかったことと、なぜ正しい答えになったかを理解できることは別だからです。'''
        sig=pipeline._reader_experience_signals(article)
        self.assertEqual('GOOD',sig['reader_delight'])
        self.assertEqual('GOOD',sig['narrative_understanding_progression'])

    def test_no_new_gemini_call_site(self):
        src=inspect.getsource(pipeline)
        self.assertEqual(7,src.count('_generate_via_chat('))
        self.assertEqual(1,src.count('genai.Client('))


if __name__=='__main__':
    unittest.main()
