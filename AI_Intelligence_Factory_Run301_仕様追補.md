# AI Intelligence Factory Run301 仕様追補

## 目的

Run296で誤って削除されたNetflix GenRec記事の冒頭要約を復活させ、同時に今後のProduction標準を「`何が出た？` ラベルだけ削除し、要約本文は維持する」仕様へ訂正する。

## 1. 正式な冒頭構造

`## どんな内容？` の直後に要約本文を1回だけ置き、その後に `なぜ重要？`、`結論は？` を続ける。

Netflix GenRecの復元対象要約:

`Netflixがユーザー行動や文脈をテキスト化し、vLLMのprefill-onlyモードでスコアリングを行う推薦アーキテクチャGenRecを公開した。`

`何が出た？` ラベル自体は復活させない。

## 2. Publication Contract / Notion

- Run296のproduction policy file変更によりPublication Contract fingerprintを更新する。
- 既存のpre-Run296署名済みGenRec本文を根拠に、修正版Run296 transformでcurrent-policy本文を再構築する。
- Content Intelligenceの同一ページへcurrent-policy Ready blockを追加する。
- Note Readyを再同期し、品質状態 `Ready`、投稿状態 `投稿準備中`、公開証拠なしを維持する。
- prose regeneration / Gemini / provider callは行わない。

## 3. note private draft

- 新規下書きは作らない。
- Chrome Historyから既存Netflix GenRec `/notes/<id>/edit` をexact-titleで1件だけ特定する。
- 修正前本文がRun300 canonical surfaceで、要約だけが欠落していることを確認する。
- Run300のexact DOM Selection → clear → canonical paste経路を再利用し、本文を1回だけ置換する。
- 保存後にrenderer-faithful actual-note auditを行う。

## 4. アイキャッチ

- デザイン内容は変更しない。
- source assetは1280×670をhard gateする。
- note上の既存header media fingerprintが本文修正前後で同一であることを要求する。

## 5. 完了条件

- 要約本文: 1回だけ存在
- 順序: `どんな内容？ -> 要約 -> なぜ重要？ -> 結論は？`
- `何が出た？`: 0回
- `Sources / Evidence`: 1回、CTAより前
- 新CTA見出し/本文/`詳しくはこちら`: 維持
- 同一private draft route: 維持
- duplicate draft: false
- public release: false
- Daily restart: false
- Gemini/model calls: 0
