# AI Intelligence Factory — Run371 仕様追補

## 1. 目的

Production ONE-SHOT Run #58 で確認された arXiv metadata API の 429 / timeout 連鎖を、品質Gateを緩めずに抑制する。

Run #58 では `export.arxiv.org/api/query` に対して、通常収集、Evidence Health、別プロセスの Product Review、その後の Evidence Health がそれぞれ独立して再試行した。arXiv 側が過負荷状態であるにもかかわらず同一 GitHub Actions Run 内で追加アクセスが続き、候補取得 0 件、待ち時間増大、Evidence 確認遅延を同時に発生させた。

Run371 はこれを「ソース品質の問題」ではなく「共有 transport state の欠如」として修正する。

## 2. 変更しないもの

以下は一切変更しない。

- Decision Score / Stock 閾値
- Evidence Sufficiency Gate
- Fact Gate
- Publication Readiness Gate
- Human Appeal / Reader Value Gate
- Deep Dive 件数・Gemini request budget
- Product Review の採用基準
- note Ready / private draft 契約
- X discovery 契約

arXiv が取得できない場合に Evidence を推測・補完して通すことは禁止する。

## 3. Run371 transport contract

### 3.1 共通入口

既存の `_fetch_arxiv_with_retry()` を `arxiv_stability_layer.ArxivStabilityController.fetch()` で置換する。

インストールは `run203_runtime_state_channel.install()` から行う。これにより、通常 Production と別プロセスで動く Product Review の両方が同一の transport contract を使用する。

### 3.2 Request pacing

arXiv metadata API への network request は、既定で前回要求から最低 4 秒空ける。

設定:

- `AIIF_ARXIV_MIN_INTERVAL_SECONDS` — default 4.0、下限 3.0
- 同一プロセス内は lock で直列化
- GitHub Actions 内では `runtime-state` の `last_request_at_epoch` をプロセス間で共有

### 3.3 Cache

HTTP 200 の metadata response を `runtime-state/.runtime/arxiv_stability_state.json` に保存する。

既定:

- TTL: 24時間
- 最大40 entry
- 1 response 最大250KB

同一 query / id_list の再利用時は network call を行わず cache を返す。

Cache は一次情報そのものの公開 XML response の再利用であり、新しい事実生成や要約ではない。

### 3.4 Overload circuit breaker

arXiv metadata API が 429 または 503 を1回返した場合、その `GITHUB_RUN_ID` では circuit を即時 Open にする。

以後の同一 Run 内 metadata request は:

1. fresh cache があれば cache を返す
2. fresh cache がなければ network call を行わず `None` を返す
3. 既存の上位ロジックが fail-safe / deferred / Evidence insufficient として処理する

429/503 に対する同一Run内の3回再試行は禁止する。

### 3.5 その他の一時障害

429/503 以外の transport timeout / 5xx は最大1回のみ bounded retry を許可する。

retry 待機は最低4秒、既定10秒。

### 3.6 Runtime-state persistence

共有状態は protected `main` へ書かない。

保存先:

`runtime-state:.runtime/arxiv_stability_state.json`

保存する情報:

- timestamp
- last HTTP status / error type
- current Actions Run の circuit state
- query hash
- 公開 arXiv XML response cache

保存しない情報:

- Gemini prompt / response
- 記事本文
- Notion content
- API key / token
- private user data

GitHub state persistence が一時的に失敗しても Production 全体は停止しない。ただし persistence failure を理由に arXiv API の追加retryは行わない。

## 4. Run #58 再発防止条件

Run #58 と同じ条件で最初の latest-query が 429 の場合、期待動作は以下。

- latest-query: arXiv network call 1回 → 429 → circuit open
- Main Evidence Health: cache missなら network 0回で defer
- Product Review child: 同じ `GITHUB_RUN_ID` の circuit を読み network 0回
- Product Review 後 Evidence Health: network 0回

従来のような「各工程で3回ずつ429/timeout」は発生させない。

## 5. 成功判定

CI:

- Run371 unit tests PASS
- full pytest PASS
- Repository-wide Falsification Guard PASS
- Notion Access Policy Guard PASS
- Integration Reconciliation CI PASS
- Synthetic Production critical failure 0

次回 live ONE-SHOT full:

- `[ARXIV STABILITY INSTALLED]` を確認
- 最低4秒 pacing または cache hit を確認
- 429/503 発生時は1回で circuit open
- 同一Run後段で `[ARXIV STABILITY CIRCUIT SKIP]` を確認
- arXiv障害があっても他ソースのProduction処理は継続
- Fact/Evidence/Publication Gate の判定基準が変わっていないこと

## 6. ビジネス上の意味

Run371 の目的は arXiv 件数を無理に増やすことではない。

目的は、外部APIが不安定な日に同じ失敗へ時間とリクエストを繰り返し投下せず、記事生成・Ready Rescue・note handoff に計算資源と実行時間を残すことである。

AIIF の最終KPIは arXiv API 成功率ではなく、一次情報の安全性を維持したうえで `Ready >= 1`、`note private draft >= 1` を安定して達成することとする。
