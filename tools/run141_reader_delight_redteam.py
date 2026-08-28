import json
import pipeline

CASES = {
    # 1. Detector keyword gaming: one rhetorical hook + smartphone + named topic,
    # but the body is still a dry report.
    "keyword_gamed_dry_report": '''スマホで困ったことはありませんか。Superpositionも、実は私たちに関係するAIの仕組みです。\n\n## Superpositionで何が変わる？\nSuperpositionは複数の特徴を非直交方向へ表現する方式です。Polysemanticityが発生します。特徴量は活性化空間に分布します。Sparse Autoencoderで辞書表現を抽出します。\n\n## 仕組み\nモデル内部の重みと活性化を解析します。特徴方向を同定します。介入実験で因果関係を評価します。一次資料を確認します。\n\n## 判断\n私なら導入前に一次資料を確認します。''',

    # 2. Warm opening followed by a long cold dump.
    "warm_hook_then_technical_dump": '''AIに「頭の中を見せて」と頼めたら面白そうですよね。Superpositionは、その頭の中を読むときに出会う厄介な現象です。\n\n## 中身を見る\n''' + ('活性化ベクトル、特徴基底、非直交表現、辞書学習、スパース符号化、干渉項、再構成誤差を評価します。' * 8) + '''\n\n## 判断\n難しそうですが、一次資料の条件を確認して判断します。''',

    # 3. Friendly headings and questions, but mechanical listicle/report prose.
    "friendly_listicle_shell": '''「AIの脳内って、どうなっているんだろう？」と気になったことはありませんか。Superpositionは、その疑問に関係する話です。\n\n## まず知っておきたい3つ\n第一に、特徴量です。第二に、非直交性です。第三に、多義性です。これらを理解する必要があります。\n\n## ここが面白いところです\n重要なポイントは3つあります。特徴量、活性化、辞書学習です。つまり、内部表現を解析することが重要です。\n\n## 私ならこうします\n一次資料を確認し、比較検討します。''',

    # 4. Cute analogy dominates; understanding feels easy but factual core is nearly absent.
    "cute_analogy_substance_thin": '''押し入れに布団も旅行バッグも扇風機も詰め込んだこと、ありますよね。AIも同じなんです。Superpositionは、AIが頭の中の押し入れを上手に使う方法だと思えば簡単です。\n\n## AIの押し入れはすごい\n斜めに入れたり、隙間に入れたり、まるで収納上手な家族みたいです。なんだか親近感が湧きますよね。\n\n## だから面白い\nAIはたくさん覚えられます。私たちのスマホも容量を工夫します。似ていますよね。\n\n## 判断\n私なら面白い研究として見守ります。''',

    # 5. Generic personal-relevance tokens injected without a real bridge.
    "self_relevance_token_stuffing": '''仕事、生活、スマホ、家族、買い物。AIはもう私たちに関係していますよね。今回のSuperpositionも自分に関係する重要な話です。\n\n## Superposition\n特徴が非直交ベクトルとして重畳されます。ニューロンはpolysemanticになります。高次元幾何で分解します。\n\n## 生活への影響\n私たちの仕事や生活に関係します。スマホやPCを使う人にも関係します。\n\n## 判断\nだから一次資料を確認する必要があります。''',

    # 6. Question-heavy but each question is superficial; designed to stay below overuse threshold.
    "rhetorical_question_gaming": '''AIの中身を見たいと思いませんか。どうやって覚えているのか気になりませんか。Superpositionという言葉、難しそうではありませんか。\n\n## 仕組み\n特徴を非直交方向に格納します。Polysemanticityが生じます。Sparse Autoencoderで分解します。\n\n## 意味\n面白いと思いませんか。私たちにも関係しそうではありませんか。\n\n## 判断\n一次資料を確認します。''',

    # 7. Strong article-specific angle and readable language, but no narrative progression.
    "readable_but_flat_fact_cards": '''AIの1個のニューロンが「英語」と「コード」の両方に反応すると聞くと、不思議に感じませんか。これがSuperpositionを考える入口です。\n\n## Superposition\nAIは限られた次元に多くの特徴を重ねて表現できます。収納棚を斜めに使うようなイメージです。\n\n## Polysemanticity\n1つのニューロンが複数の意味に関係します。名前は難しそうですが、役割が一対一ではないという話です。\n\n## Sparse Autoencoder\n重なった特徴を分けて読みやすくする方法の一つです。\n\n## 判断\n私なら研究動向を追います。''',

    # Positive control.
    "genuine_reader_story": '''AIの中を開けば、「ここが英語担当、こっちがコード担当」と分かる。そんなふうに考えたくなりますよね。ところが実際には、1つのニューロンがまるで何役も兼任しているように見えることがあります。\n\n理由の一つがSuperpositionです。収納棚が足りないとき、箱を一列に並べるのではなく向きを変えて隙間まで使う。AIも似た発想で、限られた内部空間に多くの特徴を異なる方向として重ねて表現できます。\n\n効率は上がります。でも解読する側には困ったことが起きます。「このニューロンは何担当？」と1個ずつ見ても答えが出にくいのです。そこで研究者はSparse Autoencoderなどを使い、重なった特徴を人間が読める単位へほどこうとしています。\n\n私なら、この研究を単なる数学パズルではなくAIの安全性に関わる基礎技術として見ます。出力が正しかったことと、なぜ正しい答えになったかを理解できることは別だからです。''',
}

result = {}
for name, article in CASES.items():
    s = pipeline._reader_experience_signals(article)
    result[name] = {
        "reader_delight": s.get("reader_delight"),
        "opening_non_engineer_access": s.get("opening_non_engineer_access"),
        "reader_proximity": s.get("reader_proximity"),
        "conversational_warmth": s.get("conversational_warmth"),
        "plain_language_bridge": s.get("plain_language_bridge"),
        "article_specific_angle": s.get("article_specific_angle"),
        "news_relevance": s.get("news_relevance"),
        "reader_temperature_rhythm": s.get("reader_temperature_rhythm"),
        "implementation_detail_load": s.get("implementation_detail_load"),
        "enjoyment_issues": s.get("enjoyment_issues"),
        "accessibility_issues": s.get("accessibility_issues"),
    }

bad_cases = [k for k in CASES if k != "genuine_reader_story"]
escapes = [k for k in bad_cases if result[k]["reader_delight"] == "GOOD"]
false_positive = result["genuine_reader_story"]["reader_delight"] != "GOOD"
summary = {
    "adversarial_cases": len(bad_cases),
    "escaped_as_good": escapes,
    "escape_count": len(escapes),
    "good_control_false_positive": false_positive,
    "redteam_pass": not escapes and not false_positive,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
print("RUN141_SUMMARY=" + json.dumps(summary, ensure_ascii=False))
# Deliberately fail CI when a crafted bad article escapes as GOOD or the positive control is rejected.
raise SystemExit(0 if summary["redteam_pass"] else 1)
