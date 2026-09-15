# AI Intelligence Factory Run374 仕様追補 — Ready Rescue

## 目的

Productionで記事生成とEvidence取得まで成功しているにもかかわらず、狭いFact表現またはReader Surfaceだけを理由にReadyへ到達できない記事を、安全に救済する。

Run374はGateを緩めない。Evidence / Fact / Publication / Readerの既存判定を最終的に再実行し、既存条件を満たした記事だけをReadyとする。

## Run58から確定した対象

### 1. unsupported vague quantified claim

実例: `unsupported vague quantified claim: 数日`

一次情報にない曖昧な期間を、別の曖昧表現や具体値へ言い換えてはならない。既存Fact Gateが診断した時間修飾だけを0-APIで差し引く。

許可:
- `数日で` / `数日以内に` / `数日後に` 等、診断済み時間修飾の局所削除
- 削除後に既存Gateを通常どおり再評価

禁止:
- `短期間`、`すぐ`、`近日中`など新しい未裏付け表現への置換
- 数値、日付、Evidence、固有名詞の追加
- 見出し、コード、URL、出典行への編集
- 診断されていないFact Claimの削除

### 2. Final Reader Surface

Needs Editorial Reviewに保存済みで、通常Fresh / Deferred / Pending Retry処理後にも記事生成余力が残る場合だけ、Ready Rescueを最大1候補に実行できる。

Quality FailedとPending Retryは対象外。Ready RescueはEvidence不足やFact HARD BLOCKをReader修正として迂回してはならない。

## 予算契約

Deep Dive既存上限12を維持する。デフォルト配分は次のとおり。

- Fresh: 8
- Deferred / Pending backlog: 3
- Ready Rescue: 1
- 合計: 12

Ready Rescueは追加API予算ではない。通常処理が総上限を超えることはない。Ready Rescue実行時も、その時点の`used + 1`を一時上限として、複数モデルへの連鎖Fallbackを禁止する。

## Provider契約

Provider Health Routing自体は変更しない。Run374は特定モデルを恒久除外しない。

2026-09-16 17:00 JSTまでの運用上の一時制約としてGemini 3.6の残り2リクエストを温存する。これを恒久コードへ埋め込まない。リセット後は通常Provider Health Routingへ戻せる。

## 受入条件

1. 曖昧期間救済は0 Gemini callである。
2. 新しい事実・数値・期間表現を生成しない。
3. URL / code / headingを変更しない。
4. Ready Rescueモデル枠は既存総12枠内の1枠だけである。
5. `used`をリセットしない。
6. Ready Rescue後も既存Evidence / Fact / Publication / Reader Gateを通らない限りReadyにしない。
7. Scheduled DailyはPAUSEDのままとする。
8. CI / synthetic regressionをすべて通してからmainへ反映する。
