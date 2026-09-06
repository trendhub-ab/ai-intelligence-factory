# Run268 — Proposal-First / Four-Source Intelligence

Date: 2026-09-07  
Status: current business/source strategy

## Decision

AI Intelligence Factoryの初期Primary ICPを、**AI・Web・業務システム等を顧客へ提案・開発する1〜3名規模のフリーランス／小規模開発事業者**へ寄せる。

Primary Jobは、顧客から「このAI・技術を使うべきか」と聞かれたときに、Evidence・比較・リスク・利用条件・小規模検証条件を短時間で整理し、判断・提案メモへ落とすこと。自己学習・技術力向上はSecondary Valueとする。

価格は月額1,980円を維持し、まず実有料顧客10人で支払意思と継続利用を検証する。価格変更を今回のSource変更と混ぜない。

## Four-Source contract

| Source | Product role |
|---|---|
| GitHub | 実装動向 / OSS maturity |
| ArXiv | 技術の先行動向 / frontier research |
| HackerNews | 市場・エンジニア反応 |
| OfficialVendor | 商用利用に直結する一次情報 |

### HackerNews

旧Firebase Top Stories全体巡回をactive経路から外し、Algoliaのbounded AI queryへ置換する。AI / LLM / agent / OpenAI / Anthropic / Gemini / DeepSeek / Qwen等のquery結果をdedupeし、points/commentsを補助的な反応量として扱う。追加Gemini filterは使わない。

### OfficialVendor

Round Robin上では1 Sourceとし、内部metadataに `vendor` / `vendor_region` を保持する。VendorをSource枠へ分裂させない。

欧米:
- OpenAI
- Anthropic
- Google Gemini

中国主要:
- Alibaba Qwen
- DeepSeek
- ByteDance Doubao / Seed
- Moonshot AI Kimi
- Zhipu AI GLM
- MiniMax
- Baidu ERNIE
- Tencent Hunyuan

観測対象はmodel/API releaseだけでなく、pricing/billing、token/context、rate limit、SDK/compatibility、deprecation/retirement/migration等を含む。

中国系Vendorは勢いだけで加点しない。欧米系と同じEvidence / Decision / commercial-impact基準で扱う。

## Product Hunt retirement

Run268からProduct HuntはProductionのactive Sourceではない。

巨大なhistorical `pipeline.py` を直接書き換えて回帰面を広げる代わりに、`run268_business_source_strategy.py` をProduction入口でhistorical runtime layersの後にinstallする。

互換上、legacy `pipeline.main()` が `fetch_producthunt_trending` / `ProductHunt` keyを参照するcall slotは残るが、Run268 install後は:

1. `fetch_producthunt_trending` symbolがOfficialVendor fetcherへ置換される。
2. Product Hunt token/GraphQLは使用しない。
3. legacy `ProductHunt` source-group keyはscreening前に `OfficialVendor` へmutateされる。
4. active `SOURCE_ROI_SOURCES` は GitHub / HackerNews / ArXiv / OfficialVendor の4つだけになる。
5. historical ProductHunt ROI stateは監査履歴として残し、OfficialVendorへ継承しない。

## Safety / cost boundaries

- 新しい有料API・API keyを追加しない。
- OfficialVendorは公開公式ページをbounded HTTP GETする。
- Vendor単位の取得失敗はfault-isolatedし、他Vendor/Sourceを止めない。
- HN query数は固定bounded set。
- Source取得・表示のためにGemini/model callを追加しない。
- Existing Evidence / Fact / Decision / quota / retry / publication gatesを緩めない。
- CI testsはfake HTTPを注入し、external networkを使わない。

## Files

- `business_source_acquisition.py`
- `run268_business_source_strategy.py`
- `run268_business_source_strategy_guard.py`
- `tests/test_run268_business_source_strategy.py`
- `tests/test_run268_business_source_strategy_guard.py`
- `PAID_PRODUCT_CONTRACT.md`
- `AI_Intelligence_Factory_最終仕様書.md`
- `production_pipeline.py`
- `.github/workflows/repository-falsification.yml`

## Falsification requirements

Run268 is complete only when:

- Production entrypoint installs Run268 after historical runtime layers.
- Active source tuple contains exactly GitHub / HackerNews / ArXiv / OfficialVendor.
- ProductHunt is absent from active source tuple.
- Required Western 3 + Chinese 8 vendor registry entries exist.
- HN path uses Algolia and does not use Firebase topstories.
- Run268 modules contain no Product Hunt GraphQL endpoint/token dependency.
- Paid Product Contract and canonical spec express Proposal-First ICP and Four-Source roles.
- Repository-wide required check invokes Run268 guard/tests without changing the required job/context name.
