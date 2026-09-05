# AI Intelligence Factory — 現行Production仕様

最終更新: 2026-09-05  
現行Functional Baseline: **Run209 — Gemini timeout RPD fail-closed**  
Documentation Governance Baseline: **Run210 — Documentation Freshness Guard**  
Paid Member Sync Baseline: **Run211 — paid member sync ordering**  
Paid Member UX Baseline: **Run215 — final current-authority action dedup**  
Paid Member Commerce/Onboarding Baseline: **Run217 — zero-API monetization readiness / product fulfillment**  
Paid Member Navigation/UI Baseline: **Run218 — PC-first member UX reconciliation**  
Paid Member Human-Language UI Baseline: **Run219 — non-engineer member presentation language**  
Paid Member Database Destination Baseline: **Run220 — canonical member DB cutover / fail-closed destination**  
Paid Member Database Hosting Baseline: **Run221 — API-host isolation / member-view separation**  
Article Technical Claim Precision Baseline: **Run223 — operation/API scope, performance modality, first-party date and typo precision**  
Article Deterministic Rescue Baseline: **Run224 — zero-model performance multiplier scope rescue**  
Stock Lifecycle Baseline: **Run225 — zero-model Fresh/Aging/Evergreen/Archive active-stock management**  
Free Article Editorial Planning Baseline: **Run226 — evidence-bounded human editorial planning / reader delight without template quotas**  
Article Japanese Surface Integrity Baseline: **Run227 — zero-model high-confidence broken-Japanese fail-closed gate**  
Free Article Reader Rhythm Baseline: **Run228 — evidence-preserving reader rhythm / dense-report prevention without style quotas**  
Pipeline Modularization Baseline: **Run239 — source-normalization + evidence-context + paid-product maintenance + Deep Dive portfolio + reader-experience diagnostics extraction / zero-quality-change strangler modularization**
Repository Organization Baseline: **Run201 — repository garbage cleanup without intended runtime behavior change**  
Production Source of Truth: **`main`**

## 0. この仕様書の位置づけ

このファイルは「現在のProductionで何を守るか」を明示する現行契約である。

参照優先順位:

1. `main` の実行コード、テスト、GitHub Actions workflow
2. 本ファイルの現行Production契約
3. `README.md` の運用・リポジトリ構造
4. `GEMINI_QUOTA_SETUP.md` 等の領域別Operator仕様
5. `docs/reference/` の現行領域別仕様
6. `docs/archive/` の過去Run仕様・検証記録

旧仕様は監査用であり、現在挙動をarchive文書から推測してはならない。

## 1. 事業・商品契約

AI Intelligence Factoryの事業構造:

**無料note記事 → 会員募集LP → noteメンバーシップ → 会員限定Notion Decision Intelligence + Digest**

- 無料note記事はAcquisitionチャネル。
- 有料価値は高密度な意思決定DBと会員向けDigest。
- 記事単体を有料note商品へ戻すことを前提にしない。
- subscriber PIIをGitHubの集計・attribution artifactへ持ち込まない。
- Public releaseは人間の最終操作とし、note自動化はprivate draftまで。
- Paid memberの正規入口は`AI Decision Intelligence｜会員ホーム`（Page ID `3c5479ff-dca9-8103-bff0-f2d5f408d35f`）。
- 現行Member Presentation DBはRun220のDatabase ID `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`、Data Source ID `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`のみを正規商品とする。
- 現行DBの物理APIホストはRun221のPage ID `3c5479ff-dca9-8178-867c-d9249a3ff5c8`。これは実装上のアクセス境界であり、会員入口ではない。
- 会員ホームは正規Data Sourceを会員向けview/linkとして見せる。物理DB配置と会員ナビゲーションを同一視しない。
- Run220前のDB `d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1` / `d1461b6f-0940-4bf9-803a-6686a37c4ba2` は`⚠️ 旧版・使用禁止｜AI・技術一覧（Run219前）`として監査用に隔離する。
- 旧100件Data Source `ec2ac2b3-89b6-4242-89b9-e94060826fca`も`旧版・使用禁止`であり会員入口に使わない。
- PCを会員利用の主画面とし、mobile/simple viewは補助導線として扱う。
- LPでDigestを提供物として掲げる限り、**Digest自動生成が停止中でも**各月の提供サイクルを無提供にしてはならない。必要に応じ現在DBだけを使うhuman/zero-model Digestで履行する。

## 2. 運用契約

- **Daily workflowはPAUSED。**
- Production実行は明示的なONE-SHOT / workflow_dispatchを基本とする。
- ChatOps ONE-SHOT BridgeはIssue #71の許可済みコマンドからのみ安全にdispatchする。
- API・外部サービス障害時はFail-Closedまたは局所的Fail-Safeとし、成功していない処理を成功扱いしない。
- Gemini、Notion、note、GCP等の外部状態を推測で補完しない。
- Productionの品質条件を「処理を通すため」に緩和しない。
- Public note releaseは引き続きhuman-only。

## 3. Core Intelligence Pipeline

現行`pipeline.py` / `production_pipeline.py`の主要契約:

Run231詳細: `docs/reference/RUN231_PIPELINE_MODULARIZATION.md`

- Run235でsource normalizationの重複実装を`source_normalization.py`へ集約し、`pipeline.py`は単一正本を参照する。
- Run236でEvidence本文のtruncate/excerpt/mergeロジックをprovider・DB非依存の`evidence_context.py`へ抽出する。`pipeline.py`には現行の動的文字数上限を束縛する薄いwrapperだけを残す。
- Run237でEvidence Health、Subscriber Technology DB sync、月次Digest期間選択/生成の運用保守ロジックを`product_delivery_maintenance.py`へ抽出する。`pipeline.py`はlive runtime依存を渡す薄いwrapperだけを残し、Evidence Healthのzero-model契約と直近3完了月のDigest再確認順序を維持する。
- Run238でStock済みDeep Dive候補のprofit/portfolio並べ替え、topic diversity、EVERGREEN補助、publication reliability slotのzero-model決定論ロジックを`deep_dive_portfolio.py`へ抽出する。`pipeline.py`はlive閾値・normalizer・logger等を渡す薄いwrapperだけを残す。Eligibility、Decision/Evidence/Fact条件、既存toleranceは変更しない。
- Run239で390行の`_reader_experience_signals()` zero-API診断実装を`reader_experience_signals.py`へ機械的に抽出する。`pipeline.py`にはliveな`_article_opening_excerpt`を束縛する薄いwrapperだけを残す。既存の正規表現、閾値、status、Reader Delight / information budget判定は変更せず、`soft_only=True`を維持する。
- Run235/236/237/238/239はいずれもGemini model、RPD/RPM/TPM、Fact/Evidence/Decision閾値、Daily PAUSED、Public release human-onlyを変更しない。
- Run237詳細: `docs/reference/RUN237_PRODUCT_DELIVERY_MAINTENANCE_MODULARIZATION.md`
- Run238詳細: `docs/reference/RUN238_DEEP_DIVE_PORTFOLIO_MODULARIZATION.md`
- Run239詳細: `docs/reference/RUN239_READER_EXPERIENCE_DIAGNOSTICS_MODULARIZATION.md`

- 必須観測Source: GitHub / Hacker News / arXiv / Product Hunt
- Screening全体上限: 200候補
- Screening batch: 25件
- Raw Decision Score 55以上をGlobal Calibration対象とする
- Final Decision Score 60以上をStock保存対象とする
- Deep Diveは上位最大3件を基本とし、失敗時は次点Backfillを許容する
- Decision品質とCommercial Valueを混同しない
- Profit/Portfolio最適化は品質閾値・Evidence・Fact条件を迂回しない
- Observed履歴、Source ROI、deferred state等のProduction continuity dataを保持する

### 3.1 Pending Retry fast lane — Run206 / Run207

`pending_retry_validation.py`はScreening済みの高価値Pending Retryだけを再処理する低コストRecovery entrypointである。

- fresh collection / screeningを行わない。
- Screening Score降順で処理する。
- 1記事成功で即停止する。
- 専用Gemini request budgetは**最大3 requests**。
- fast laneでは**1回目のHTTP 503**で当該modelをそのrun中cooldownする。
- Persistent counter、global budget、Evidence/Fact/Reader/Publication gateは迂回しない。
- Public note releaseは行わない。

### 3.2 Reader Value repair — Run208

`run208_reader_value_repair.py`はPending Retry fast laneに限り**Reader Value repair**を1回だけ許可する。

- repairable Reader-only failureに限定する。
- Fact/Evidence blocker、過剰主張、非Reader Hard/Review理由が混ざる場合は発火しない。
- Evidenceを削ってReady化することは禁止。

### 3.3 Screening Stock lifecycle — Run225

Screening Stockは履歴資産として保持するが、無期限の現役候補キューにはしない。`run225_stock_lifecycle.py`はGeminiを使わず、一次情報の鮮度と限定的なdurable-source例外だけでActive Stockを管理する。

- **Fresh**: 0〜30日。
- **Aging**: 31〜90日。日付不明/不正もFreshへ推測せずAgingとして扱う。
- **Evergreen**: 91日超でもGitHub/arXivのdurable assetで、明示的な一過性event/news signalがないもの。
- **Archive**: 91日超でEvergreen条件を満たさないもの。
- ArchiveはNotionから削除・trashしない。履歴として保持し、active review queueと会員ホームTop3候補からだけ外す。
- Raw Screening Stockの鮮度は`公開日`を優先し、`分析日`はfallbackに限る。再取込だけでFreshへ戻さない。
- current/human reviewが明示されるmember-product側では、そのreview時刻を最優先anchorとしてFreshへ再昇格できる。
- Content Intelligence DBの`更新状態`は書込量削減のためblankをFreshのcanonical encodingとし、Aging / Evergreen / Archiveだけを必要時にmaterializeする。
- `stock_lifecycle_reconcile.py`は`評価状態=Stocked`だけを対象に`更新状態`以外を変更しない。Score / Decision / Evidence / Article state / URL / source textは不変。
- `run225_portfolio_lifecycle.py`はRun131の後にinstallし、Archiveを除外した後のranking/diversityは既存Run131へ完全委譲する。
- `run225_member_lifecycle_ui.py`はRun170〜Run215のcurrent-copy authorityを置換せず、最終homepage ranking境界だけでFresh/Evergreen→Agingの順に優先しArchiveへrankを与えない。
- `.github/workflows/stock-lifecycle-reconcile.yml`はmanual ONE-SHOTのみ。`plan`はread-only、`apply`は`RECONCILE_STOCK`確認必須。Daily PAUSEDとPublic release human-onlyを変更しない。
- Gemini/model callは0、record deletionは0。

詳細: `docs/reference/RUN225_STOCK_LIFECYCLE.md`

## 4. 品質・Evidence契約

維持すべき不変条件:

- Fact / Evidence / Decisionの整合性
- Primary Sourceを優先するEvidence authority
- Publication readinessのFail-Closed
- Human Appeal / reader-first編集品質
- 非エンジニアでも核心が理解できる平易さ
- Evidenceを削って「読みやすさ」を作らない
- 比喩・会話調は理解補助でありEvidenceではない
- Reader Experience診断を理由に重大Fact/Evidence gateを緩めない

### 4.1 Technical Claim Precision — Run223

`run223_technical_claim_precision.py`は、初回note実機全文監査で露呈した技術Claimの狭い精度欠陥をzero-modelで防ぐ。

- 同名パラメータでもメソッドごとに値・意味が異なる場合、1つの設定値へ丸めない。
- 一部/特定/lossyなBreaking Changeを「全面禁止」「すべて廃止」へ一般化しない。
- x倍・%改善・レイテンシ等が期待値/ベンチマーク/測定例なら、主体・モダリティ・条件を保持し、workload/環境依存の留保を落とさない。
- 一次情報の`公開・更新`日はfirst-party本文/明示metadataだけを使い、収集日・分析日・発見元投稿日を代用しない。確認不能なら推測せず省略する。
- `によるな処理`等の既知の明白な日本語助詞崩れをPublication前に局所blockする。
- Evidence閾値、Decision Score、Gemini request budgetは変更しない。
- Run223はPublication Contract fingerprint対象であり、policy変更後の旧Ready原稿は現行policyで再構築・再stampされるまでfail-closedとする。

詳細: `docs/reference/RUN223_TECHNICAL_CLAIM_PRECISION.md`

### 4.2 Performance Multiplier Deterministic Rescue — Run224

`run224_multiplier_deterministic_rescue.py`は、Run223が`performance_multiplier_scope_lost`を検出した場合だけ発火するzero-model局所救済層である。

- Run223が一次情報内の同じ倍率とbenchmark/expectation scopeを確認済みの場合に限る。
- 対象の性能倍率・その他数値・Evidence・Decision・Score・URLは変更または削除しない。
- 対象文の直後に、一次情報で示された特定条件下の目安であることと、実際の改善幅が処理内容・条件・実行環境によって変わる留保だけを追加する。
- fenced codeとMarkdown headingは編集しない。
- 同じqualifierを二重追記しない。
- 既存subtractive rescueの変更を保持し、`_rescue_loss`を悪化させない。
- Rescue後もFact / Editorial / Publication / Human Appeal Gateを通常どおり再評価し、残るHARD/REVIEWを迂回しない。
- Gemini/model callは0。Public note releaseも行わない。
- Run224はPublication Contract fingerprint対象であり、policy変更後の旧Ready原稿は現行policyで再構築・再stampされるまでfail-closedとする。

詳細: `docs/reference/RUN224_MULTIPLIER_DETERMINISTIC_RESCUE.md`

### 4.3 Human Editorial Planning — Run226

`run226_reader_delight_planning.py`は無料note記事の既存生成requestに、Evidence境界内の**生成前編集計画**だけを追加する。人間らしさを後付けの口語表現で作るのではなく、同じ既存model callの中で、記事を書く前に以下の5つの編集レンズを内部設計する。

- **Reader Tension**: 非エンジニア読者が何を疑問・困りごととして受け取るか。
- **Discovery**: 単なる発表要約ではない「そういうことだったのか」という記事固有の核心。
- **Concrete Consequence**: Evidenceで直接支えられる範囲の仕事・選択・使い方・導入判断への意味。
- **Explanation Bridge**: 専門知識がなくても技術的な芯へ到達できる説明順。比喩・問い・scene・会話調は任意であり必須ではない。
- **Editorial Point of View**: Evidenceと既存Decisionから導く編集者の視点を記事全体へ自然に通す。

Production契約:

- 5レンズは内部planningであり、本文の5見出しや固定順序として出力しない。
- Evidenceにない数値baseline、時間、金額、日付、人物、会話、引用、利用場面、普及/トレンド、競合roadmap、因果、多数派認識を「分かりやすさ」のために創作しない。
- sourceの倍率・%改善を具体的な時間/金額/件数へ換算するのは、baselineと換算後の値の双方がSOURCE BOUNDARYで直接確認できる場合だけ。
- Hook分類、比喩、問い、短文段落、箇条書き、会話マーカー等に回数ノルマ・均等配分を設定しない。style countだけを新しいHard Gateにしない。
- 入口・見出し順・段落順・Decision Voice位置は記事固有のEvidence/Discoveryから決め、固定テンプレートにしない。
- 既存Run126〜Run144 Reader Experience / Human Appeal診断を維持し、Fact / Evidence / Decision / Run223 / Run224 / Publication Contractを緩めない。
- 既存`build_decision_prompt`の出力schemaとbase promptを保持し、その末尾へ契約をidempotentに追加する。
- 新規Gemini/model call siteは0。既存記事生成requestだけを使う。
- Run226はPublication Contract fingerprint対象であり、旧policyのReady稿を新policy Readyとして流用しない。
- Daily PAUSED、Public note release human-onlyを変更しない。

詳細: `docs/reference/RUN226_READER_DELIGHT_PLANNING.md`

### 4.4 Japanese Surface Integrity — Run227

Run226導入後の初回FULL ONE-SHOT実記事監査で、Fact/Evidence/Reader Gateを通過したReady稿に`結果はでした。`、`計算はに速くなる`、`FP4を過度に適応すると`という明白な日本語崩れが残った。`run227_japanese_surface_integrity.py`は、この種の**高信頼で機械判定できる表層破損だけ**をzero-modelでPublication前にFail-Closedする。

- 述語欠落型の`結果はでした。`、比較・変化語彙直前の`はに`助詞衝突、技術対象を不自然に`〜を適応する`とする狭い他動詞誤用を検出する。
- `モデルが環境に適応する`、`方式を環境に適応させる`、`FP4を適用する`等の妥当な近接表現はblockしない。
- code fence / inline codeは検査対象外とし、コード文字列によるfalse positiveを避ける。
- deterministic自動書換えはしない。欠けた述語・副詞・意図語を推測すると意味を変えるため、通常のbounded retryへ局所修正指示だけを渡す。
- retryでも新しいFact・数値・人物・因果を補ってはならない。
- Fact / Evidence / Decision / score / source URL / Gemini request budgetを変更しない。
- Run227はPublication Contract fingerprint対象であり、旧policyのReady稿は現行policyで再生成・再検証・再stampされるまでnote Ready queueで投稿可能扱いにしない。
- Daily PAUSED、Public note release human-onlyを変更しない。

詳細: `docs/reference/RUN227_JAPANESE_SURFACE_INTEGRITY.md`

### 4.5 Reader Rhythm Planning — Run228

Run226初回FULL ONE-SHOTでは記事固有の切り口・Curiosity Pullは改善した一方、複数稿が`reader_value_review:dense_report_cluster`を残した。問題はEvidence不足ではなく、**Factが「理解→意味→判断」へ変換される前に次のFactが積み上がる報告書密度**である。`run228_reader_rhythm_planning.py`は既存生成requestの内部planningだけを追加し、この密度を下げる。

- 技術Fact・ベンチマーク・実装詳細を連続列挙するだけで終わらず、必要な説明から読者の理解・意味・Decision consequenceへ前進してから次の詳細へ移る。
- 記事には主要な説明軸を通し、核心理解・重要制約・Decisionのどれにも影響しない副次的実装列挙は無理に詰め込まない。
- Evidence上重要な数値・条件・反証・制約は削除しない。読みやすさはEvidence削減ではなく、重複・汎用前置き・Decisionに不要な周辺列挙の整理で作る。
- 専門語はその場で普通の言葉へ橋渡しし、辞書型の定義列挙を増やさない。
- table/listが正確で短く理解できる場合は使ってよく、読み物化のためだけに散文へ崩さない。
- scene、比喩、問い、短文、会話調、感情語を温度調整の装飾として義務化しない。
- 文長・段落文数・問い・比喩・箇条書き・見出し数に回数ノルマを設けず、固定構成へ揃えない。
- セキュリティや障害等、軽さが不適切なテーマでは明快さ・発見・判断可能性をReader Delightとして扱う。
- 新しいFact、数字、人物、会話、利用実績、因果、競合情報をReader Rhythmのために創作しない。
- 新規Gemini/model call siteは0。Fact / Evidence / Decision / Reader Value / Publication Gateは変更・迂回しない。
- Run228はPublication Contract fingerprint対象であり、旧policy Ready稿を現行policy Readyとして流用しない。
- Daily PAUSED、Public note release human-onlyを変更しない。

詳細: `docs/reference/RUN228_READER_RHYTHM_PLANNING.md`

## 5. Production runtime layer

`production_pipeline.py`は現行Production entrypointであり、以下を明示順でinstallする。

- `run203_runtime_state_channel.py`
- `gemini_timeout_rpd_fail_closed.py`
- `gemini_transient_recovery.py`
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
- `run194_publication_contract.py`

Run番号が古く見えても現役Production codeである。整理目的だけで削除・rename・統合してはならない。

### 5.1 Runtime state — Run203

`run203_runtime_state_channel.py`はGemini Persistent Counter等をProduction continuity stateとして扱う。

- reservation前にwritability/state preflightを行う。
- `.runtime/`は生成ゴミではなく保護対象。

### 5.2 Gemini timeout RPD — Run209

`gemini_timeout_rpd_fail_closed.py`はtransport/watchdog timeoutでもprovider側RPDが消費され得る実測に合わせ、**pre-send reservationを巻き戻さない**。

- 3.5 / 3.6 / 3.7 FlashのFactory daily safety ceilingは18。
- Provider上限20まで使い切る方向へ変更しない。
- timeoutでProduction RPD残量を増やさない。
- Google AI Studio Rate Limitsを最終的な外部実態として優先する。

詳細は`GEMINI_QUOTA_SETUP.md`を参照する。

### 5.3 Paid member product sync — Run211

会員向けNotion商品は次の順序で派生更新する。

**Source/Product Review更新 → Subscriber Decision Brief Sync → Member Presentation Sync**

- Daily / ONE-SHOT完了後はまずSubscriber Decision Brief Sync。
- Member Presentation Syncはその成功後に実行し、Source workflowと並列に走らせない。
- Subscriber Inventory Bootstrapは**apply**のみ同期チェーンへ接続する。
- **Inventory plan**は0-API/read-only契約を維持する。
- 両member writerは`member-derived-notion-writes`で直列化する。
- 派生同期はGemini APIを使用しない。
- `主なリスク` / `向いている用途` / `向いていない用途`等はSource値を同期し生成し直さない。
- `関連記事`は確定URLがある場合だけ伝播する。

### 5.4 Paid member presentation copy authority — Run212

`run212_member_review_copy.py`はarchive Product Reviewを現在判断として復活させず、読者向けcopyだけを限定利用する。

- archiveで利用できるのは`plain_summary`と`topic_trigger`のみ。
- historical score/status/reason/risk/best-for/avoid-for/Evidence/URLは現在stateを上書きしない。
- stale/time-sensitive archive copyは捨てる。
- zero-Geminiを維持する。

### 5.5 Paid member topic specificity — Run213

`run213_member_topic_specificity.py`はRun212後にも残るdeterministic generic topicだけを現在情報で補う。

- post-Run212 `今回の話題` がgenericな場合だけ**現在の `判断理由`**を利用できる。
- 非generic topicは上書きしない。
- role separationを維持する。
- `Safety 根拠` / `Transfer 根拠`等の既知artifactだけ狭く修正する。
- 新しいFact/判断を生成しない。

### 5.6 Paid member action specificity — Run214

`run214_member_action_specificity.py`は既知deterministic action templateだけを現在文脈で具体化する。

- 元action本文、件数、人数、期間、比較指標を保持する。
- current `向いている用途`を最優先し、なければcurrent non-generic `今回の話題`を使う。
- explicit/source-specific actionは上書きしない。
- Decision/Evidence stateを変更しない。

### 5.7 Paid member final action dedup — Run215

`run215_member_action_final_dedup.py`は残存action重複だけを解消する。

- specific current `向いている用途`を引き続き最優先する。
- 既知generic best-for fallbackだけをcurrent non-generic topicへ退避できる。
- current topicがgeneric/空欄なら重複解消だけを目的に文章を捏造しない。
- explicit actionや既存検証条件を変更しない。
- Decision/Evidence stateを変更しない。

### 5.8 Paid member commerce / onboarding — Run217

Run217は商品履行・Digest・legacy隔離の履歴Baselineである。NavigationはRun218、DB destinationはRun220がcurrent authority。

- Run217当時の206件DB `d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1` / `d1461b6f-0940-4bf9-803a-6686a37c4ba2` は現在`⚠️ 旧版・使用禁止｜AI・技術一覧（Run219前）`。
- 旧100件Data Source `ec2ac2b3-89b6-4242-89b9-e94060826fca`も使用禁止。
- Run217ホーム`3d0479ff-dca9-819e-9da0-c951225de6b3`は`【旧・統合済み】`で新規会員入口に使わない。
- `会員限定Digest｜2026年9月 初回版`はzero-modelで作成された。
- `今月の重要変化`とPriorityは意味を分離し、表示目的でフラグを偽装しない。

### 5.9 Paid member navigation / UI — Run218

Run218はPC中心のCurrent Navigation/UI Baselineである。

- 正規会員入口: `AI Decision Intelligence｜会員ホーム`
- Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- **PC-first**、mobile/simple viewは補助。
- Top3は`注目順位 <= 3`へ追随する**live Top3**。
- Shortlistを100件超の広域リストへ戻さない。
- 主要viewは会員向け列を優先しinternal sync identifierを通常表示しない。
- `今月の重要変化` source semanticsは維持する。
- authoritative historyに`評価の変化 >= 20`または`<= -20`が存在する場合はpresentation-only fallbackとして表示できる。
- 説明のない空表をprimary surfaceに置かない。
- 会員ホームは正規Data Sourceへの会員向けview/linkを提供する。物理DBをホーム直下へ置くことはUX契約ではなく、物理配置はRun221に従う。

### 5.10 Paid member human-language UI — Run219

`run219_member_human_language_ui.py`は非エンジニアが抵抗なく読める会員本文を生成するPresentation層である。

会員本文の主要ラベル:

- `このAI・技術をどう見る？`
- `いま、どうする？`
- `そう判断した理由`
- `気をつけたいこと`
- `こんな使い方に向いています`
- `こんな使い方には向きません`
- `確認に使った公式・一次情報`

- body summaryではADOPT / TEST / WATCH / AVOIDコードを前面表示せず日本語の行動意味を示す。
- DBの判断値・score・Evidence・Factを変更しない。
- cached/no-op pageは不要なNotion通信を行わない。
- Gemini/provider pathを持たない。

### 5.11 Canonical member DB cutover — Run220

Run219本番検証で、workflowの同期先と会員ホームの参照DBが別になっているsplit-brainを発見した。Run220以降、会員商品DBは1つに固定する。

Current canonical destination:

- Database ID: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Data Source ID: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
- Physical API host Page ID: `3c5479ff-dca9-8178-867c-d9249a3ff5c8`（Run221 authority）

Pre-cutover audit-only destination:

- Database ID: `d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1`
- Data Source ID: `d1461b6f-0940-4bf9-803a-6686a37c4ba2`
- Title: `⚠️ 旧版・使用禁止｜AI・技術一覧（Run219前）`

Production contract:

1. `provision_member_presentation_db.py`は上記canonical Data Sourceを直接verifyする。
2. parent Database IDがcanonical Database IDと一致することをverifyする。
3. titleが`AI・技術一覧｜判断DB`と一致することをverifyする。
4. 不一致・読取不能なら**Fail-Closed**する。
5. 通常Productionで別の同名DBへfallbackしない。
6. 通常Productionで新しいPresentation DBを自動作成しない。
7. `.github/workflows/member-presentation-sync.yml`は`MEMBER_PRESENTATION_ALLOW_CREATE: 'false'`を固定する。
8. workflowと会員ホームの参照Data Sourceを同じcanonical IDsに固定する。
9. Run219 human-language UIを維持する。
10. Gemini/model APIを使用しない。

詳細: `docs/reference/RUN220_MEMBER_DB_CANONICAL_CUTOVER.md`。

### 5.12 Member DB API host isolation — Run221

Run220をmainへ反映後、正規DBを会員ホーム直下へ物理移動した状態ではGitHub ActionsのNotion Integrationからcanonical Data SourceがHTTP 404となった。Run220 Fail-Closedにより別DBは作成されなかった。同じDBを元のAPI-accessible hostへ戻した後、同じmain SHAの再実行が成功したため、物理親の変更によるIntegrationアクセス継承が原因と確定した。

Current hosting contract:

- Customer member home: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- Canonical Database: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Canonical Data Source: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
- Physical API host: `3c5479ff-dca9-8178-867c-d9249a3ff5c8`

Production invariant:

1. 会員入口と物理APIホストを別概念として扱う。
2. `provision_member_presentation_db.py`はcanonical DS/DBに加えてphysical API hostもverifyする。
3. `.github/workflows/member-presentation-sync.yml`は`MEMBER_PRESENTATION_API_HOST_PAGE_ID: '3c5479ff-dca9-8178-867c-d9249a3ff5c8'`を固定する。
4. physical host mismatch / unreadableはmember write前にFail-Closedする。
5. 現行Integrationへ会員ホーム親のアクセスが明示付与・検証されるまでは、breadcrumb改善だけを目的にDBを会員ホーム直下へ物理移動しない。
6. 会員ホームは正規Data Sourceの会員向けview/linkを表示し、内部物理ホストを会員向け案内に使わない。
7. bootstrap parentもAPI hostを既定値とする。
8. Run220のno-fallback / no-auto-createを維持する。

Run220 post-merge再検証:

- main SHA `a3eecf70f64ddea46525b2e0225e1d94ea822b09`
- Member Presentation Sync Run `33771347577`
- Attempt 1: canonical resolve HTTP 404、fallback/create 0
- API hostへ戻したAttempt 2: SUCCESS
- `created: False`
- source records 206 / presentation unchanged 206
- body total 206 / unchanged 206
- `zero_gemini_calls=true`

詳細: `docs/reference/RUN221_MEMBER_DB_HOST_ISOLATION.md`。

## 6. Publication Contract / note Ready契約

note投稿対象はContent Intelligence側のReadyだけでは不十分。

少なくとも:

- note Ready queueで投稿可能
- current publication policy fingerprintに一致
- manuscript caption SHAと本文bytesが一致
- Notion `rich_text` 分割はtransport上の都合に限定し、全segmentを連結したbytesが生成時manuscriptと完全一致する
- captionの`manuscript_sha256`は分割前だけでなく、読み戻した永続化本文でも一致しなければならない
- 必須eyecatch assetが存在
- historical paid-area control marker等を含まない

古い契約、hash不一致、asset不足を無理に復活させない。Notion保存時に改行等が1文字でも欠落したReady本文も投稿対象にせずFail-Closedする。

### 6.1 note footer / presentation integrity — Run222

初回の実note private-draft E2Eで、CTAがSources / Evidenceより前に置かれること、note title fieldと本文H1が重複すること、単一`#`が本文に生表示されることを確認した。Run222以降の公開表示契約は以下。

1. 記事本文・結論の後に`Sources / Evidence`、権利/出典注記、免責を置く。
2. `AI Decision Intelligence` CTAはそれら信頼情報の**後**、記事の最終Actionとして置く。
3. note editorではstored Ready manuscriptをPublication Contractでbyte-exact検証した**後だけ**presentation transformを適用する。
4. note title fieldと同一の先頭H1は本文から除去する。
5. 残存する本文H1はcode fence外だけH2へ縮退し、raw Markdown `#`を表示しない。
6. pre-Run222 policyでstampされた原稿は直接受理しない。現行policyでdeterministic rebuild/restampし、byte-exact readbackを通過してからnote editorへ送る。
7. Evidence / Decision / score / source URL / article factは変更しない。
8. Gemini/model call 0、public release action 0を維持する。

詳細: `docs/reference/RUN222_NOTE_PRESENTATION_INTEGRITY.md`。

## 7. note private-draft automation

現行note stack:

- `note_draft_automation.py`
- `run185_note_ready_legacy_skip.py`
- `run186_note_header_image_resilience.py`
- `run187_note_editor_readiness.py`
- `run188_note_header_upload_fallback.py`
- `run189_note_editor_route_gate.py`
- `run190_note_persistent_cloud.py`
- `run191_note_crop_dialog_resilience.py`
- `run193_note_official_header_upload.py`
- `run194_note_current_contract.py`
- `run194_note_persistent_cloud.py`
- `run199_note_vm_preflight.py`
- `run222_note_presentation_integrity.py`

`.github/workflows/note-create-draft.yml`はzero-browser / zero-Gemini preflight後、eligible candidateがある場合だけGCP Chrome VMを起動する。private draftのみ作成し、公開は人間が行う。

## 8. GCP / browser cost contract

- publish-safe candidateが0件ならGCP note Chrome VMを起動しない。
- 実draft時のみpersistent Chrome VMをon-demand使用する。
- workflow後にVM停止確認を行う。

## 9. 保護対象データ

通常cleanupで削除・移動しない:

- `.runtime/`
- `observed_history/`
- `source_roi_history/`
- `deferred_deep_dive/`
- `eyecatch_images/`
- `assets/`

## 10. テスト・変更管理

- Run番号付きtestは古い名前だけを理由に削除しない。
- Production code semantic refactorはcleanupと分離する。
- main反映前にRepository-wide Falsification Guard、zero-API regression、Synthetic smoke、関連CIを通す。

### 10.1 Documentation Freshness Guard — Run210

Canonical documentationを「後で更新する」運用は禁止する。Production変更と仕様更新を同一変更セットで扱う。

CIは少なくとも次を検証する。

- `production_pipeline.py` active runtime layerが本仕様書に記載されること。
- Functional / Documentation / member-product baselineがREADMEと整合すること。
- Gemini Flash safety ceiling 18、Daily PAUSED、AI Studio external truthが矛盾しないこと。
- Pending Retry最大3 requests / 1回Reader repair契約が欠落しないこと。
- Run211 member sync順序とInventory plan read-only境界を維持すること。
- Run212 archive copy-only authorityを維持すること。
- Run213 current `判断理由` topic fallback境界を維持すること。
- Run214 current-context action specificity境界を維持すること。
- Run215 specific best-for優先とgeneric fallback境界を維持すること。
- Run217 legacy quarantine / Digest履行を維持すること。
- Run218 PC-first / mobile-secondary、live Top3、重要変化source/presentation分離を維持すること。
- Run219 non-engineer human-language bodyを維持し、body summaryへstatus codeを再露出させないこと。
- Run220ではREADME / Canonical / Operator / workflowがcurrent DB `b2787ee0-5b58-4ca7-b4eb-774f60237f1f` / `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`を指すこと。
- Run220前DB `d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1` / `d1461b6f-0940-4bf9-803a-6686a37c4ba2`を`旧版・使用禁止`として扱うこと。
- Run221ではREADME / Canonical / Operator / workflowがphysical API host `3c5479ff-dca9-8178-867c-d9249a3ff5c8`を指し、会員ホームと物理ホストを同一視しないこと。
- Member Presentation normal Productionが別DBを自動作成・fallback選択しないこと。
- Member Presentation normal Productionがphysical host mismatchを受理しないこと。
- 会員向け主要画面を説明のない空表へ退行させないこと。
- Run222ではSources/Evidence + 免責をCTAより前に維持し、note title重複H1/raw `#`生表示を再発させない。
- Run224ではRun223が確認した性能倍率scope lossだけをzero-modelで局所補完し、倍率・Evidence・Decision・Score・URLを変更せず、通常Gate再評価を迂回しない。
- Run225ではScreening Stockを削除せずFresh/Aging/Evergreen/Archiveでzero-model管理し、Archiveだけをactive review / member homepageから外す。Score・Decision・Evidence・Run131・Run170〜Run215 authorityを変更しない。
- Run226では無料記事のReader DelightをSOURCE BOUNDARY内のReader Tension / Discovery / Concrete Consequence / Explanation Bridge / Editorial Point of Viewとして生成前に設計し、固定Hook・比喩・問い・段落・箇条書き等の回数ノルマをHard Gate化しない。Evidence / Decision / 既存Gate / Gemini call数を変更しない。
- Run227では実Productionで確認した高信頼の日本語表層破損をzero-modelでFail-Closedし、自動推測修正・Fact/Evidence/Decision変更・追加model callを行わない。旧Ready稿は現行policy fingerprintに一致するまでnote投稿対象にしない。
- Run228ではdense-report clusterをEvidence削減で隠さず、既存生成request内でFactを理解・意味・判断へ変換するReader Rhythmを設計する。style countや固定構成を新しいHard Gateにせず、Fact/Evidence/Decision/Reader Value/Publication Gate/Gemini call数を変更しない。

Production behavior changeでCanonical docsがstaleになる場合、コードだけをmainへ入れてはならない。

## 11. Repository organization

rootは現在のoperator/canonical documentsと実行entrypointを優先し、過去Run説明は`docs/archive/`へ置く。Production continuity stateと公開参照資産は保護する。
