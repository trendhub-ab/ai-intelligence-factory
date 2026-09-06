# Run269 — Live Acquisition Precision / East-West Vendor Smoke

Run269はRun268の**Business / Four-Source Intelligence設計を変更しない**。Run268をSource architecture authorityとして保持したまま、実ネットワークSmokeで発見した取得精度の問題だけをProduction後段overlayで補正する。

## 目的

Run268の初回Live Acquisition Smokeでは、11 OfficialVendorすべてへ到達できた一方、次の誤差が確認された。

1. OfficialVendorのナビゲーション文言（例: Models & pricing / Get API key）が更新候補として混入し得る。
2. Hacker News Algoliaのtypo toleranceにより、`Qwen`検索へ`jQuery`記事が混入し得る。
3. 中国Vendorの一部はHTML本文・埋込JSON・モデル一覧など公開面の形が異なり、単一HTML抽出方式では「接続成功」と「更新情報取得成功」を区別できない。
4. ByteDance / VolcengineはGitHub-hosted runnerから通常ドキュメントHTMLを取得した際、同じURLでもモデル一覧本文ではなくJavaScript shellだけが返る場合がある。

Run269はこれらをFail-Closed寄りに補正し、**接続できたことではなく、意思決定に使える一次情報を構造化取得できたこと**をLive Smokeの合格条件にする。

## Run268とのAuthority境界

Run268の以下は変更しない。

- active Source: `GitHub / HackerNews / ArXiv / OfficialVendor`
- GitHub = 実装動向
- ArXiv = 技術の先行動向
- HackerNews = 市場・エンジニア反応
- OfficialVendor = 商用利用に直結する一次情報
- Product Huntはactive Sourceへ戻さない
- OfficialVendorはRound Robin上1 Source
- 米国3社 + 中国主要8社
- 新しい有料API / API key / Gemini callを追加しない

Run269は`production_pipeline.py`で**Run268 install後**に適用し、Live acquisition関数だけをprecision版へ差し替える。

## Hacker News Precision

Run269のHNは市場規模の推定器ではなく、**エンジニア/コミュニティ反応の観測面**である。

取得契約:

- Algolia `search_by_date`
- `tags=story`
- `restrictSearchableAttributes=title`
- 直近**30日**のみ
- raw query `AI`は禁止
- bounded query: artificial intelligence / large language model / LLM / AI agent / coding agent / OpenAI / Anthropic / Claude / Gemini / DeepSeek / Qwen
- Algolia結果をそのまま信用せず、`_query_matches_title`で正規化後の**exact token / exact phrase**一致を再確認する
- `Qwen -> jQuery`のようなtypo false matchを捨てる

HNにブランド批判、議論、評判、漏洩主張等が含まれること自体は異常ではない。HNの役割はVendor公式更新の代替ではなく、コミュニティ反応・論点・熱量を観測することだからである。事実Authorityは引き続きEvidence/一次情報側で判定する。

## OfficialVendor Precision

Run269はVendorページを次の状態へ分ける。

- `structured_html` — server-readable HTMLから更新/商用状態を抽出
- `structured_embedded` — Next/Mintlify等の埋込JSON/escaped textから更新/退役情報を抽出
- `structured_current_state` — リリースイベントではなく、公式モデル一覧等の「現在状態」を一次情報として扱う
- `page_fallback` — 到達したが構造化更新を解決できない。**Strict Live Smokeでは不合格**

ナビゲーションやgeneric documentation headingを更新情報へ昇格させない。pre-H1 navigationは候補化しない。

### ByteDance / Volcengine

ByteDanceは公式の火山方舟モデル一覧を、商用選定に直結するcurrent-state primary sourceとして使用する。

- 通常取得URL: `https://www.volcengine.com/docs/82379/1799865?lang=zh`
- canonical model-list URL: `https://www.volcengine.com/docs/82379/1330310`
- リリースイベントと偽装しない
- 公式ページの`最近更新时间`を取得できる場合はtimestampを保持する
- timestampがHTTP返却形に含まれない場合、`模型列表`とSeed / Doubao系の具体的モデルmarkerの両方が確認できた場合だけcurrent-stateとして扱い、日付は捏造しない
- 通常HTMLがJavaScript shellのみの場合、ByteDance公式`bytedance/agentkit-samples`でも使用されているVolcengine公式文書fetch endpoint `https://docs-api.cn-beijing.volces.com/api/v1/doc/fetch`を最終bounded fallbackとして使用する
- このofficial docs APIはAPI key不要で、同じVolcengine公式文書のTitle / Contentを取得するだけである。第三者Evidenceやmodel APIへ切り替えない
- docs APIが返した内容も`模型列表` + Seed / Doubao等のcurrent-state markerまたは明示的な`最近更新时间`を満たさなければ`structured_current_state`へ昇格させない
- generic文書内容や単なるHTTP成功は`page_fallback`のままでStrict Live Smokeを失敗させる
- 取得transportは`current_state_transport`へ保存し、HTML成功か`official_doc_api`かを観測可能にする

## 中国主要Vendor

Run269でも中国Vendorを補助扱いにしない。

- Alibaba Qwen
- DeepSeek
- ByteDance Doubao/Seed
- Moonshot AI Kimi
- Zhipu AI GLM
- MiniMax
- Baidu ERNIE
- Tencent Hunyuan

出身地域ではなく、一次情報・商用影響・Evidence/Decision契約で同等に評価する。

## Live Smoke Safety Contract

`.github/workflows/run269-live-acquisition-smoke.yml` は実ネットワーク取得を行うが、Production write経路から分離する。

- Gemini/model calls = 0
- Notion writes = 0
- Production DB writes = 0
- publication actions = 0
- `pipeline`をimportしない
- public HTTPのみ
- 11 Vendorを個別fault isolation
- HNは20件bounded取得
- JSON reportを短期Artifactとして保存

Strict modeは11/11 Vendorが`structured_*` evidenceを返すことを要求する。`page_fallback`だけでは合格させない。

## 2026-09-07 Live結果

最終Live Smokeで次を確認した。

- OfficialVendor configured: 11
- structured success: **11/11**
- US: **3/3**
- CN: **8/8**
- fallback-only: **0**
- ByteDance: **`structured_current_state` / `transport=official_doc_api`**
- HN: **20 candidates / 11 queries / 30-day lookback**
- Run269 precision unit tests: **9/9 PASS**
- current-state unit tests: **8/8 PASS**
- `Qwen -> jQuery`誤一致は再現テストで拒否

Live SmokeはProduction記事生成・Gemini quota・Notion DBを一切消費しない。

## 非交渉事項

- Run268 four-source architectureをRun269都合で変更しない
- Product Huntをactive Sourceへ戻さない
- HNを市場需要/市場規模と誤認しない
- Algolia typo matchingを最終Authorityにしない
- Vendor page reachabilityをstructured evidence成功と同一視しない
- current-state pageを架空のrelease eventへ変換しない
- official docs APIのgeneric返却をcurrent-state Evidenceへ昇格させない
- current-state timestampを観測できない場合に日付を捏造しない
- 新しい有料API/API key/Gemini callを追加しない
- Daily PAUSEDを解除しない
- Public note human-onlyを変更しない

Run269の正本は、本書、`run269_acquisition_precision.py`、`run269_vendor_current_state.py`、`run269_business_source_precision.py`、`run269_acquisition_precision_guard.py`、関連tests、Live Smoke workflowである。
