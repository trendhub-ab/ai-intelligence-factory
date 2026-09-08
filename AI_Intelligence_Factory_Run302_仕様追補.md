# AI Intelligence Factory Run302 仕様追補

## 目的

人間がnoteで本番公開したNetflix GenRec記事を、実公開ページの監査後にNote Readyへ安全に同期する。

## 1. 対象

- 同期ID: `3bd479ffdca9817f926aeaffbb779c4b`
- 記事: `Netflixが推薦の舞台裏をLLMネイティブへ舵を切った理由。`
- 公開操作そのものは人間が実施済みとし、Run302は公開・再公開・編集・取下げを一切行わない。

## 2. 公開URLの確定

- persistent Chrome Historyから既存の同一note editor routeをexact titleで1件だけ特定する。
- editor routeの `/notes/<note-id>/edit` からnote-idを抽出する。
- editor DOMに存在するpublic link/canonical/og:urlと、固定author slug `trendhub_biz` を候補にする。
- 候補URLは公開ページを実際に開き、note-id・タイトル・本文・アイキャッチ監査を通過した1件だけを採用する。
- 検索結果や推測URLだけではNote Readyへ書き込まない。

## 3. 実公開ページ監査

以下を必須とする。

- 公開URLのnote-idが既存editor routeと一致
- タイトル一致
- `どんな内容？` が存在
- GenRec要約本文が1回だけ存在
- `どんな内容？ -> 要約 -> なぜ重要？ -> 結論は？` の順序
- `何が出た？` は0回
- `Sources / Evidence` がCTAより前
- 新しい有料サブスクCTA本文と `詳しくはこちら` が存在
- 公開アイキャッチをvisible large image + og:imageで確認

## 4. Note Ready更新

公開ページ監査PASS後のみ、同一Note Ready行の以下4項目を更新する。

- 投稿状態: `投稿済み`
- note公開URL: 実監査済みURL
- 投稿日: Asia/Tokyoの公開確認日
- 最終同期日: 同日

品質状態 `Ready` その他のsystem propertiesは変更しない。

## 5. 重複防止

- 同じnote公開URLが別のNote Ready行に既に結び付いていたらfail-closed。
- 同期IDの行が1件でなければfail-closed。
- 新規draftは作成しない。

## 6. Safety

- note public release action: 0
- note draft mutation: 0
- Gemini/model call: 0
- Daily restart: false
- VMは監査終了後に停止する。
