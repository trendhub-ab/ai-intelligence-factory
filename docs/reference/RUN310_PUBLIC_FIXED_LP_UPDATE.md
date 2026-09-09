# Run310 — Exact Public Fixed LP Update

## Purpose

ユーザーの明示承認に基づき、公開固定note **`ned673e381ef8`** 1件だけをRun308 current copyへ更新する。

これは通常記事の自動公開解禁ではない。通常のPublic note releaseは引き続きhuman-onlyとし、Run310は固定LP保守の**明示ID限定例外**とする。

## Authorized target

- Public URL: `https://note.com/trendhub_biz/n/ned673e381ef8`
- Editor URL: `https://editor.note.com/notes/ned673e381ef8/edit/`
- Publish settings: `https://editor.note.com/notes/ned673e381ef8/publish/`
- Exact confirmation: `UPDATE_PUBLIC_LP_NED673E381EF8`
- ChatOps: `/aiif note lp update`

## Live UI evidence

Run309で実noteをzero-mutation監査した。

1. 編集画面で確認した操作: `閉じる` / `一時保存` / `公開に進む`
2. `公開に進む`だけを押したread-only stageで、`/publish/`へ遷移
3. 公開設定画面の確定操作は `更新する`

したがってRun310は推測selectorではなく、**`公開に進む` → `更新する`** の実測導線だけを使用する。

### First live update falsification

2026-09-09の初回Run310 live updateは、本文・タイトルをeditorへ入れた後、最終`更新する`を押す前にfail-closedで停止した。原因は、DOM上のhidden duplicateまで含むrole locatorの`count()==1`を要求していたためで、Run309で実測した「画面上の見える`更新する`は1個」という事実とselector contractが一致していなかった。

修正後は `button:visible` に限定し、可視ボタンのexact textだけを解決する。hidden duplicateは候補数に含めない。公開ページを再確認した結果、初回失敗後も旧タイトルのままであり、最終更新は発生していないことを確認済み。

## Content authority

本文・タイトルは `docs/reference/RUN308_PUBLIC_NOTE_READY_TO_PASTE.md` のSection 1/2を唯一の入力正本とする。

Current title:

> **「このAI、使える！」を根拠付きで判断する｜Decision Brief + AI意思決定DB**

中心価値:

> **「このAI、使える！」を、根拠付きで判断できる。**

CTAはMarkdown linkで `https://note.com/trendhub_biz/membership` へ明示的に接続する。

## Fail-closed update sequence

1. Exact tokenを検証
2. Exact note ID/editor URLへ移動
3. current titleが旧正本 `AIはとっても重要。でも正直、もう追いきれない。` と一致することを確認
4. 想定外タイトルなら無変更で停止
5. タイトルをcurrentへ置換
6. Run308本文を挿入し、editor内で本文一致を検証
7. 画面上でvisibleな`公開に進む`がexactly oneであることを確認してクリック
8. exact `/notes/ned673e381ef8/publish/` を確認
9. タグ・マガジン・メンバーシップ設定へ触れず、画面上でvisibleな`更新する`がexactly oneであることを確認してクリック
10. public URLを再読込
11. 新タイトル・主要marker・membership clickable link・旧タイトル消失を確認

更新後検証に失敗した場合も成功扱いにしない。

## Idempotency

既にcurrent titleの場合は再編集せずpublic verificationだけを実行し、`already_current`として終了する。

## Non-goals

- 通常記事の自動公開
- 新規記事の公開
- タグ自動変更
- マガジン変更
- membership publication setting変更
- アイキャッチ変更
- note private API利用
- Gemini/model call
- Notion schema変更

## Cost / safety

- Gemini/model calls: **0**
- paid provider calls: **0**
- Production ONE-SHOT: **0**
- Scheduled Daily: **PAUSED維持**
- Notion write: **0**
- 対象公開note: **1件のみ**
