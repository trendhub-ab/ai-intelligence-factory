# AI Intelligence Factory Run313 仕様追補

Run313は、Run312で実測したユーザー手動編集済み固定noteを全文上書きせず、current Product / Member UX contractと不整合な箇所だけを最小修正する保守層である。

## 対象

- note ID: `ned673e381ef8`
- Run312 body SHA-256: `3e3569378f388634c02d107d11672dd05958bbee4c4b4a6c9a2368af415f4b5c`

## 修正範囲

1. 冒頭に残った旧導入文と途中で切れた文を削除する。
2. `PC・スマートフォン対応` を、Run218のPC-first契約に合わせ `PCでの利用を推奨（スマートフォン向け簡易ビューあり）` へ修正する。

その他の本文、タイトル、CTA、価格、ソース表記、アイキャッチ、タグ、公開設定は維持する。

## Fail-closed

- titleがcurrent titleと一致しない場合は停止。
- body SHAがRun312実測値と一致しない場合は停止。ただし既にRun313修正済みでpublic verificationが通る場合のみ無変更成功とする。
- 全文貼り直しは禁止。
- 最終更新後にpublic URLで旧prefix消失、PC-first表現、主要Product marker、membership CTAを再検証する。

## 不変条件

- Gemini/model 0
- Production ONE-SHOT 0
- Notion write 0
- Scheduled Daily PAUSED維持
- 通常記事のhuman-only release契約は変更しない
