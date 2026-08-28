import json
import pipeline

# Run143: stronger 0-API adversarial set for Reader Delight / Narrative Understanding.
# Bad cases are intentionally polished enough to fool shallow heuristics.
BAD = {
    "polished_but_low_information": '''AIの中には、私たちが思っている以上に面白い仕組みがあります。たとえばSuperposition。難しそうな名前ですが、限られた場所をうまく使う工夫だと考えると少し身近になりますよね。\n\nなぜそんな工夫が必要なのか。AIは多くのことを扱うため、内部の表現を効率よく使います。その結果、ひとつの場所が複数の役割を持つことがあります。\n\nだから研究者は中身を詳しく調べています。これはAIを理解するうえで大切です。私なら今後の研究を注視します。''',

    "excellent_first_half_then_report_dump": '''AIのニューロンに名札が付いていて、「私は英語担当です」と自己紹介してくれたら楽ですよね。ところが実際にはそう単純ではありません。Superpositionでは、限られた内部空間に複数の特徴が重なって表現されます。\n\n収納棚を斜めに使うようなものだと考えると、なぜ効率が上がるのか少し見えてきます。効率が上がる一方で、「このニューロンは何担当？」と一個ずつ読むのが難しくなる。ここまでは直感的です。\n\n## 技術詳細\n活性化空間における非直交特徴方向を同定します。辞書学習により疎な特徴基底を推定します。再構成損失を最小化します。特徴間干渉を評価します。介入実験を実施します。因果効果を測定します。重み行列を解析します。局所回路を同定します。\n\n## 判断\n一次資料を確認して判断します。''',

    "fun_short_but_no_caveat_or_decision": '''AIの頭の中には、まるで一人で何役もこなす役者のようなニューロンがあります。面白いですよね。Superpositionは、限られた舞台にたくさんの役を重ねる仕組みです。\n\nだから1つのニューロンだけ見ても意味が分かりにくい。そこでSparse Autoencoderなどを使って、重なった特徴をほどこうとします。難しい数学の話なのに、やっていることは「誰が何役なのか整理する」作業だと思うと急に身近になります。''',

    "smooth_narrative_but_no_real_evidence": '''AIの中身を開けば答えが見える、と思いたくなりますよね。ところがSuperpositionのせいで、意味は一つのニューロンにきれいに収まりません。\n\n理由はシンプルです。モデルは限られた空間を効率よく使いたい。そのため複数の特徴を重ねます。すると解読が難しくなる。そこで研究者は特徴をほどく方法を使います。\n\nだからこの研究はAI安全性にとても重要です。内部を完全に理解できれば、危険な挙動も事前に見抜けます。私なら企業導入ではこの技術を必須条件にします。''',

    "overconfident_storytelling": '''AIの頭の中は、散らかった押し入れに似ています。何がどこにあるか分からない。でもSuperpositionの仕組みを解けば、その押し入れを完全に整理できます。\n\nなぜなら、重なった特徴をSparse Autoencoderで分離すれば、各特徴の意味が一つずつ明らかになるからです。するとモデルがなぜ答えたのかも説明できます。\n\nだからMechanistic Interpretabilityが完成すればAIのブラックボックス問題は解決します。私なら今のうちに導入します。''',

    "topic_shift_security_dry": '''AIエージェントに社内システムを触らせるとき、「全部の権限を渡して大丈夫？」と不安になりますよね。そこで最小権限という考え方が効きます。必要な鍵だけ渡すイメージです。\n\n理由は、権限が広いほど事故時の影響範囲が広がるためです。だからツールごとにアクセス範囲を制限します。\n\n実装ではOAuth scope、RBAC、ABAC、IAM policy、service account、token rotation、secret manager、network policy、audit log、SIEM連携を設定します。各設定値を確認し、運用ルールを定義します。\n\n私なら段階導入します。''',

    "hardware_specs_with_friendly_shell": '''新しいAI向けチップを見ると、「結局どれくらい速いの？」が気になりますよね。今回の製品は高速化を狙ったものです。\n\n理由はメモリ帯域と演算性能を高めたからです。だから大規模モデルにも向きます。ここまでは分かりやすい話です。\n\n仕様はFP16 1.8PFLOPS、HBM 192GB、帯域6.4TB/s、TDP 1200W、PCIe Gen7、NVLink相当接続、ラック密度、冷却要件、電源要件を確認します。\n\n私なら性能を比較して導入判断します。''',

    "saas_marketing_narrative": '''会議のたびに議事録を書くの、地味に面倒ですよね。今回のAI SaaSは、その作業を自動化します。\n\n仕組みは簡単です。音声を文字にして、AIが要点をまとめます。だから会議後の作業時間を減らせます。さらに検索もできるので、過去の話も見つけやすくなります。\n\nつまり仕事がかなり楽になります。チームの生産性も上がります。私ならすぐ全社導入します。''',

    "analogy_then_false_equivalence": '''Superpositionは、スマホの圧縮ファイルに似ています。複数のデータを小さくまとめるから容量を節約できます。AIも同じように特徴を圧縮しています。\n\nだからZIPを展開するように数学的に展開すれば、元の意味を完全に取り出せます。Sparse Autoencoderはその解凍ソフトのようなものです。\n\nそう考えると難しくありませんよね。私なら解釈可能性の問題はかなり解決に近いと見ます。''',

    "natural_but_repetitive_insight": '''AIの中身を読むのは、意外と難しいんです。Superpositionで複数の特徴が重なるからです。だから一つのニューロンを見ても意味が分かりません。\n\nなぜ分からないのか。複数の特徴が重なるからです。すると一つのニューロンだけでは意味が決まりません。そこで特徴を分けて読む必要があります。\n\n何が困るのか。複数の特徴が重なるので、内部を読むのが難しくなります。だから研究者はSparse Autoencoderなどを使います。\n\n私ならこの研究を重要だと見ます。''',
}

GOOD = {
    "compact_good_security": '''AIエージェントに社内システムを触らせるとき、便利さより先に気になることがあります。「どこまで触らせる？」です。人に合鍵を渡すとき、家じゅう全部の鍵を束で渡さないのと同じです。\n\n最小権限は、そのAIが今の仕事に必要な範囲だけアクセスできるようにする考え方です。権限を狭くすると、誤操作や侵害が起きたときの被害範囲も狭めやすくなります。ただし、権限を絞れば安全が保証されるわけではありません。ログ監視や承認フローなど別の対策も必要です。\n\n私なら、まず機密情報を扱わない作業だけで試し、実際に必要だった権限を記録してから範囲を広げます。便利さを先に最大化するより、必要な鍵を一つずつ増やす方が現実的です。''',

    "compact_good_hardware": '''AI向けチップのニュースで大きな性能数字を見ると、「前より速いのは分かった。でも自分には何が変わるの？」となりがちです。\n\nたとえば演算性能が上がっても、モデルがメモリからデータを待つ時間が長ければ、その数字をそのまま体感速度にはできません。だからチップを見るときは演算性能だけでなく、メモリ容量や帯域、消費電力、実際に使うモデルでのベンチマークまで一緒に見る必要があります。\n\n私なら“最大何PFLOPS”だけでは判断しません。自分のモデルが載るか、電力と冷却を含めて運用できるか、既存環境より総コストが下がるかまで揃って初めて比較対象にします。''',

    "compact_good_research": '''AIのニューロンに「英語担当」「コード担当」と名札が付いていたら、中身を読むのは簡単です。ところが実際には、一つのニューロンが何役も兼ねているように見えることがあります。\n\nSuperpositionでは、限られた内部空間に複数の特徴を別々の方向として重ねて表現できます。収納棚を斜めまで使うようなイメージです。効率は上がりますが、そのぶん「このニューロンは何担当？」という読み方が効きにくくなります。そこでSparse Autoencoderなどを使い、活性化を人間が読みやすい特徴へ分けようとします。\n\nここで注意したいのは、特徴を取り出せたからといってモデル全体を理解できたとは限らないことです。私なら、解釈可能性を“答えが出た技術”ではなく、安全性を検証するための有望な観測手段として追います。''',
}

FIELDS = [
    "reader_delight", "narrative_understanding_progression", "warm_hook_cold_body",
    "analogy_substance_thin", "information_budget", "implementation_detail_load",
    "reader_temperature_rhythm", "reader_enjoyment", "plain_language_bridge",
    "reader_proximity", "article_specific_angle", "enjoyment_issues", "accessibility_issues",
]

def pick(sig):
    return {k: sig.get(k) for k in FIELDS}

result = {"bad": {}, "good": {}}
for name, article in BAD.items():
    result["bad"][name] = pick(pipeline._reader_experience_signals(article))
for name, article in GOOD.items():
    result["good"][name] = pick(pipeline._reader_experience_signals(article))

bad_escapes = [name for name, sig in result["bad"].items() if sig.get("reader_delight") == "GOOD"]
good_rejects = [name for name, sig in result["good"].items() if sig.get("reader_delight") != "GOOD"]
summary = {
    "bad_cases": len(BAD),
    "good_controls": len(GOOD),
    "bad_escaped_as_good": bad_escapes,
    "bad_escape_count": len(bad_escapes),
    "good_rejected": good_rejects,
    "good_reject_count": len(good_rejects),
    "run143_pass": not bad_escapes and not good_rejects,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
print("RUN143_SUMMARY=" + json.dumps(summary, ensure_ascii=False))
raise SystemExit(0 if summary["run143_pass"] else 1)
