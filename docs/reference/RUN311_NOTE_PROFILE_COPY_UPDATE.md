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

## Fail-closed contract

1. exact token `UPDATE_NOTE_PROFILE_TRENDHUB_BIZ`
2. public profile URLを開く
3. current文なら無変更で終了
4. old public stateにProduct Huntがない別状態なら停止
5. visible exact `設定` を1つだけ解決
6. legacy/current markerを含むプロフィール入力欄だけを解決
7. legacy本文が既知の旧正本と一致しなければ停止
8. current copyへ置換
9. visible exact `保存` を1つだけ解決し保存
10. public profileを再読込しcurrent copy存在・Product Hunt消失を確認

## Cost / scope

- Gemini/model calls: 0
- Production ONE-SHOT: 0
- Notion write: 0
- Scheduled Daily: PAUSED維持
- profile description 1フィールドのみ
