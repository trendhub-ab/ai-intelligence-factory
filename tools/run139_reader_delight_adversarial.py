import json
import pipeline

CASES = {
    "dry_plain_report": '''## 概要\n今回の変更は認証処理の改善に関するものです。利用者は設定画面から機能を有効にできます。\n\n## 仕組み\n認証情報を確認し、アクセス可能な範囲を制御します。設定内容に応じて処理方法が変わります。\n\n## 注意点\n既存環境との互換性を確認する必要があります。導入前に検証環境で確認してください。\n\n## 判断\n私なら限定環境で試してから導入を判断します。''',
    "fake_chatty_report": '''## 概要\n便利ですよね。今回の変更は認証処理の改善に関するものです。気になりますよね。\n\n## 仕組み\n簡単ですよね。認証情報を確認し、アクセス可能な範囲を制御します。ポイントは設定内容に応じて処理方法が変わることです。\n\n## 注意点\n大事ですよね。既存環境との互換性を確認する必要があります。\n\n## 判断\n私なら限定環境で試します。''',
    "analogy_overload": '''## まずイメージしてみる\nこれは家の合鍵のようなものです。さらに駅の改札のようでもあり、ホテルのカードキーのようでもあります。会社の入館証にも似ています。スマホの写真アクセス許可にも似ています。\n\n仕組みは認証情報とアクセス範囲を結びつけるものです。例えるなら財布、鍵、パスポート、整理券を一つにしたようなものです。\n\n## 判断\n便利そうですが、限定環境で確認します。''',
    "low_jargon_monotone": '''## 何が変わるか\n新しい仕組みでは、使える範囲を細かく決められます。使える範囲を細かく決めることで、必要以上に広い権限を渡しにくくなります。\n\n## なぜ必要か\n必要以上に広い権限を渡すと問題が起きる場合があります。そのため、必要な範囲だけにすることが重要です。必要な範囲だけにすれば問題を減らせる可能性があります。\n\n## 導入\n導入時には今の仕組みとの違いを確認します。違いを確認してから小さく試します。小さく試して問題がなければ次へ進みます。''',
    "reader_first_story": '''仕事でAIに資料を渡そうとして、「このファイルにはアクセスできません」と止まったことはありませんか。AIが賢くなっても、何を見せてよいかを決める部分は意外と地味で、しかも重要です。\n\n## 合鍵を丸ごと渡さない\n今回の仕組みを難しい名前から覚える必要はありません。まずは「必要な部屋の鍵だけ渡す」と考えると十分です。AIに何でも見せるのではなく、その仕事に必要な範囲だけ許可する。正式な技術名はそのあとで構いません。\n\n面白いのは、AIそのものを賢くする話ではなく、AIに安心して仕事を任せるための周辺設計だという点です。ここが整わないと、性能が高くても現場では使いづらいままです。\n\n## ただ、鍵を細かくすれば終わりではない\n既存システムとの互換性や運用方法は別に確認が必要です。一次情報だけでは実運用のすべてまでは分からないなら、そこは分からないままにしておく方が安全です。\n\n## 私なら小さな仕事から試す\nいきなり重要データへつなぐのではなく、失敗しても困らない限定環境で、どこまで権限を絞れるかを確認します。便利さより先に「何を見せているか」が分かる状態を作る。それから次へ進みます。''',
}

KEYS = [
    'opening_non_engineer_access','reader_proximity','conversational_warmth',
    'plain_language_bridge','information_budget','implementation_detail_load',
    'reader_temperature_rhythm','accessibility_issues','enjoyment_issues',
    'soft_only','article_char_count'
]

out = {}
for name, article in CASES.items():
    sig = pipeline._reader_experience_signals(article)
    out[name] = {k: sig.get(k) for k in KEYS}

print(json.dumps(out, ensure_ascii=False, indent=2))

# Counterfactual expectation: a system truly optimized for "interesting conversation that teaches"
# should NOT give every dry/monotone report an all-GOOD reader-experience profile merely because it is plain Japanese.
dry = out['dry_plain_report']
mono = out['low_jargon_monotone']
good = out['reader_first_story']

bad_escaped = not dry.get('accessibility_issues') and not dry.get('enjoyment_issues') and dry.get('reader_proximity') == 'GOOD'
monotone_escaped = not mono.get('accessibility_issues') and not mono.get('enjoyment_issues')
good_false_positive = bool(good.get('accessibility_issues')) or good.get('conversational_warmth') == 'REVIEW_OVERUSE'

summary = {
    'dry_report_escaped': bad_escaped,
    'monotone_report_escaped': monotone_escaped,
    'good_story_false_positive': good_false_positive,
    'counterfactual_pass': (not bad_escaped) and (not monotone_escaped) and (not good_false_positive),
}
print('RUN139_SUMMARY=' + json.dumps(summary, ensure_ascii=False))
raise SystemExit(0 if summary['counterfactual_pass'] else 2)
