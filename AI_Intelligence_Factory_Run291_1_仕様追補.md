# AI Intelligence Factory Run291.1 仕様追補

## 目的

Run291で実装・全CI検証済みのread-only private draft監査を、現在の接続環境から安全に実行するため、既存のIssue #71専用Note ChatOps Bridgeへ監査専用コマンドを1つ追加する。

## 新規コマンド

`/aiif note audit`

## 認証境界

既存のNote ChatOpsと同じく、以下を全て必須とする。

- issue_comment createdイベント
- run_attempt = 1
- Issue #71
- Pull Requestではない
- comment user = trendhub-ab
- actor = trendhub-ab
- コメント本文が完全一致

前方一致・部分一致・追加文字・追加空白は許可しない。

## Dispatch先

監査コマンドは以下だけを起動する。

- workflow: `note-private-draft-audit.yml`
- ref: `main`
- confirm: `AUDIT_NOTE_DRAFT`
- sync_id: `3bd479ffdca9817f926aeaffbb779c4b`

sync_idは今回の監査対象Netflix GenRecへ固定する。

## 既存経路

以下は変更しない。

- `/aiif note sync` → `note-ready-sync.yml`
- `/aiif note draft` → `note-create-draft.yml`

## 禁止事項

Bridge自体は以下を持たない。

- Gemini/model call
- Production pipeline起動
- GCP VM直接操作
- Playwright/browser操作
- draft本文・draft URLの出力
- note公開操作

実際のread-only VM監査と必須VM停止はRun291 workflow側の責務とする。

## コスト・安全性

- Gemini/provider calls: 0
- new draft: 0
- draft mutation: 0
- public release: 0
- Daily: PAUSEDのまま
