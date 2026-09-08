# AI Intelligence Factory — 現行Production仕様

最終更新: 2026-09-09  
Core Reliability Baseline: **Run209 — Gemini timeout RPD fail-closed**  
Provider Resilience Baseline: **Run303 — Verified HTTP 503 confirmation / consecutive-only run-local circuit**  
Product Review Provider Runtime Baseline: **Run305 — Run304 counter authority / Run203 + Run209 + transient recovery + Run303 via sole `production_pipeline.py` entrypoint**  
Documentation Governance Baseline: **Run267 — Current Canonical Contract Sync / Required-Check Governance**  
Documentation Freshness Foundation: **Run210 — Documentation Freshness Guard**  
Production Source of Truth: **`main`**  
Paid Member Sync Baseline: **Run211 — Subscriber Decision Brief Sync / Member Presentation Sync**  
Paid Member UX Baseline: **Run215**  
Paid Member Commerce/Onboarding Baseline: **Run217**  
Paid Member Navigation/UI Baseline: **Run218**  
Paid Member Presentation Baseline: **Run219**  
Paid Member Database Destination Baseline: **Run220**  
Paid Member Database Hosting Baseline: **Run221**  
Paid Product Baseline: **Run268 — Proposal-First Decision Intelligence / Four-Source Intelligence**  
Member Surface Baseline: **Run270 — Proposal-First Member Surface / Run250 compatibility overlay**  
Member Body Sync Baseline: **Run271.1 — Member Body Delta Sync / previous-success checkpoint / sentinel full-fallback**  
Paid Product Contract: **`PAID_PRODUCT_CONTRACT.md`**  
Article Production Baseline: **Run249 + current article-quality stack**  
Article Model Routing Baseline: **Run261 — Run260 Live-Path Hardening / Gemini 3.7 Primary / 3.8 Quality Rescue**  
Eyecatch Baseline: **Run183 — Run181 Visual Balance / Run182 Conclusion Emphasis / Run183 Emphasis Scale**  
Pipeline Modularization Baseline: **Run245**  
Repository Organization Baseline: **Run246**  
Workflow Reference Integrity Baseline: **Run257 — Workflow Reference Guard**  
ChatOps Dispatch Baseline: **Run259 — GH_PAT ONE-SHOT Dispatch Token**  
ONE-SHOT Downstream Fan-out Baseline: **Run261 — Explicit GH_PAT Post-Run Dispatch**  
Integration Determinism Baseline: **Run263 — Hermetic / Locked / Zero-Provider Integration CI**  
Standalone Synthetic Baseline: **Run264 — Hermetic Synthetic Regression**  
Dependency Compatibility Baseline: **Run266 — Pillow 12.1+ Production Floor / <13 Upper Bound**  
Required PR Check Governance Baseline: **Run267 — Required contexts must be emitted for every PR to main**  
Business / Source Strategy Baseline: **Run268 — Proposal-First ICP / Four-Source Intelligence / OfficialVendor East-West Coverage**  
Acquisition Precision Baseline: **Run269 — Live Acquisition Precision / 11-Vendor Structured Smoke**  
Operational Reliability Baseline: **Run272 — Bounded Daily Failure Tails / Notion Date Boundary / arXiv Run-Local Circuit / Product Review 600s Bound**
Note Editorial Format Baseline: **Run296 — Reader-approved Note Editorial Format v2**

> 本書は「現在のProductionで何を守るか」を示すcanonical仕様である。歴史を無制限に積み増さない一方、現在もコード・Workflow・Fail-Closed Guard・回帰テストが保護する契約は省略しない。詳細な変更理由と観測記録は `docs/reference/`、過去資料は `docs/archive/` とGit履歴へ分離する。

---

## 0. 参照優先順位

1. `main` の実行コード・テスト・GitHub Actions
2. 本ファイル
3. `PAID_PRODUCT_CONTRACT.md`
4. `README.md` / `NOTION_ACCESS_POLICY.md` / `GEMINI_QUOTA_SETUP.md` 等の領域別Operator契約
5. `docs/reference/` の現行領域別仕様
6. `docs/archive/` とGit履歴

Productionコード・テスト・Fail-Closed Guardを、文書整理の都合で弱めたり旧仕様扱いしたりしない。

---

## 1. 事業・商品契約

AI Intelligence Factoryは **note事業そのものではない**。noteは低コストの集客・SEO・信頼形成チャネルの一つであり、将来はGoogle検索、X、YouTube、LinkedIn、Zenn/Qiita、コミュニティ、紹介等から同じ有料商品へ送客できる構造を維持する。

### 初期ICP

**AI・Web・業務システム等を顧客へ提案・開発する、1〜3名規模のフリーランス／小規模開発事業者。**

- Primary Jobは、顧客から「このAI・技術を使うべきか」と聞かれたとき、Evidence・比較・リスク・利用条件・小規模検証条件を短時間で整理し、判断・提案メモへ落とすこと。
- 自己学習・技術力向上はSecondary Valueとする。Primaryと同格にしない。
- AI専業である必要はないが、技術選定・提案・実装判断が売上や案件品質に影響する人を優先する。
- 「AIに興味がある個人全般」「非エンジニア全般」「法人全般」は初期ICPにしない。
- 法人は将来の高単価市場として保持するが、PMF前に請求書・複数席・SSO・管理者機能を作り込まない。

### 中心価値

> **「このAI、使える？」に、根拠付きで早く答えられる。**

有料価値は「情報量」ではなく、**変化を知る → Evidenceを確認する → 使う/試す/待つ/避けるを判断する → リスクと条件を整理する → 判断・提案メモへ落とす**工程を短時間で進められること。DB件数やニュース量を購入理由の中心にしない。

### Intelligence Source Contract — Run268

Productionで同格に巡回するactive Sourceは次の4系統とする。

1. **GitHub = 実装動向** — OSSの実装進展、更新、成熟度、保守状態、導入可能性を観測する。
2. **ArXiv = 技術の先行動向** — 研究・技術的ブレークスルー・将来の実装候補を観測する。論文であること自体を実用性と同一視しない。
3. **HackerNews = 市場・エンジニア反応** — HN全体Top StoriesではなくAI関連のbounded queryから、実務者・開発者の反応、論点、熱量を観測する。
4. **OfficialVendor = 商用利用に直結する一次情報** — モデル/API更新、価格、制限、context/token、SDK、互換性、deprecated/retire/migration等を公式ページから取得する。

OfficialVendorはRound Robin上では**1 Source**として扱い、内部metadataの `vendor` / `vendor_region` で識別する。ベンダーをSource枠へ分裂させない。

- 欧米主要: OpenAI / Anthropic / Google Gemini
- 中国主要: Alibaba Qwen / DeepSeek / ByteDance Doubao・Seed / Moonshot AI Kimi / Zhipu AI GLM / MiniMax / Baidu ERNIE / Tencent Hunyuan

中国系Vendorを補助扱いにしない。一方で出身地域だけで加点・減点せず、一次情報・実務影響・Evidence/Decision契約で同じように評価する。

**Product HuntはRun268からProductionのactive Sourceではない。** 過去の関数名・ROI履歴・画像資産等が互換/監査目的で残っていても、Production取得・active Source ROI・Round Robinの正本には含めない。Run268の互換層が旧 `fetch_producthunt_trending` 呼出しスロットをOfficialVendor取得へ差し替え、Product Hunt GraphQL/tokenは使用しない。

### 商品4層

1. **無料note** — 知る・面白く理解する。無料品質を意図的に落とさない。
2. **Decision Brief** — 今月、顧客案件・技術選定で知っておく価値がある3〜7件を先に読む。
3. **Decision Intelligence** — 必要時に全体DBで比較・根拠・リスク・履歴を確認する。
4. **Decision / Proposal Action Asset** — 利用条件、判断・提案メモ、小規模検証条件、比較観点等へ落とす。大量テンプレート市場へピボットしない。

内部の Intelligence Engine は上記より広く、Deep Techを含む。内部追跡対象と会員トップ表示を同一視しない。
### 価格・初期商業検証

- 標準価格: **月額1,980円**を維持して検証する。
- 初期主要マイルストーン: **知らない実顧客10人が実際に支払うこと**。
- 100人獲得や広告投下は、その後。
- 決済事業者・entitlement方式は実装済みProduction事実だけを本書へ昇格させる。未検証のStripe/note checkout案をProduction完了扱いしない。

---

## 2. Paid Member Production Surface

### 2.1 正規会員入口とDB

正規会員入口は **AI Decision Intelligence｜会員ホーム**。

- Home Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- 正規Member Presentation Database ID: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- 正規Member Presentation Data Source ID: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
- 物理API Host Page ID: `3c5479ff-dca9-8178-867c-d9249a3ff5c8`
- `MEMBER_PRESENTATION_ALLOW_CREATE: 'false'`

**Run218** がNavigation/UI Authority、**Run220** がDB destination Authority、**Run221** がphysical API host separation Authorityである。物理APIホストと会員ナビゲーションを同一視しない。

### 2.2 旧DBの隔離

以下は履歴・回帰監査のため残すが、現行destinationとして使用しない。

- Pre-Run220 Database ID: `d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1` — **旧版・使用禁止**
- Pre-Run220 Data Source ID: `d1461b6f-0940-4bf9-803a-6686a37c4ba2` — **旧版・使用禁止**
- Legacy Data Source ID: `ec2ac2b3-89b6-4242-89b9-e94060826fca` — **旧版・使用禁止**

旧100-row Member DB系を新しいcanonical destinationへ戻さない。DB自動生成はfail closedで、勝手に別DBへ切り替えない。

### 2.3 Member UX契約

- **PC-first**。PCを主要会員体験とし、モバイル/simple viewはsecondary fallback。
- 会員トップの **live Top3** は実データから生成し、手書き固定カードへ戻さない。
- `今月の重要変化` はsource semanticsを改変しない。
- Presentation-only fallbackでは `評価の変化 >= 20` または `評価の変化 <= -20` を大きな変化の補助条件として扱う。
- 表示都合でsourceのmonthly checkboxやcanonical Decision/Evidenceを書き換えない。

2026年9月 Decision Brief Page ID: `3d0479ff-dca9-81de-b614-fef528d2f32c`  
AI導入 判断・提案メモ Page ID: `3d3479ff-dca9-8119-b0d8-c014b068fe82`

### 2.4 Member同期・Commerce互換契約
**Run211** の派生同期は、`Subscriber Decision Brief Sync` → `Member Presentation Sync` の順序を守る。`Inventory plan` はwrite fan-outを起こさず、Inventory Bootstrapのapplyだけを派生write対象にする。

Scheduled Dailyは現在 **`Daily Intelligence & Content Pipeline [PAUSED]`** としてhard-PAUSEDである。Run261以降、成功したONE-SHOTの直接fan-outは受動的なONE-SHOT `workflow_run` に依存しない。`.github/workflows/daily-one-shot.yml` が `${{ secrets.GH_PAT }}` で `note-ready-sync.yml`、`subscriber-decision-brief.yml`、`cross-db-contract-guard.yml` を `workflow_dispatch` する。これら3本は直接ONE-SHOTをpassive subscribeせず、将来GitHub側の挙動が変化しても同じONE-SHOTから二重writeしない契約とする。

`Subscriber Decision Brief Sync` の `workflow_run` は独立した `Subscriber Inventory Bootstrap` 完了経路だけを保持し、`[apply]` のみwrite対象とする。`Member Presentation Sync` は `Subscriber Decision Brief Sync` の完了後に動き、同一の `member-derived-notion-writes` lockで直列化する。PAUSED stubや存在しない将来aliasをlive triggerとして残さない。Scheduled Dailyを明示的に再開する場合、その時点の実在するworkflowとfan-out方式を同一のreviewed changeで再設計する。

ChatOps control issueからONE-SHOTをdispatchする場合は、**Run259** の契約として `${{ secrets.GH_PAT }}` を必須のdispatch credentialにする。`${{ github.token }}` / repository `GITHUB_TOKEN` へ黙ってフォールバックしない。さらに**Run261**では、ONE-SHOT成功後の直接fan-outにも同じくGH_PATを必須とし、PAT未設定・dispatch失敗はfail closedとする。Production本体だけ成功し会員向け派生同期が欠落する「部分成功」を正常扱いしない。

**Run217** はCommerce/Onboarding履歴として保持し、Run218/220/221の後続Authorityを明示する。Digestを販売価値として案内する以上、**Digest自動生成が停止中でも**、人間運用を含めて会員へ約束したDigestを無言で消さない。自動生成停止を「Digest提供停止」と読み替えない。

### 2.5 Proposal-First Member Surface — Run270

Run268でPrimary ICPとPaid ProductをProposal-Firstへ変更した後も、Run250由来のWork-First bodyが最終可視面として残っていた。Run270はRun250を歴史的互換層として保持しつつ、`run219_member_human_language_ui.py` の実workflow入口で**Run250の後**に `run270_proposal_first_member_surface` を適用する。

Member Presentation DBのgenerated detail bodyは、既存canonical値だけを使って原則次の順に表示する。

- `これは何？`
- `顧客にどう答える？`
- `提案できる場面`
- `なぜ今見る？`
- `提案前に確認すること`
- `提案・検証の次の一手`
- material changeがある場合 `Decision Update｜提案を変える必要がある？`
- `確認に使った公式・一次情報`

Home / Decision Brief / AI導入 判断・提案メモの静的Notion面も同じProposal-First契約へ揃える。顧客提案を「副次利用」と表現しない。社内利用・自己学習はSecondary Valueとして残す。

Run270はSource score / Decision / Evidence / Deep Tech / Notion schemaを変更せず、表示のためのGemini/model callを追加しない。詳細と実ページIDは `docs/reference/RUN270_PROPOSAL_FIRST_MEMBER_SURFACE.md` を正本とする。

### 2.6 Run271 — Member Body Delta Sync

Run270本番反映ではMember Presentation DB **206件**の本文移行に約13分23秒を要した。Run169.1でgenerated-only pageの親callout再構築は既に導入済みだったため、Run271はsteady-stateの主因である**全206ページのblock GET / body一致判定**を通常運用から外す。

Run271.1では `Member Presentation Sync` がGitHub Actions read APIから**前回成功したmainのMember Presentation Syncの `run_started_at`** を取得し、それを `MEMBER_BODY_CHANGED_SINCE` とする。body phaseはNotion DB一覧を1回取得した後、原則として `last_edited_time >= MEMBER_BODY_CHANGED_SINCE` のページだけをblock GET / write対象にする。前回成功runの開始時刻を使うことで、前回run実行中またはrun間に手動・自動で編集されたgenerated bodyも次回に再検査する安全なoverlapを持つ。

ただし高速化でmigration safetyを弱めない。

- delta runごとにgenerated bodyを**sentinel 1件**だけcurrent body contractと照合する。
- sentinelが一致すればchanged pagesだけ本文I/Oする。
- 前回成功checkpointを取得できない場合はcutoffを空にし、**full scanへFail-Closed fallback**する。
- sentinel不一致、`MEMBER_BODY_FORCE_FULL=true`、cutoff欠落時は**full scanへ自動fallback**する。
- checkpoint取得には既存workflow tokenの `actions: read` のみを追加し、GH_PATや新規secret、有料APIを追加しない。
- push-triggered member presentation workflowはbody contract変更の可能性を考慮してfull modeとする。
- workflow rerun（`github.run_attempt > 1`）もrecoveryのためfull modeとする。
- manual `workflow_dispatch` は `force_full_body_sync` で明示full migrationできる。
- manual Notion block保護、Run270見出し、Evidence / Decision / source / Deep Tech、Notion schema、ZERO Gemini/model call契約は変更しない。

詳細・反証・Production timingは `docs/reference/RUN271_MEMBER_BODY_DELTA_SYNC.md` を正本とする。2026-09-07の通常delta Production観測では、206件中 `scanned_body_pages=0` / `skipped_by_delta=206` / `sentinel_checked=1` / `delta_fallback_full=false`、本文stepは約**2.34秒**だった。Run270の約13分23秒比で約**343.4倍高速・99.71%短縮**、Run271.1 push安全fullの約130.78秒比で約**55.9倍高速・98.21%短縮**。これは単一のno-change Production観測値でありSLAではない。

---

## 3. Decision Brief / Decision Update 契約 — Run256 / Run270

Decision Briefは静的な「今月のおすすめ一覧」だけにしない。
- 今月の主要候補を3〜7件へ絞る。
- `使う / 試す / 待つ / 避ける` の判断を出す。
- 顧客案件・技術選定への意味、確認事項、次の一手を短く示す。
- **技術選定・提案判断を変えるmaterial changeが存在する場合、少なくとも1件は具体例をBrief本文へ出す。** 一覧リンクだけで代替しない。
- material changeがない月は、無理に変化を作らず **「重要な判断変更なし」** を価値として示す。
- 生の `82 → 91` を継続課金価値の中心にしない。何が変わり、判断を変える必要があるかへ翻訳する。
- 既存のStatus変更・Decision Score差分・INITIAL判定を壊さない。
- 表示ロジックのためにNotion schemaを増やさない。
- 表示ロジックのためにGemini/model APIを追加しない。

material change表示は、既存履歴から可能な範囲で **変更 / 現在の判断 / 理由 / 根拠 / 次のAction** を明示する。Evidenceが記録されていない場合は捏造せず、その事実を明示する。

Decision Updateは Changed / New / Unchanged-important を扱えるが、個別Watchlistや通知パーソナライズはPMF前に実装しない。

2026年9月の編集上の確認例:
- `FlowiseAI/Flowise` — 公式GitHub Archivedを根拠に、新規AIワークフロー基盤としてはAVOID、既存構成の保守・移行判断に限定する例。runtimeへこの固有例をhard-codeしない。

---

## 4. Core Intelligence Pipeline

Production pipelineは、候補収集 → Screening → Deep Dive / Evidence → Decision → Stock / Member DB → 無料記事候補という既存契約を維持する。

Run268以降、Production入口 `production_pipeline.py` は歴史的runtime layerを維持したまま `run268_business_source_strategy.install` を後段適用する。Source取得戦略の変更で記事品質・Evidence・Gemini budgetのwrapper順序を変更しない。OfficialVendor取得とHN絞り込みは追加Gemini/model callを使わず、公開HTTPをboundedに利用する。Vendor単位の取得失敗はfault-isolatedとし、他Sourceを停止しない。

### HackerNews Precision — Run269

Run269はRun268のfour-source architectureを変更せず、実ネットワークで発見した取得精度だけを後段overlayで補正する。HNはAlgolia `search_by_date` を使い、`tags=story`、title限定、直近**30日**に絞る。raw query `AI`は使わず、結果を `_query_matches_title` で再検査し、**exact token / exact phrase** 一致のみ採用する。これにより `Qwen -> jQuery` のようなtypo tolerance由来のfalse matchをProduction候補へ入れない。

OfficialVendorは `structured_html` / `structured_embedded` / `structured_current_state` / `page_fallback` を区別する。`page_fallback` は「到達できたが更新一次情報を構造化できていない」状態であり、Strict Live Smokeでは合格とみなさない。ByteDance/Volcengineの公式モデル一覧のように商用選定上の現在状態が正本となる面は、架空のrelease eventへ変換せず `structured_current_state` として扱う。

Run269は `production_pipeline.py` でRun268 install後に適用し、Source architecture、Evidence/Decision、Gemini budget、Notion write経路を変更しない。Live Acquisition Smokeは11 Vendorを個別fault isolationし、Gemini/model 0、Notion write 0、Production DB write 0、公開処理0で実ネットワークだけを検査する。2026-09-07の最終Live SmokeではOfficialVendor **11/11 structured成功（US 3/3、CN 8/8、fallback-only 0）**、HN 20候補/11 query/30日を確認した。詳細は `docs/reference/RUN269_LIVE_ACQUISITION_PRECISION.md` を正本とする。

重要な非交渉事項:

- Fact / Evidence / DecisionのHARD BLOCKを商品都合で弱めない。
- 一次情報・Evidence境界を保持する。
- Source scoreを顧客適合度へ置換しない。
- Deep Techを削除しない。
- canonical DBと会員表示層を分離する。
- 429 / 404 / 503等はFail-Closedまたは既存Retry Budgetに従う。
- Google Search GroundingはOFF。
- 新しい有料APIを追加しない。
- Gemini/model呼出しを表示専用ロジックへ追加しない。

Pipeline modularizationの現行境界はRun245を基準とし、巨大な単一ファイルへ機能を戻さない。

### 4.1 Active runtime manifest — Documentation Freshness Guard対象

`production_pipeline.py` が現在保護するactive runtime layerは以下。Documentation Freshness Guardは、これらがcanonical仕様から無言で消えた場合Fail-Closedする。

- `run203_runtime_state_channel.py`
- `gemini_timeout_rpd_fail_closed.py`
- `gemini_transient_recovery.py`
- `gemini_provider_resilience.py`
- `run260_gemini_model_routing.py`
- `run172_production_reliability.py`
- `run173_operational_yield.py`
- `run174_monthly_digest_integrity.py`
- `run175_semantic_fact_precision.py`
- `run223_technical_claim_precision.py`
- `run224_multiplier_deterministic_rescue.py`
- `run227_japanese_surface_integrity.py`
- `run176_scope_fidelity.py`
- `run177_paid_funnel_alignment.py`
- `run226_reader_delight_planning.py`
- `run228_reader_rhythm_planning.py`
- `run178_eyecatch_editorial_layout_optimizer.py`
- `run179_eyecatch_font_refinement.py`
- `run180_eyecatch_semantic_layout.py`
- `run181_eyecatch_visual_balance.py`
- `run182_eyecatch_conclusion_emphasis.py`
- `run183_eyecatch_emphasis_scale.py`
- `reader_value_review_bridge.py`
- `run208_reader_value_repair.py`
- `run222_note_presentation_integrity.py`
- `run296_editorial_format_v2.py`
- `run248_first_real_publish_quality_calibration.py`
- `run249_final_publication_surface_gate.py`
- `run194_publication_contract.py`

この一覧は「古いRun番号だから削除してよい」という意味ではない。現在のruntime manifestから外す場合は、実装・回帰・仕様・Guardを同時に意図的更新する。

---

## 5. Gemini / Provider契約

- 基本はGemini Free Tier運用。
- ONE-SHOTのFlash安全上限は現行Guardに従う。
- RPD/RPM/TPM、Retry Budget、安全弁を超えて無理に実行しない。
- API枯渇・quota不明時は推測で実行しない。
- Geminiは記事生成等の限定された生成担当であり、主要な設計判断・コード判断のAuthorityにしない。
- Geminiの生成結果はEvidence / tests / 別ロジックで検証する。
- ZERO-provider-callで可能な表示・監査・移行はZERO-provider-callを優先する。

Run209 quota / retry保護:

- pre-send reservationを巻き戻さない。
- timeout後に「未使用だった」と推測してquotaを返却しない。
- Pending Retry fast laneは **最大3 requests**。
- **1回目のHTTP 503** は、Run303で構造化されたprovider status code=503を確認した場合に限り、同一モデルで1回だけ確認再試行する。
- 2回連続のverified HTTP 503で初めて、そのmodelのrun-local circuitを開く。
- 200成功、transport timeout、429、404、その他non-503結果は503連続系列を切り、過去の503累積でmodelをcooldownしない。
- transport timeoutはHTTP 503と別障害として記録し、Run209のRPD fail-closed reservation保持を維持する。
- Run303の確認再試行は既存per-run / persistent daily / Pending Retry / Product Review budgetの内側でのみ動作し、Gateやrequest ceilingを拡張しない。
- `Reader Value repair` の追加消費を既存budget外へ拡張しない。

Run261 article model routing:

- Fresh Deep Diveは **`gemini-3.7-flash`** をPrimaryとする。
- Fresh Deep Dive fallbackは **`gemini-3.8-flash` → `gemini-3.6-flash` → `gemini-3.5-flash`**。
- 既存のmodel-based `quality_retry`は **`gemini-3.8-flash`** を先頭にする。
- 3.8が使えない場合は **3.6 → 3.5 → 3.7** の順でbounded fallbackする。
- Screeningは既存Flash-Lite poolを変更しない。
- deterministic zero-API rescueは3.8 callへ置換しない。
- Run260の`_call_model_pool` routingはdefense-in-depthとして保持し、**Run261は実Production入口 `_call_deep_dive_pool` でもquality repair順を強制する**。
- Run261のlive-path wrapperは既存`_call_model_pool`へ1回だけ委譲し、新規retry loop・Gate緩和・追加のDeep Dive枠を作らない。
- `gemini-3.8-flash`のrepository-local安全上限は最大18 requests/day。`GEMINI_38_FLASH_DAILY_BUDGET`は18以下へ下げるためだけに使う。
- Deep Dive全体のper-run 12 requests上限は維持する。
詳細は `GEMINI_QUOTA_SETUP.md`、`docs/reference/RUN261_LIVE_ROUTING_AND_FANOUT_REPAIR.md`、`docs/reference/RUN260_GEMINI_37_PRIMARY_38_QUALITY_RESCUE.md`、current runtime code、Google AI Studio Rate Limitsを正本とする。

---

## 6. 無料note記事契約

無料noteはAcquisitionであり、品質を下げてPaywall gapを作らない。

読者体験:

- 中学生〜非エンジニアでも核心を理解できる。
- 専門性・Evidence・Decision価値は維持する。
- 読み物として面白く、再訪したくなることを重視する。
- 身近な例・比喩・語り口は理解補助として使うが、事実を捏造しない。
- 固定テンプレート感、AI glue、短文連打、機械的列挙を避ける。
- Reader Experience / Human Appeal / Editorial Naturalnessを独立監査する。

### Run226 Reader Delight Planning

**Run226** / `run226_reader_delight_planning.py` は、Evidence境界を保持したまま記事設計に人間的な編集視点を入れるactive layerである。Reader Tension / Discovery / Concrete Consequence / Explanation Bridge / Editorial Point of Viewを編集レンズとして使うが、**回数ノルマ**や固定Hook配分へ変換しない。比喩・問い・scene・会話調は、理解を自然に助ける場合だけ使う。

Article production surface:

- Run248: real-note quality calibration
- Run249: final assembled public-surface revalidation
- Run261: Gemini 3.7 primary / Gemini 3.8 bounded quality repair at the live Deep Dive entrypoint
- Public releaseは**human-only**。自動化はprivate draftまで。

### Run296 Reader-approved Note Editorial Format v2

最初の実note Private Draftの人間レビューをProduction標準へ反映する。`run296_editorial_format_v2.py` はRun222後段のreader-facing surfaceを正規化し、追加Gemini/model requestを作らない。

- 記事冒頭は `どんな内容？` とし、`30秒でわかるこの記事` と `何が出た？` を廃止する。
- 有料CTAは `有料サブスクのご案内`、指定本文、`詳しくはこちら` をcanonical copyとし、既存tracking URLは保持する。
- 長い記事タイトルをアイキャッチへそのまま複製せず、意味を保った短いvisual copyへ圧縮する。
- `舞台裏` 等の保護対象複合語を行境界で分割しない。
- highlightは意味の完結したフレーズを使い、Netflix GenRecでは `舵を切った理由` 全体を強調する。
- アイキャッチ下部説明文/subheadlineは描画しない。
- Netflix GenRecのreviewed specimenは `Netflix推薦の舞台裏` / `LLMネイティブへ` / `舵を切った理由` の3行をdeterministicに使う。
- Public releaseは引き続きhuman-only。既存private draft更新は別のspecimen-bound workflowでin-place実施し、read-only監査を再実行する。

### Eyecatch

Run183 current stackを基準とする。Run181 → Run182 → Run183の順序はactive runtime contractである。

- Run181: visual balance / mixed-size geometryの現行基礎
- Run182: 結論強調に使うexact highlight substringの選択・検証
- Run183: approved emphasis scaleを適用し、`HIGHLIGHT_FONT_SCALE = 1.20`、`HIGHLIGHT_MAX_FONT = 96`
- 1280×670
- approved background/right illustrationを保持
- title 2行推奨、最大3行許容
- オレンジ強調 `#F28C28`
- reader-purpose badge / category/date / source-bounded subcopy
- Productionでapproved background/illustrationを勝手に置換しない

---

## 7. Notion / Member Data契約

- Member Presentation DBは会員向け読みやすさを担う表示層。
- canonical Decision / EvidenceをPresentation都合で壊さない。
- schema変更は必要性が明確な場合のみ。
- PIIをGitHub artifactへ持ち込まない。
- Notion write先はfail-closedで解決する。
- Sourceが返した日付文字列はEvidence/current-state契約として取得層で保持し、Notion `date.start` へ入れる直前にだけRun272のdate boundaryで検証・正規化する。既知形式はISOへ変換し、解釈不能な値は推測せず空欄へfail closedする。
- CI greenだけで本番反映完了としない。実Notionの見出し、順位、copy、source preservationを直接監査する。
- Physical API hostとlinked viewsの役割を分離し、Run221のhosting boundaryを維持する。

Run250–256で確立したproduct presentation履歴:

- Run250: initial paid-product presentation overlay
- Run251: legacy fixed shortlist retirement
- Run252: `__main__` production script-entrypoint authority
- Run253: Work-First correction
- Run254: unnecessary first-person removal
- Run255: context-safe / natural neutralization
- Run256: concrete Decision Update + documentation reconciliation

Run270は上記を削除せず、Run250の後段で現行Proposal-First visible surfaceを適用する。

### Member表示順 — Run270

会員向け詳細は既存canonical値を使い、原則として次を表示する。

- `これは何？`
- `顧客にどう答える？`
- `提案できる場面`
- `なぜ今見る？`
- `提案前に確認すること`
- `提案・検証の次の一手`
- material changeがある場合 `Decision Update｜提案を変える必要がある？`
- 公式・一次情報

Source score / Decision / Evidence / Deep Tech分類を顧客適合のために改変しない。ICP relevanceはNavigation-only。Run270ではRun250のproven navigation rankerを維持し、表示AuthorityだけをProposal-Firstへ更新する。

### 日本語表現

主語省略を基本とする。

- `自分の仕事に使える` → `仕事に使える`
- `自分の利用条件` → `利用条件`
- `自分の作業時間` → `作業時間`

ただし `自分だけ / 少人数 / チーム` のように主体差が意味を持つ場合は残す。中立化より自然で意味が保たれる日本語を優先し、`自社`を機械的に一律置換しない。

---

## 8. 運用契約

- **Daily workflowはPAUSED。**
- Production実行は明示的なONE-SHOT / workflow_dispatchを基本とする。
- PAUSED中の派生workflowは、存在しない通常Daily aliasやPAUSED stubを`workflow_run`上流に持たない。Run257 `Workflow Reference Guard` が静的参照をFail-Closedで検査する。
- ChatOpsからONE-SHOTを起動する場合、Run259として `GH_PAT` を必須にする。
- ONE-SHOT成功後の直接fan-outはRun261として `GH_PAT` による明示 `workflow_dispatch` を必須とし、Note Ready / Subscriber Decision Brief / Cross DBをdispatchする。直接対象3本はONE-SHOTのpassive `workflow_run`を併設しない。
- GH_PAT未設定またはdownstream dispatch失敗はfail closedとし、部分成功を正常扱いしない。
- Public note公開はhuman-only。
- 外部サービス状態を推測で補完しない。
- 成功していない処理を成功扱いしない。
- CI greenは必要条件であり、Production実物監査の代替ではない。
- 本番変更は小さく、回帰可能にし、Source/Evidence/Decisionを保護する。

### 8.1 Deterministic CI / zero-provider回帰契約 — Run263 / Run264

Run263以降、`Integration Reconciliation CI` はProduction不具合とCI自身の揺らぎを分離するため、hermetic / locked / zero-providerをcurrent contractとする。

- runnerは `ubuntu-24.04`、Pythonは `3.11.16`。
- checkout / setup-python actionはknown-good SHAへ固定する。
- Production dependency rangeは `requirements.txt`、CI再現性は `requirements-ci-constraints.txt` をAuthorityとする。
- pytestはknown-green `8.4.2` をconstraint経由で使い、`python -m pip check` を通す。
- `GEMINI_PERSISTENT_DAILY_COUNTER='false'` とし、deterministic CIがrepository-backed Production counterへ触れない。
- pytestのautouse network guardを維持し、予期しないexternal network accessをFail-Closedする。
- Integrationはstructural guards → **full pytestを1回** → current Production stackのSynthetic smokeという順を維持する。
- Run264以降、standalone `Synthetic Regression Suite` も同じhermetic/locked/pytest契約を使い、旧 `unittest discover` 全件実行へ戻さない。
- これらの回帰はGemini/Notion等のProduction call・Production writeを行わない。
詳細は `docs/reference/RUN263_INTEGRATION_HERMETICITY_AND_STABILITY.md`、`docs/reference/RUN264_STANDALONE_SYNTHETIC_HERMETICITY.md`、`integration_stability_guard.py` を正本とする。

### 8.2 Dependency compatibility契約 — Run265 / Run266

- Production dependency rangeのAuthorityは `requirements.txt`。
- CI known-green exact graphのAuthorityは `requirements-ci-constraints.txt`。
- Run265でPillow deprecated API `Image.getdata()` のdirect使用を排除し、`get_flattened_data()`へ移行した。
- そのAPI契約に合わせ、Run266以降のProduction Pillow rangeは **`Pillow>=12.1.0,<13.0.0`**。
- 現行CI known-green pinは **`Pillow==12.3.0`**。
- `<13.0.0` の上限は現在も有効であり、Pillow 13/14をProduction対応済みとは扱わない。上限を広げる場合は別途compatibility auditと回帰を行う。
- warning suppressionでdeprecated APIを隠す方式へ戻さない。

### 8.3 main required status check governance — Run267

2026-09-07のGitHub Ruleset `Protect main production` 直接監査で、default branchに対するrequired status contextは次の3つ。

- `zero-api-regression`
- `falsify-all-tracked-surfaces`
- `notion-access-policy`

**required status checkに指定されたWorkflowは、対象PRで必ずcheck contextを生成できなければならない。** required contextを出すWorkflowの`pull_request`に変更ファイル依存の **pull_requestのpath filterを置かない**。path filterでWorkflow自体がskipされると、required contextが`Expected`のままになり正常なPRをmerge不能にできるためである。

- `zero-api-regression`: `Integration Reconciliation CI`。main向け全PRで起動し、`paths` / `paths-ignore`を置かない。
- `falsify-all-tracked-surfaces`: `Repository-wide Falsification Guard`。main向け全PRで起動する。
- `notion-access-policy`: `Notion Access Policy Guard`。全PRで起動し、Run266以降path filterを置かない。
- required job/context名を無断で変更しない。変更する場合はGitHub RulesetとWorkflowを同一reviewed changeで更新し、direct ruleset auditを行う。
- GitHub Rulesetはrepository外部状態なので、zero-network CIだけでRuleset自体の変更を検知したとは主張しない。外部設定変更時は直接監査する。

Run267 `run267_documentation_contract_guard.py` は、上記3WorkflowのPR triggerがpath-filteredへ戻らないこと、job context名、Pillow契約、Run183 Eyecatch baseline、Run263/264 current CI contractをFail-Closedで保護する。

### 8.4 Daily failure-tail hardening — Run272

Run272は、Run `34075019008` の45分cancelを「Workflow全体が遅い」と一括処理せず、外部障害と後段処理のfailure tailを分解して有界化したoperational reliability契約である。

- Production本体の完了と、後段Product Reviewのtimeoutを区別する。Global Daily timeoutは**45分のまま**で、延長して問題を隠さない。
- `notion_payloads.py` はNotion `date.start` へ渡す直前だけ既知の日付形式をISOへ正規化する。取得層のraw `publishedAt` は保持し、Run269のEvidence/current-state契約を変えない。解釈不能な日付は捏造せず空欄へfail closedする。
- `product_delivery_maintenance.py` のEvidence Healthは、arXivで最初の `FETCH_ERROR` を観測したらそのrunだけarXiv circuitを開く。残りarXiv候補はdeferし、non-arXiv候補は継続する。
- provider unavailableを `MISSING` / `MATERIAL_CHANGE` と誤認せず、deferred arXiv候補のEvidence Ledger healthを障害だけを理由に書き換えない。
- `daily_portfolio_review.py` はProduct Review childを既定**600秒**へ有界化する。Run305以降、childはraw `pipeline.py`を直接起動せず、`AIIF_PRODUCT_REVIEW_RUNTIME=true` を付けた唯一のroot authority `production_pipeline.py` を起動する。timeout時もpartial outputへunsafe-activity detectorを適用し、安全なら `bounded_child_timeout` としてdeferする。
- Gemini request budget / retry budget / RPD safety ceiling、Run268 four-source architecture、Fact/Evidence/Decision gate、Public release契約は変更しない。
- 反証過程で、取得層の日付正規化と `source_normalization.install()` 公開面拡張は既存契約を壊すため撤回された。Run272はpersistence/maintenance/deadline境界に限定する。

詳細は `docs/reference/RUN272_DAILY_FAILURE_TAIL_HARDENING.md` を正本とする。

### 8.5 Product Review provider runtime — Run304 / Run305

Run37でProduct Review childがlegacy `main` counterを読み `Persistent Gemini Daily Counter: 0` と誤認する不具合を確認し、Run304で親Productionの `AIIF_RUNTIME_STATE_BRANCH` をchildの `GEMINI_COUNTER_BRANCH` へ継承した。Run38で非ゼロcounterの継承と3.6の5/18→8/18更新を実環境確認した。

Run38は同時に、raw `pipeline.py` childがRun209/Run303 provider/quota runtimeをinstallしていない別の経路欠落も示した。Run305以降は `production_pipeline.py` を唯一のroot entrypointとして維持し、`AIIF_PRODUCT_REVIEW_RUNTIME=true` のときarticle/publication stackより前に次の4層だけを適用する。

1. `run203_runtime_state_channel.install`
2. `gemini_timeout_rpd_fail_closed.install`
3. `gemini_transient_recovery.install`
4. `gemini_provider_resilience.install`

その後Run203 runtime-state preflightを実行してから既存product-only coreへ進む。Product Reviewのモデル順 `3.6 → 3.7 → 3.8 → 3.5`、max reviews 2、local request budget 3、persistent daily safety capは変更しない。Run260 Article Model Routing、Run172 article/evidence overlay、article/publication/Reader Value/eyecatch layerはProduct Review専用runtimeへ導入しない。Run303の1回目verified 503同一model確認再試行も既存Product Review budget内に限定する。

詳細は `docs/reference/RUN305_PRODUCT_REVIEW_PROVIDER_RUNTIME.md` と `GEMINI_QUOTA_SETUP.md` を正本とする。

---

## 9. 回帰・反証契約

最低限、変更領域に応じ以下を通す。

- Repository-wide Falsification Guard
- Workflow Reference Guard
- Integration Reconciliation CI
- Synthetic Regression
- Notion Access Policy Guard
- Cross DB Contract Guard（該当時）
- Documentation Freshness Guard
- Run262 Documentation Contract Guard
- Run267 Documentation Contract Guard
- Run268 Business / Source Strategy Guard
- Run269 Acquisition Precision Guard
- Run270 Proposal-First Member Surface Guard
- Run271 Member Body Delta Sync Guard
- Run272 Daily Failure Tail zero-API regression tests
- 関連unit tests / full pytest
- Production Notion direct audit（Member UI変更時）
- Public surface direct audit（note/article変更時）

特に表示ロジックでは、テストが緑でも次を反証する。

- 実行中moduleとimport moduleのAuthorityずれ
- Run270より後にRun250が再適用されていないか
- stale bodyをcurrentと誤認
- Run271 delta scopeがchanged pages以外へ不要なblock GETを広げていないか
- Run271 sentinel不一致時にfull fallbackできるか
- Run271.1 checkpointが前回成功runの開始時刻を使い、取得失敗時にfull fallbackできるか
- 文字列置換による不自然な日本語
- old fixed shortlistの復活
- Source score / Evidence / Deep Techの意図しない変異
- 顧客提案が再びSecondary扱いになっていないか

Run272の運用信頼性変更では、さらに次を反証する。

- OfficialVendor等のraw source dateを取得層で勝手にISOへ書き換えていないか
- 既知の日付だけがNotion境界でISO化され、不正値がHTTP 400を起こすpayloadとして残っていないか
- arXiv最初のFETCH_ERROR後に同一runで残りarXivへ再試行連鎖していないか
- arXiv provider failureをMISSING/MATERIAL_CHANGEへ誤分類・永続化していないか
- arXiv circuit open後もGitHub等non-arXiv health checkが継続するか
- Product Review child timeout時にもpartial outputのunsafe検査を飛ばしていないか
- Product Review timeoutがDaily全体の成功を偽装せずstructured deferredとして観測できるか
- global Daily 45分上限やGemini budgetを安易に拡張していないか

Gemini model routing変更では、さらに次を反証する。

- Screening Flash-Lite poolを意図せず変更していないか
- Fresh Deep DiveのPrimaryが3.7になっているか
- model-based quality repairだけが3.8先頭になるか
- 実Production入口 `_call_deep_dive_pool` でもquality repairが3.8先頭になるか
- 3.8追加でDeep Dive per-run 12、Pending Retry、persistent safety capを迂回していないか
- deterministic zero-API rescueを不要なprovider callへ置換していないか
- Gate閾値をReady件数目的で緩めていないか

Workflow / CI変更では、さらに次を反証する。

- `run:` / `- run:` が削除済みrepository-local scriptを指していないか
- `python -m unittest tests.*` が実在するmoduleか
- `uses: ./...` / `- uses: ./...` のlocal actionが実在するか
- `workflow_run.workflows` が実在するtop-level workflow nameか
- static `gh workflow run` targetが実在するか
- duplicate workflow nameによる曖昧性がないか
- workflow内workflow dispatchが必要なfan-outを持つ場合、repository `GITHUB_TOKEN` による連鎖抑制を踏んでいないか
- ONE-SHOTの直接fan-out targetが `workflow_dispatch` を受け付けるか
- 同じdirect targetにONE-SHOT passive `workflow_run`を残して二重write経路を作っていないか
- required status contextを出すWorkflowへ`pull_request.paths` / `paths-ignore`を追加していないか
- required job/context名とGitHub Rulesetの対応を無断で変えていないか
- Integration / standalone Syntheticがlocked dependency、pytest network isolation、persistent counter OFFのhermetic contractから外れていないか

---

## 10. 現在の商業優先順位

利益に近い順に判断する。

**顧客需要 → 売れるか → 継続するか → 粗利 → 自動化 → 技術的完成度**

現在の優先順位:

1. Paid Product / LP / Offerの整合
2. 実有料顧客10人の獲得
3. 初月利用・継続理由の観測
4. Decision Update / Proposal Actionの価値検証
5. 集客チャネル拡張
6. 法人版は実需要が見えてから

PMF前にやらないこと:

- 広告費の大規模投入
- 大規模SNS自動化
- 個別Watchlist/通知の作り込み
- 法人向け請求書・席管理・SSO・管理画面
- 大量テンプレート販売へのピボット
- 技術的な美しさだけを目的にした大改修

---

## 11. Documentation Governance

本ファイルは、商品・Production契約が変わったRunで更新する。

- 現行仕様は読みやすく保つが、active runtime / Fail-Closed / customer destination / quota safety / deterministic CI / dependency compatibility / required-check governance / operational failure-tail boundingの保護契約を「古いから」という理由で削らない。
- 詳細な変更理由・反証記録は `docs/reference/RUNxxx_*.md` へ置く。
- 純粋な履歴説明は `docs/archive/` とGit履歴へ置く。
- current code/tests + 本書 + `PAID_PRODUCT_CONTRACT.md` の整合を保つ。
- Documentation Freshness Guardが要求するmarkerは、テストを通すための文字列ではなく、現在Productionが依存するoperational contractとして扱う。
- Run257のWorkflow参照修整・反証記録は `docs/reference/RUN257_WORKFLOW_REFERENCE_INTEGRITY.md` を正本とする。
- Run259のChatOps dispatch修整・反証記録は `docs/reference/RUN259_CHATOPS_FANOUT_TOKEN.md` を正本とする。
- Run260のGemini routing導入契約は `docs/reference/RUN260_GEMINI_37_PRIMARY_38_QUALITY_RESCUE.md` を履歴/基礎契約として保持する。
- Run261の実Production入口Gemini routingとONE-SHOT explicit fan-out契約は `docs/reference/RUN261_LIVE_ROUTING_AND_FANOUT_REPAIR.md` を現行正本とする。
- Run262はcanonical仕様がRun260/Run259の旧mechanismへ戻らないよう `run262_documentation_contract_guard.py` で必須CIからFail-Closedする。
- Run263のIntegration hermeticity / deterministic CIは `docs/reference/RUN263_INTEGRATION_HERMETICITY_AND_STABILITY.md` と `integration_stability_guard.py` を正本とする。
- Run264のstandalone Synthetic hermeticityは `docs/reference/RUN264_STANDALONE_SYNTHETIC_HERMETICITY.md` と `integration_stability_guard.py` を正本とする。
- Run265/266のPillow compatibility結果とRun267のrequired-check/canonical同期は `docs/reference/RUN267_CANONICAL_SPEC_SYNC.md`
- `docs/reference/RUN268_BUSINESS_SOURCE_STRATEGY.md` に現行Source architecture / paid-product要約を保持する。
- Run269のLive Acquisition Precision / 11-Vendor structured smoke / HN exact-match契約は `docs/reference/RUN269_LIVE_ACQUISITION_PRECISION.md` を正本とする。
- Run270のProposal-First Member Surface / static Notion surface契約は `docs/reference/RUN270_PROPOSAL_FIRST_MEMBER_SURFACE.md` を正本とする。
- Run271/271.1のdelta-scoped Member body sync / previous-success checkpoint / sentinel fallback契約は `docs/reference/RUN271_MEMBER_BODY_DELTA_SYNC.md` を正本とする。
- Run272のNotion date boundary / arXiv run-local Evidence Health circuit / bounded Product Review child契約は `docs/reference/RUN272_DAILY_FAILURE_TAIL_HARDENING.md` を正本とする。
- Run303のverified HTTP 503 / consecutive-only circuit / timeout分離契約は `docs/reference/RUN303_GEMINI_PROVIDER_503_RESILIENCE.md` を正本とする。
- Run305のProduct Review counter authority / provider-quota runtime / sole production entrypoint契約は `docs/reference/RUN305_PRODUCT_REVIEW_PROVIDER_RUNTIME.md` を正本とする。
- Run267はRun263〜266以降のcurrent CI/dependency/Eyecatch/required-check契約がcanonical仕様から脱落しないよう `run267_documentation_contract_guard.py` でFail-Closedする。
- Run269はRun268のSource architectureを上書きせず、取得精度だけを `run269_acquisition_precision_guard.py` でFail-Closedする。
- Run270はRun250を歴史層として保持し、最終member surfaceだけを `run270_proposal_first_member_surface_guard.py` でFail-Closedする。
- Run271.1は通常本文同期を前回成功run以降のchanged pagesへ限定しつつ、checkpoint取得失敗 / sentinel mismatch / explicit force / recovery時のfull fallbackを `run271_member_body_delta_sync_guard.py` でFail-Closedする。
- Run272は専用zero-API regression `tests/test_run272_daily_failure_tails.py` と既存Repository-wide / Integration / Run269契約の組合せで、修正がSource Evidence・Notion・Product Review safetyを横断破壊していないことを反証する。
- Run262 GuardはRun261 live routing/fan-outのfocused guardとして残し、Run267 Guardがpost-Run262 current governanceを補完する。これらとRun268/269/270/271 GuardをRepository-wide Falsification Guard内で実行する。

**現在のPaid Product Strategy正本はRun268。**  
**現在のMember Surface正本はRun270。**  
**現在のMember Body Sync正本はRun271.1。**  
**現在のSource Architecture正本はRun268。**  
**現在のAcquisition Precision正本はRun269。**  
**現在のOperational Reliability正本はRun272。**  
**現在のProvider Resilience正本はRun303。**  
**現在のProduct Review Provider Runtime正本はRun305。**  
**現在のWorkflow Reference Integrity正本はRun257。**  
**現在のChatOps Dispatch正本はRun259。**  
**現在のArticle Model Routing正本はRun261。**  
**現在のONE-SHOT Downstream Fan-out正本はRun261。**  
**現在のIntegration Determinism正本はRun263。**  
**現在のStandalone Synthetic Hermeticity正本はRun264。**  
**現在のDependency Compatibility正本はRun266。**  
**現在のDocumentation Contract Freshness正本はRun267。**

### Run268 — Proposal-First / Four-Source Intelligence

- Primary ICPを顧客へAI・Web・業務システムを提案・開発する1〜3名規模のフリーランス/小規模開発事業者へ再定義。
- 自己学習はSecondary Valueへ降ろし、判断・提案メモを有料価値の中心Artifactへ格上げ。
- active Sourceを GitHub / HackerNews / ArXiv / OfficialVendor の4系統へ再編。
- Product Hunt Production取得を退役し、OfficialVendorへ置換。新しいAPIキー・有料APIは追加しない。
- HNはFirebase Top Stories全巡回からbounded Algolia AI queryへ変更し、取得段階で市場・エンジニア反応へ絞る。
- OfficialVendorは米国3 + 中国主要8を1 Source内のvendor-level round robinで公平化する。
- Run268 guardはProduction入口、active source tuple、Vendor registry、Product contract、本仕様書、CI組込みをzero-networkでfail closed検証する。

### Run269 — Live Acquisition Precision / Structured Vendor Evidence

- Run268のfour-source architecture・ICP・Product contractは変更しない。
- HN Algoliaをtitle限定・30日・exact token / exact phrase再検証へ強化し、typo toleranceのfalse matchを除外する。
- OfficialVendorのナビゲーション文言を更新候補へ昇格させず、`structured_html` / `structured_embedded` / `structured_current_state` / `page_fallback` を区別する。
- `page_fallback`だけではStrict Live Smokeを合格させない。
- ByteDance/Volcengineの公式モデル一覧は架空のreleaseではなくcurrent-state一次情報として扱う。
- 実ネットワーク最終SmokeでOfficialVendor 11/11 structured成功、US 3/3、CN 8/8、fallback-only 0、HN 20 candidates / 11 queries / 30日を確認した。
- Live SmokeはGemini/model 0、Notion write 0、Production DB write 0、publication 0を維持する。
- Run269 GuardはProduction install順、HN precision、Vendor registry/current-state、Live Smoke safety、canonical仕様、CI組込みをzero-networkでfail closed検証する。

### Run270 — Proposal-First Member Surface

- Run268のPrimary ICPとPaid Product contractを実会員表示へ反映する。
- Run250 Work-First rendererは歴史的互換層として残し、Run270をその後段に適用して最終可視AuthorityをProposal-Firstへ切り替える。
- Member detail bodyは `顧客にどう答える？` / `提案できる場面` / `提案前に確認すること` / `提案・検証の次の一手` を中心にする。
- Home / Decision Brief / AI導入 判断・提案メモも同じPrimary Jobへ同期する。
- Evidence / Decision Score / canonical status / Source / Deep Tech / Notion schemaは変更しない。
- Run250 navigation rankerはRun270では維持し、未検証の大きなranking再設計を同時導入しない。
- ZERO Gemini/model calls。
- Run270 GuardはRun250→Run270 install順、Proposal-First contract、member workflow test、static Notion page IDs、canonical仕様、required Falsification組込みをzero-networkでfail closed検証する。

### Run271 — Member Body Delta Sync

- Run270のvisible body contractは変更せず、steady-stateの本文同期I/Oだけをdelta化する。
- Run271.1では `MEMBER_BODY_CHANGED_SINCE` を前回成功したmainのMember Presentation Sync `run_started_at` から解決し、それ以降に編集されたMember pagesだけを通常のblock GET/write対象にする。
- delta runではsentinel 1件をcurrent body contractと照合し、不一致なら全件scan/migrationへfallbackする。
- checkpoint取得失敗 / push / rerun / explicit `force_full_body_sync` はfull modeを選ぶため、手動編集・本文契約変更・recoveryをdelta最適化で取りこぼさない。
- workflow履歴取得は `actions: read` のみを使い、新規secret・GH_PAT・有料APIは追加しない。
- manual Notion blocks、Evidence / Decision / Source / Deep Tech / schema、ZERO Gemini/model call契約を保持する。
- 2026-09-07の通常delta Production観測では本文step約**2.34秒**、`scanned_body_pages=0`、`skipped_by_delta=206`、`sentinel_checked=1`、`delta_fallback_full=false`。Run270約13分23秒比で約**343.4倍高速・99.71%短縮**。単一no-change観測でありSLAではない。
- Run271 Guardはprevious-success checkpoint / delta cutoff / sentinel / full fallback / workflow recovery / canonical仕様 / required Falsification組込みをzero-networkでfail closed検証する。

### Run272 — Daily Failure-Tail Hardening

- Run34075019008の45分cancelを、Production本体・Evidence Health・Product Reviewへ分解して根因を反証した。
- Notion dateはsource raw valueを保持したまま、persistence boundaryだけでISO化し、不正値は空欄へfail closedする。
- arXiv Evidence Healthは最初のFETCH_ERRORでrun-local circuitを開き、残りarXiv checkをdeferする。non-arXiv checkは継続し、provider unavailableをEvidence消失へ変換しない。
- Product Review childは既定600秒へbounded化し、timeout partial outputでもunsafe detectorを実行する。安全ならstructured deferredとして返す。Run305以降はraw `pipeline.py`を直接起動せず、`AIIF_PRODUCT_REVIEW_RUNTIME=true` 付き `production_pipeline.py` を唯一のroot authorityとして使う。
- Global Daily timeout 45分、Gemini budget/retry、Run268 Source architecture、Fact/Evidence/Decision gateは変更しない。
- 初期案の取得層date normalizationとsource normalization公開面拡張は既存契約を壊したためCI反証で撤回し、最終修正を境界層へ限定した。
- 実装merge前にfull pytest **1795 passed**、Repository-wide Falsification、Integration/Synthetic Production Smoke、Notion Access Policy、Run269 Live Acquisition SmokeをPASSした。
- 詳細は `docs/reference/RUN272_DAILY_FAILURE_TAIL_HARDENING.md` を正本とする。

### Run305 — Product Review Provider Runtime

- Run304でProduct Review childのpersistent counter authorityを `runtime-state` に統一し、Run38で非ゼロcounter継承を実環境確認した。
- Run38でraw childがRun209/Run303をinstallしていないことを反証し、Run305で唯一のroot Production entrypoint `production_pipeline.py` にProduct Review専用modeを追加した。
- `AIIF_PRODUCT_REVIEW_RUNTIME=true` のとき、Run203 → Run209 → transient recovery → Run303だけを適用し、runtime-state preflight後にproduct-only coreへ進む。
- Product Reviewモデル順、max reviews 2、request budget 3、persistent daily capsは変更しない。
- Run260/Run172/article/publication/Reader Value/eyecatch layerはProduct Review専用runtimeへ導入しない。
- Repository-wide direct core-pipeline bypass guard、Run203/Run231通常Production source ordering、Daily PAUSED、public note human-onlyを維持する。
- 詳細は `docs/reference/RUN305_PRODUCT_REVIEW_PROVIDER_RUNTIME.md` を正本とする。
