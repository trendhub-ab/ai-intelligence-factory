# AI Intelligence Factory Run372 仕様追補

## 目的

Production Daily が外部Sourceの一時障害を増幅しないことを保証する。

Run371でarXiv metadata APIの429/503、timeout、重複retryを抑制した結果、同じ種類の運用リスクがHacker News、X/Apify、OfficialVendor、GitHub GraphQLにも存在し得ることが判明した。Run372はSourceの内容・評価基準を変更せず、transport failure時の挙動だけを統一する。

## 変更しない契約

- Screening / Calibration / Decision Scoreのロジックは変更しない。
- XはDiscovery onlyであり、X投稿自体をEvidenceにしない。
- OfficialVendor / GitHub / HN / arXivのEvidence authorityは変更しない。
- Fact Gate、Evidence Gate、Publication Gate、Reader Gateを緩和しない。
- Notion DB schema、note公開境界、Scheduled Daily PAUSEDを変更しない。
- Source ROIはprovider outageをSource品質低下として学習しない既存契約を維持する。

## Hacker News / Algolia

Run269はAI関連11 queryをAlgoliaへ順番に送る。1 query目で429/503が発生した場合、同一Run内で残りqueryをnetworkへ送らない。

- 429/503: source circuitを即時OPEN。
- 500/502/504: 最大1回だけbounded retry。再失敗時にsource circuit OPEN。
- circuit OPEN後の同一Run request: network 0回でlocal skip。
- 正常200 response: 同一requestを短期in-process cache。

## X / Apify

20 profile isolationは維持する。個別プロフィールの欠損やactor row errorは他プロフィールへ波及させない。

一方、Apify provider全体を示すHTTP 401/402/403/404/429/500/502/503/504は1プロフィール目でprovider circuit相当として扱い、残りprofile actor runを停止する。

これにより、provider-wide障害時に最大20回の有料Actor実行・長時間timeoutを連鎖させない。

総課金上限、max records、20 handle watchlist、12h lookback、raw X non-Evidence契約は変更しない。

## OfficialVendor

OfficialVendorはSource全体で止めず、host単位で分離する。

- vendor Aの障害でvendor Bを止めない。
- exact configured release host単位でcircuitを持つ。
- 同一URL/params/jsonの正常200は短期in-process cacheし、同じRun内の重複取得を削減する。
- 429/503はhost circuit OPEN。
- 500/502/504は最大1回retry後にhost circuit OPEN。
- 403はblocked hostとして同一Runの追加取得を停止する。

ByteDance/Volcengineの公式Doc API fallback等、既存の一次情報境界は維持する。

## GitHub GraphQL

GitHub Trending discoveryは1 GraphQL requestの既存設計を維持する。

ただしHTTP 200で`errors`が返り、usable `data.search.nodes`が存在しない場合を正常な候補0件として扱わない。

この場合、Source Stability transportは既存collectorにdegraded HTTP相当を返し、fault-isolated source failureとして記録する。

`errors`が存在してもusable nodesが存在するpartial responseは候補として利用可能とし、warningを記録する。

## arXiv cache size guard

Run371の24h cacheは有効だが、40 entries × 大きなXML responseを単一runtime-state fileへ保持すると長期運用でContents stateが肥大化し得る。

Run372では次を追加する。

- 1 entry body上限: 既存250KB。
- entry数上限: 既存40。
- persisted state総量上限: default 700KB。
- 総量超過時は新しいcacheから優先して保持し、古いcacheを削除する。
- circuit / last request等のcontrol stateは維持する。

## Business KPIとの関係

Run372自体は記事品質を上げる機能ではない。目的は、外部Source障害時の無駄なnetwork待ち・有料call・誤った0件判定を減らし、正常なSourceとGeminiへ処理時間・API budgetを残すことにある。

最終事業KPIは従来どおり、Production fullで `Ready >= 1`、続いてNote Ready Syncから `note private draft >= 1` を安定して達成すること。
