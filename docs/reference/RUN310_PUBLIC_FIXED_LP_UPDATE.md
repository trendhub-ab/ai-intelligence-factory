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

## Live falsification findings

### Hidden duplicate control

初回Run310は、本文・タイトルをeditorへ入れた後、最終`更新する`を押す前にfail-closedで停止した。DOM上のhidden duplicateまで含むrole locatorを数えていたことが原因だった。修正後は`button:visible`かつexact textだけを対象とする。

### Editor autosave is not publication state

2回目Run310で、noteは最終`更新する`前でも編集内容をeditor側へautosaveすることが判明した。editorでは新タイトルになっていた一方、公開URLは旧タイトルのままだった。

したがって **editor title == current title を `already_current` の根拠にはしない**。current titleがeditorに存在する場合は、

1. editor本文がRun308正本と一致することを再検証
2. 別pageでpublic URLを確認し、editor画面を破壊しない
3. publicもcurrentなら`already_current`
4. publicが旧タイトルなら「staged editor / legacy public」と判定し、その正本一致済みstaged contentを`公開に進む`→`更新する`へ進める

public側で新タイトルはあるが他markerが欠ける等の部分的不整合は自動補正せずfail-closedとする。

## Content authority

本文・タイトルは `docs/reference/RUN308_PUBLIC_NOTE_READY_TO_PASTE.md` のSection 1/2を唯一の入力正本とする。

Current title:

> **「このAI、使える！」を根拠付きで判断する｜Decision Brief + AI意思決定DB**

中心価値:

> **「このAI、使える！」を、根拠付きで判断できる。**

CTAはMarkdown linkで `https://note.com/trendhub_biz/membership` へ明示的に接続する。

## Fail-closed update sequence

1. Exact token / ID / editor URLを検証
2. editorが旧タイトルならRun308 title/bodyを投入し本文一致を検証
3. editorがcurrent titleなら、staged本文がRun308と完全に整合することを検証
4. staged caseでは別pageでpublic stateを検証
5. publicもcurrentなら変更せず`already_current`
6. publicが旧版ならstaged editorを保持したまま続行
7. visible exact `公開に進む`を1回クリック
8. exact `/notes/ned673e381ef8/publish/` を確認
9. タグ・マガジン・メンバーシップ設定へ触れず、visible exact `更新する`を1回クリック
10. public URLを再読込し、新タイトル・主要marker・membership clickable link・旧タイトル消失を確認

更新後検証に失敗した場合も成功扱いにしない。

## Non-goals / Cost

- 通常記事の自動公開、新規記事公開、タグ/マガジン/アイキャッチ変更は対象外
- Gemini/model calls: **0**
- paid provider calls: **0**
- Production ONE-SHOT: **0**
- Scheduled Daily: **PAUSED維持**
- Notion write: **0**
- 対象公開note: **1件のみ**
