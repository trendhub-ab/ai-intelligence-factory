# AI Intelligence Factory Run290 仕様追補

## 目的

Run287のPublication Policy更新時に、note Ready DBの品質失効処理が `品質状態=Ready取消` だけでなく `投稿状態=取下げ` まで自動変更し、後続のRun288再基底化後も人間ワークフロー状態が片道で残る問題が実データで確認された。

Run290では、**自動品質判定と人間の投稿ワークフローを完全に分離する**。

## 確定仕様

### 1. 自動品質失効が変更してよい項目

Content Intelligence側で以下のいずれかが成立し、note Ready DBの既存行が現在の公開候補から外れる場合:

- current Publication Contractではない
- current Ready manuscriptがない
- 必須アイキャッチがない
- active public sourceではない
- その他既存のfail-closed条件

自動同期が変更してよいのは以下のみ:

- `品質状態`: `Ready` → `Ready取消`
- `最終同期日`

### 2. 自動品質失効が変更してはいけない項目

以下は人間ワークフロー領域として、品質失効時も保持する:

- `投稿状態`
- `note公開URL`
- `投稿予定日`
- `投稿日`

`投稿状態` が以下のどの状態でも、自動品質失効は変更しない:

- 投稿待ち
- 投稿準備中
- 保留
- 取下げ
- 投稿済み

### 3. 新規Ready行の初期状態

新しいcurrent-policy Ready記事をnote Ready DBへ初めて作成するときは、従来どおり:

- `品質状態=Ready`
- `投稿状態=投稿待ち`

とする。

これは新規行の初期化であり、人間ワークフローの上書きではない。

### 4. 既存Ready行の再同期

既存行がcurrent-policy Readyへ戻った場合、従来どおりシステム管理項目を更新するが、人間ワークフロー項目は上書きしない。

したがってRun290以降は、品質失効→再Readyという往復が発生しても、`投稿状態` はその間ずっと人間が最後に設定した値を保持する。

### 5. 公開境界

Run290は以下を変更しない:

- Fact / Editorial / Reader / Publication Gate
- Publication Contractの判定ロジック
- 記事本文
- アイキャッチ生成
- Gemini model routing / budget
- note private draft作成ロジック
- note公開ロジック
- Daily schedule

公開は引き続きhuman-only。

## 反証テスト

最低限、以下をrequired CIで確認する:

1. 品質失効propertiesに `投稿状態` / `note公開URL` / `投稿予定日` / `投稿日` が含まれない。
2. 投稿待ち・投稿準備中・保留・取下げ・投稿済みの全状態で、品質失効PATCHが `投稿状態` を送らない。
3. すでに `Ready取消` の行はidempotentに再書き込みしない。
4. 新規Ready行だけは従来どおり `投稿状態=投稿待ち` で作成される。
5. 既存Ready更新も人間ワークフロー項目を上書きしない。

## コスト・安全性

- Gemini/provider calls: 0
- note browser/VM calls: 0
- Publication policy SHA変更: なし（運用同期ロジックのみ）
- 既存private draftへの変更: なし
- public release: 0
- Daily: PAUSEDのまま
