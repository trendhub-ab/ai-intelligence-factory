# AI Intelligence Factory Run291 仕様追補

## 目的

Run289でNetflix GenRecのprivate note draft作成に初成功した。既存のdraft作成経路は、保存後にタイトル・本文・アイキャッチの永続化を再読込で確認しているが、**人間が公開前に見る実エディタ画面の構造監査**は成功時に記録していない。

Run291では新しいdraftを作成せず、既存private draftをread-onlyで再表示し、公開前のpresentation integrityを自動監査する。

## プライバシー境界

リポジトリは公開であるため、未公開note本文・draft URL・成功画面スクリーンショットをGitHub Actions artifact / log / summaryへ出してはならない。

Run291が外へ出してよいのは、本文を復元できない以下の監査メトリクスだけとする。

- title_match
- body visible / expected character counts and ratio
- body H1 count
- H2/H3/H4 count
- paragraph / list / link / blockquote count
- eyecatch persistence boolean
- Sources / Evidence がCTAより前にあるか
- duplicate title prefix boolean
- title/body geometry
- local Chrome history candidate count / matched rank
- draft URLのSHA-256短縮hash

## 対象条件

監査対象は明示sync_idで1件に固定し、以下を全て満たす必要がある。

1. note Ready DBに同じ同期IDがexactly one存在する。
2. 品質状態 = Ready。
3. 投稿状態 = 投稿準備中。
4. note公開URLが空。
5. 投稿日が空。
6. Content Intelligence側もactive Ready。
7. current Publication Contractのbyte-valid manuscriptが存在する。
8. eyecatchが存在する。
9. Source / destination titleが一致する。

1つでも満たさない場合はfail-closed。

## 既存draftの特定

private draft URLはGitHubへ保存しない。

永続Chrome VMのローカルprofileに残るChrome History DBをVM内でcopyしてread-only queryし、直近の `https://note.com/notes/.../edit` または `https://editor.note.com/notes/.../edit` 候補だけを抽出する。

候補URLはログへ出さず、Chromeでread-only表示して、期待タイトルが完全一致したページだけを監査対象とする。

## 実画面監査

対象draftを開いた後、以下を確認する。

- editor routeであること。
- titleが完全一致すること。
- bodyの先頭・末尾がapproved presentation manuscriptと一致すること。
- body visible lengthがexpected lengthから大きく乖離しないこと。
- body-level H1が0であること。
- heading structureが保持されていること。
- eyecatch変更controlが存在し、保存済み画像を確認できること。
- Sources / Evidence → CTA の順であること。
- body先頭にtitleが重複していないこと。
- title/body editor geometryが異常に狭くないこと。

## note mutation禁止

Run291は以下を一切行わない。

- title/body編集
- keyboard入力
- clickによる編集操作
- eyecatch upload/change
- draft save
- draft create
- Notion投稿状態更新
- note public release
- screenshot artifact upload

認証sessionが失効している場合、既存のNOTE_STORAGE_STATE_B64からnote.com sessionだけをpersistent profileへseedすることは許可する。ただしdraft contentは変更しない。

## Workflow

`note-private-draft-audit.yml` はworkflow_dispatch専用。

1. GitHub-hosted preflightでexact targetを確認。
2. targetがaudit-readyの場合だけpersistent note VMを起動。
3. self-hosted runnerでread-only audit。
4. safe metricsだけstep summaryへ記録。
5. success/failureにかかわらずVMを停止。

artifact uploadは禁止。

## コスト・安全性

- Gemini/provider calls: 0
- new draft: 0
- note draft mutation: 0
- public release: 0
- unpublished screenshot artifact: 0
- Daily schedule: PAUSEDのまま
