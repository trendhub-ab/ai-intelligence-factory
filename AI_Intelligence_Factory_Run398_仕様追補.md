# AI Intelligence Factory Run398 仕様追補

## 目的
Gemini Flash系のHTTP 503混雑時に、同一モデルの確認再試行だけで少数のDeep Dive予算を使い切らず、次の安定モデルへ到達できるようにする。同時に通常Deep Diveの推論負荷を下げ、最新モデル公開直後などの高需要時でもReady生成率を維持する。

## Production事実
2026-09-13のarticle_validationでは既存RubyGems記事1件に対し、gemini-3.8-flashが503を2回、gemini-3.7-flashが503を2回返した。4件のDeep Dive予算を同一モデル確認だけで消費し、既存fallbackであるgemini-3.6-flash / gemini-3.5-flashへ到達できず generated=0 となった。

## Run398契約

### 1. Deep Diveの503
- providerが構造化HTTP 503を1回返した時点で、そのモデルをrun-local unavailableへ置く。
- 同一モデルの503確認再試行はDeep Diveでは行わない。
- 残りのリクエスト予算を次のdistinct modelへ保存する。
- 通常のモデル順・日次上限・run上限は変更しない。
- 429、404、transport timeoutは既存の個別契約を維持する。

### 2. Thinking Level
- 通常Deep Diveは `thinking_level=low` を明示する。
- `quality_retry` / `quality_repair` / `quality_rescue` / `recompose` / `reader_repair` は既存caller設定を保持し、Run398がlowへ強制しない。
- Fact / Evidence / Publication / Reader Gateは一切緩和しない。

### 3. 変更しないもの
- Deep Dive request budget
- model daily budget
- Screening契約
- Product Review契約
- Notion永続化契約
- note公開契約
- Xロジック

## 期待する失敗時動作
4モデルpoolが `3.8 -> 3.7 -> 3.6 -> 3.5` の場合、3.8と3.7が各1回503でも、3件目の3.6へ到達できる。これにより同じ4リクエスト予算でも最大4つのdistinct modelを試せる。

## 回帰条件
- 3.8=503、3.7=503、3.6=success のfixtureで、provider-visible call順が `[3.8, 3.7, 3.6]` であること。
- 通常Deep Diveが `thinking_level=low` を受け取ること。
- quality retryのcaller指定thinking levelが保持されること。
- 既存Gateとbudgetを変更しないこと。
