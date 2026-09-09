# Run311 — Exact Note Profile Copy Update

## Purpose

AI Intelligence Factoryの公開noteプロフィール文だけをRun308 current product positioningへ同期する。

対象アカウントは `https://note.com/trendhub_biz`。クリエイター名、画像、SNSリンク、記事、タグ、メンバーシップ設定には触れない。

## Current copy

**AI・技術の「使える / まだ」を、一次情報とEvidenceから判断するAI Intelligence Factory。自分の開発、業務利用、必要に応じた提案に使えるDecision BriefとAI意思決定DBを運営しています。**

旧プロフィールに含まれる `Product Hunt` はcurrent sourceではないため削除する。

## UI authority

note公式ヘルプのPC手順は、クリエイターページで `設定` を選択し、プロフィール文を更新して `保存` を選択する流れ。

Run311はこの2つのvisible exact controlだけを使う。入力欄は既存文中の `Product Hunt` またはcurrent文中の `Decision Brief` を含むvisible fieldだけを対象とする。

### First live UI falsification

2026-09-09の初回Run311 live executionは、公開プロフィールで旧文を確認し、visible exact `設定` のクリックまでは成功したが、保存・入力変更の前にfail-closedで停止した。旧resolverが `textarea` / `input[type=text]` / `contenteditable="true"` の3形態だけを想定しており、noteの現在UIのプロフィール入力実装を取得できなかったためである。公開プロフィールへのmutationは発生していない。

修正後は、mutation対象を広げるのではなく**候補の観測範囲だけ**を広げる。`textarea:visible`、`input[type=text]:visible`、`[contenteditable]:visible`、`[role="textbox"]:visible` を観測するが、実際に編集対象として採用する条件は従来どおり、既存値に `Product Hunt` または `Decision Brief` が含まれること。markerが見つからなければ保存せず停止し、visible entryのtag/role/contenteditable/name/placeholder/aria-label/valueの短い診断とdialog textをログへ残す。

これにより、note UIの実装差を観測しながら、別の入力欄を誤編集するリスクは増やさない。

## Fail-closed contract

1. exact token `UPDATE_NOTE_PROFILE_TRENDHUB_BIZ`
2. public profile URLを開く
3. current文なら無変更で終了
4. old public stateにProduct Huntがない別状態なら停止
5. visible exact `設定` を1つだけ解決
6. visible textbox候補を観測し、legacy/current markerを含むプロフィール入力欄だけを解決
7. markerが見つからない場合はread-only diagnosticsを残して無変更停止
8. legacy本文が既知の旧正本と一致しなければ停止
9. current copyへ置換
10. visible exact `保存` を1つだけ解決し保存
11. public profileを再読込しcurrent copy存在・Product Hunt消失を確認

## Cost / scope

- Gemini/model calls: 0
- Production ONE-SHOT: 0
- Notion write: 0
- Scheduled Daily: PAUSED維持
- profile description 1フィールドのみ
