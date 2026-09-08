# AI Intelligence Factory Run296 仕様追補

## 目的

最初の実note Private Draftを人間が目視した結果を、単発修正ではなく今後のProduction標準へ反映する。

## 1. アイキャッチ

- 長い記事タイトルをアイキャッチへそのまま複製しない。24 canonical文字を超えるsource titleとeyecatch titleが同一ならsemantic planをRejectする。
- 日本語複合語は文字幅都合で分割しない。少なくとも `舞台裏`、`生成AI`、`機械学習`、`深層学習`、`大規模言語モデル`、`意思決定` を保護する。
- highlightは意味の完結した連続フレーズを使う。`舵を切った理由` を `切った理由` へ欠落させない。
- 下部説明文/subheadlineは廃止する。badge / hook / main title / category-date footerは維持する。
- Netflix GenRecの人間レビュー済み修正は以下をdeterministic specimenとして固定する。
  - 1行目: `Netflix推薦の舞台裏`
  - 2行目: `LLMネイティブへ`
  - 3行目: `舵を切った理由`
  - orange highlight: `舵を切った理由`
- GenRec specimenの修正にGemini callは使わない。今後の通常記事はRun180の既存1回のbounded layout callを継続し、Run296は追加callを作らない。

## 2. 記事冒頭

- `## 30秒でわかるこの記事` を `## どんな内容？` へ変更する。
- `**何が出た？**` はラベルだけを削除し、その直後の要約本文は維持する。
- 要約本文は `## どんな内容？` と `なぜ重要？` の間に1回だけ残す。
- `なぜ重要？` と `結論は？` は維持する。

## 3. 有料サブスクCTA

見出し:

`### 有料サブスクのご案内`

本文:

`有料サブスクでは、意思決定DBと月次ダイジェストを公開しています。AI情報の変化を追い、採用・様子見・見送りの判断を助けます。`

リンクラベル:

`詳しくはこちら`

既存のtracking URLは変更しない。

## 4. Footer順序

Run222の `Sources / Evidence -> disclaimer -> CTA` を維持する。Run296はRun222の後段でreader surfaceのみ正規化する。

## 5. Publication Contract

Run296は公開本文およびアイキャッチにmaterialな変更を与えるため `publication_contract.PUBLICATION_POLICY_FILES` に含める。既存Readyは新policyではそのまま公開不可とし、current-policy manuscriptへ明示的にrebaseする。

## 6. Safety

- Public note publicationは人間のみ。
- Run296自体にnote browser mutation、Notion write、public release、追加Gemini/model requestを持たせない。
- 既存GenRec draftを更新する場合は別のspecimen-bound workflowで同じdraftをin-place更新し、再度read-only監査を通す。
