# AI Intelligence Factory 現行仕様

最終更新: 2026-08-23  
本パッケージコード基準: **Run 115 Product Review Adversarial Hardening 完成版候補**  
基準ファイル: `pipeline.py` / `inventory_bootstrap.py` / `decision_intelligence.py` / `.github/workflows/`

> 本仕様書はRun 102までのProduction基盤を維持しつつ、Run 103〜115で追加されたReader-First、Eyecatch精度、Human Editorial Naturalness、Subscriber Inventory Bootstrap、Cross-Source Evidence Resolution、Product Review Reliability、Product Review Adversarial Hardeningを含む本パッケージ仕様を記録する。Run115は完成版候補であり、main反映・実Provider運用確認前にProduction適用済みとは扱わない。Pipeline本体の既定値とGitHub Actionsの環境変数指定が異なる場合は、GitHub Actionsの環境変数が優先される。

## 1. 目的と情報設計

AI・技術情報を毎日自動収集し、価値を段階的に選別して蓄積する。

| 層 | 対象 | 保存先 | 目的 |
|---|---|---|---|
| Observed | Screeningした全候補 | JSON履歴・GitHub | 観測、再浮上検知、トレンド分析 |
| Stocked | Final Score 60点以上 | 内部Notion DB | 検索・比較できる意思決定資産 |
| Deep Dive | Stocked上位から最大3件 | 既存Notionページを更新、note原稿等 | 一次情報に基づく詳細分析 |

Observedの全件をNotionへ保存しない。NotionにはFinal Score 60点以上のみを保存し、情報密度を維持する。

## 2. 日次処理フロー

1. Pending Retryは最長待機順で処理するが、専用Gemini実送信上限2回/Runを超えずFresh候補のDeep Dive枠を優先する
2. GitHub、Hacker News、arXiv、Product Huntを収集する
3. OSSライセンス安全性を確認する
4. Notion既存URL・ローカル重複を除外する
5. Source-balanced Round Robinで候補を構成する
6. 最大200件を25件ずつBatch Screeningし、Decision Scoreと独立したCommercial Value / Shelf-Lifeも同時推定する
7. Raw Decision Score 55点以上をGlobal Calibrationし、Decision / Commercial / Shelf-Lifeを横断補正する
8. 全Screening結果をObserved JSONへ保存し、GitHubへも保存する
9. Final Decision Score 60点以上をNotion Stockとして保存する（Commercial ValueだけではStockへ昇格させない）
10. 永続化済みStockをProfit Priority順に並べ、最大3件をDeep Diveし、失敗時は次点をBackfillする
11. 月末のみ月次ダイジェストを生成する
12. Telegramへ結果・異常を通知する

## 3. 収集仕様

| Source | 上限 | 取得内容の例 |
|---|---:|---|
| GitHub | 50件 | AI/MLリポジトリ、Stars、更新日時、ライセンス |
| Hacker News | 50件 | Top Story、HNスコア、外部リンク、投稿本文 |
| arXiv | 50件 | AI/ML新着論文、Abstract、著者、分類 |
| Product Hunt | 50件 | 製品、Tagline、Description、Votes |

- 合計Screening上限は200件。
- GitHub、Hacker News、arXiv、Product Huntの4 Sourceはすべて同格の必須Sourceとする。Source ROI、最低取得枠、最大取得枠、学習式、explorationではProduct Huntだけを優遇・抑制しない。
- Product Huntだけ`PRODUCTHUNT_DEVELOPER_TOKEN`が必要なため、欠落はproduction PreflightでGemini消費前に停止する。これはAPI認証上のtransport要件であり、事業ロジック上の特別扱いではない。各Source側の一時障害はFault Isolationで局所化し、他Sourceの処理は継続する。
- Product Huntは日次新着性を優先し、`PRODUCTHUNT_LOOKBACK_HOURS=72`を既定として`postedAfter`を明示し、`NEWEST`順で取得する。
- Round Robinにより、先に連結されたSourceだけで上限を使い切らない。
- ローカル重複はURL末尾スラッシュや主要tracking parameterの差を正規化して除外する。

## 4. ScreeningとCalibration

### Batch Screening

- `SCREENING_BATCH_SIZE=25`
- 200候補の場合、通常は8回のGemini Flash-Lite呼出し。
- Batch間は`SCREENING_BATCH_PACING_SECONDS=10`秒待機する。
- 入力はID、Source、名称、説明、Engagement、Published At、URLのみ。本文・README・論文PDFの取得は行わない。
- `score`（Decision Score）は従来どおり、技術的新規性、実務インパクト、意思決定への影響、緊急性、市場波及性、情報源の信頼性を評価する品質・意思決定価値スコア。
- `commercial_score`（Commercial Value Score）はDecision Scoreから完全分離し、読者需要の見込み、意思決定の緊急性、会員DB転換可能性、継続的な実務需要、商業隣接性を0〜100でmetadataのみから保守的に推定する。入力にないアクセス数・検索量・売上は捏造しない。
- `shelf_life_score`は情報価値の持続性を0〜100で推定し、`FLASH=0-34`（主に1〜7日）、`TREND=35-69`（主に1〜4週）、`EVERGREEN=70-100`（数か月以上）へ決定論的に分類する。
- `topic`はSource種別ではなく内容の主テーマを`MODEL / AGENT / DEVTOOLS / INFRA / DATA / SECURITY / MULTIMODAL / PRODUCT / OTHER`の9分類で推定する。補助メタデータであり、欠落・不正時は`OTHER`へFail-SafeしてDecision Scoreを失わない。
- Source間でEngagementの絶対値を直接比較しない。
- 出力はJSON配列（`id`、`score`、`commercial_score`、`shelf_life_score`、`topic`、`reason`）。ID欠落、重複、未知ID、score範囲外、JSON不正を検出する。Profit/Portfolio補助値が欠落・不正でも有効なDecision Score行は捨てず、Commercial/Shelfは中立値50、Topicは`OTHER`へFail-Safeする。
- 欠落候補だけを最大10件のRecovery Batchで再試行する。正常結果は再送しない。

### Global Calibration

- `ENABLE_GLOBAL_CALIBRATION=true`
- Raw Score 55点以上のみを対象に、最大50件ずつ横断比較する。
- Calibration後の`final_score`はNotion Stock閾値のDecision Scoreとして使用する。同時にCommercial Value / Shelf-Life / Topicも横断補正するが、品質スコアと混合しない。
- Calibration失敗時は、有効なRaw Decision Scoreと初回Profit/Portfolio metadataを保持して処理を継続する。

### 収益最適化（Profit Priority）

- `ENABLE_PROFIT_PRIORITY=true`を既定とする。品質Gate、Notion Stock閾値、Fact/Evidence判定は一切変更しない。
- Deep Dive候補の順序だけを `Priority = 0.65 × Final Decision Score + 0.35 × Commercial Value Score` で再順位付けする。重みは`DEEP_DIVE_DECISION_WEIGHT` / `DEEP_DIVE_COMMERCIAL_WEIGHT`で変更でき、負値は0として扱う。
- Commercial Value Scoreが100でもFinal Decision Scoreが60未満ならStockにもDeep Diveにも入れない。Notion Stock永続化に失敗した候補も従来どおり除外する。
- Shelf-Lifeは短命ニュースへの偏りを防ぐためのPortfolio制御にのみ使う。TOP3にEVERGREENが0件の場合、候補のProfit Priorityが現在の3位以内のcutoffから`EVERGREEN_PRIORITY_TOLERANCE=8`点以内なら、EVERGREENを最大1枠（`EVERGREEN_PORTFOLIO_MIN=1`）まで3位へ繰り上げる。大幅に弱いEVERGREENを品質・利益より優先しない。
- Content Portfolio Balanceを既定ON（`ENABLE_PORTFOLIO_BALANCE=true`）とする。TOP3が単一Topicへ偏り、別Topic候補が現在cutoffから`PORTFOLIO_TOPIC_PRIORITY_TOLERANCE=6`点以内なら、`PORTFOLIO_MIN_DISTINCT_TOPICS=2`を目安に最大1件以上を保守的に繰り上げる。大幅に弱い別Topicは繰り上げず、`OTHER`を含む場合は分類不足とみなし順位を動かさない。
- Topic多様化はEvergreenの唯一枠を破壊しない。Profit Priority / Evergreen / TopicはいずれもDeep Dive候補順にだけ作用し、Stock閾値・Evidence・Quality Gateを変更しない。
- この版ではNotion DBの新規Property追加を要求しない。Commercial / Shelf-Life / Topic / Profit PriorityはObserved履歴と実行時候補データへ保存し、既存Notion Schemaを壊さない。将来Revenue Feedback Loopを実装する際にNotion/分析DBへ昇格する余地を残す。

### Source ROI Learning

- `ENABLE_SOURCE_ROI_LEARNING=true`を既定とし、4 Sourceの過去Runにおける`screened`、実Notion `stock_saved`、`deep_dive_attempted`、`generation_requests`、`ready`等のaggregateだけを最大30 Run保持する。記事本文・個人情報はROI状態へ保存しない。
- ROIは既定で `Stock Yield 35% + Ready Yield 45% + Generation Efficiency 20%`。少数データ暴走を抑えるBayesian smoothingと、直近Runを重くする`SOURCE_ROI_RECENCY_DECAY=0.93`を適用する。
- `SOURCE_ROI_MIN_SCREENED=50`かつ`SOURCE_ROI_MIN_DEEP_DIVE_ATTEMPTS=2`を満たす成熟Sourceが2つ以上になるまで、冷開始として従来の50件/Sourceを維持する。状態欠落・破損時も同じ冷開始へFail-Safeする。
- 学習有効化後も4 Sourceすべてに`SOURCE_ROI_MIN_FETCH_PER_SOURCE=25`を保証する。残り枠だけをROIと小さなexploration bonusで動的配分する。ROIが低いSourceも停止・除外しない。
- **4 Sourceは完全に同格**とし、最大取得枠は共通の`SOURCE_ROI_MAX_FETCH_PER_SOURCE=75`を使用する。Product Huntだけ50に固定する等のSource固有capは持たない。4 Sourceが同じROIなら200件上限時は50/50/50/50へ対称配分される。
- APIごとの認証、pagination、レスポンス形式、Evidence抽出差はSource adapter層の技術要件として扱うが、Source ROIスコアやDeep Dive優先度へSource名による固定boost/penaltyを入れない。
- ROI状態は`source_roi_history/source_roi_state.json`へ保存し、Observed履歴には当該RunのROI profileとfetch allocationも監査用に保持する。

## 4.5 Free Article → Subscription Attribution

- Business modelは`無料note = Acquisition`、`会員向け意思決定DB + 月次サマリー = Paid Subscription Product`で固定する。有料note記事の販売ロジックは追加しない。
- `ENABLE_SUBSCRIPTION_ATTRIBUTION=true`を既定とし、Ready記事ごとにPrimary URL由来の安定`article_id`を生成する。Source名ではなくcanonical Primary URLをidentityとするため、utm差・HN/Product Hunt等のDiscovery Source差でAttributionが分裂しない。
- `SUBSCRIPTION_LANDING_URL`が有効なHTTP(S) URLの場合だけ、無料記事末尾に会員向け意思決定DB＋月次サマリーへのCTAを追加する。URLには`utm_source=note`、`utm_medium=free_article`、`utm_campaign`、`utm_content=article_id`、`aif_article_id=article_id`を決定論的に付与する。既存の非Attribution query parameterは維持する。
- Landing URL未設定・不正時は壊れたCTAを公開せず、記事生成自体は継続する。production preflightでは警告だけを出し、品質Pipelineを止めない。
- Attribution manifestは**Quality Gate PASS AND Notion Persistence SUCCESSでReady確定した後だけ**`subscription_attribution/articles/<article_id>.json`へ保存する。Telemetry保存失敗はReadyを取り消さない。
- Manifestは記事単位aggregate metadataだけを保持し、subscriberの氏名、メール、member/customer/payment ID等のPIIを保存しない。
- 外部実績は`subscription_metrics_template.csv`と`subscription_attribution.py`で集計する。`attribution_method`を`note_dashboard_only / tracked_cta / end_to_end / manual_verified`の4段階で必須化し、計測根拠を超えるsubscriber/revenue値を入力した場合はFail-Closedで拒否する。未知`article_id`やPII様columnも拒否する。
- 集計KPIは`CTA click rate`、`Subscriber conversion/click`、`Subscriber conversion/note view`、`Subscription revenue/1,000 note views`等。**現版では実績をCommercial Value / Source ROIへ自動Feed Backしない**。少数・不完全帰属による自己強化バイアスを避け、Revenue Feedback Loopは十分な実測蓄積後に別実装する。
- GitHub Actionsでは`SUBSCRIPTION_LANDING_URL`をRepository Variableから受け取る。`subscription_attribution/**`のみのruntime commitではSynthetic Regression CIを再起動しない。

## 5. Gemini API保護

- Screening Model Pool: Flash-Lite系モデル（既定: `gemini-3.5-flash-lite`、`gemini-3.1-flash-lite`）
- Deep Dive Model Pool: Flash系モデル（既定: `gemini-3.6-flash`、`gemini-3.7-flash`、`gemini-3.5-flash`）
- 429、404、503等ではモデルPool内でFallbackする。
- Persistent Daily Counterは**repository-local・モデル単位**で利用量を永続管理する。API key交換でCounterがリセットされないようrepository由来の安定scopeをSHA-256短縮して使い、生のRepository名/Project ID/API Keyは状態ファイルへ保存しない。旧API-key / Project scopeの同日counterは新scopeへ保守的に合算移行する。Google Project全体の最終使用量はAI Studio Rate Limits画面を正とする。ローカルBudget/Retry Budgetを先に検査し、実送信不能な要求でPersistent Counterを過剰予約しない。
- 実行内Gemini安全上限は50リクエスト。Deep Dive用に3リクエストを予約する。
- Screening Retry Budgetは4、Deep Dive Retry Budgetは1。無限Retryはしない。
- クォータ・通信障害はQuality FailedではなくPending Retry／未判定として扱う。
- `GEMINI_QUOTA_PROJECT_ID`は任意の監査メタデータとする。Workflowから取得できない場合は`github.repository`由来のrepository-local counter scopeへ自動フォールバックし、Dailyは継続する。安定scope自体を決定できない場合だけFail-Closedする。
- 1 Run内のGemini送信試行は`GeminiUsageAudit`でmodel / request kind /短いcandidate context / success-error / SDKが返すtoken usageに分解して記録する。Prompt本文・未公開記事本文は監査ログへ保存しない。`gate_history/gemini_usage_*.json`はPrivate Artifactへ保存し、Daily完了通知にもmodel別・用途別attempt数を出す。

### Deep Dive記事生成の現行設定

- 1実行あたりのDeep Dive request budgetは既定12回。`GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET`で変更できる。
- 1回のDeep Dive出力上限は既定9,000トークン。管理データと記事本文を同時に出力するため、旧設定6,000トークンで発生した`MAX_TOKENS`による途中切れを抑制する。
- Deep Dive候補の試行上限は既定7件。成功記事数の目標は最大3件であり、4位以降をBackfillに使用する。
- Quality Gate不合格、出力途中切れ、一次情報不足、Pending Retryなどが発生しても、候補試行上限とAPI予算の範囲内で次点候補へ進む。
- Evidence Sufficiencyが`INSUFFICIENT`の候補はGemini Deep Diveを呼ばず、API枠を消費せずに次点候補へ進む。
- Quality Retryは最大1回。ただし`PUB_SOURCE_SUFFICIENCY`、Primary Source未解決、Technical Claims不足、Freshness未解決、高リスクAction根拠不足など、再作文ではEvidenceが増えないReason CodeではRetryを実行しない。Repair可能なFact/構造/タイトル/Action表現だけを局所修正する。`MAX_TOKENS`時は必須構造を保った短縮完全版を再生成する。
- 12回への増枠は記事成功数を保証するものではない。根拠外表現、一次情報不足、Publication Readiness、Human Appealの不合格は引き続き公開しない。

### GitHub Actionsとの設定整合

`pipeline.py`の既定値と`.github/workflows/daily.yml`の`GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET`は、現在ともに12回で統一されている。GitHub Actionsの日次実行ではWorkflowの環境変数指定が適用される。Daily/Real Article Regressionは同一`ai-intelligence-gemini-budget` concurrency groupを共有し、Gemini枠を同時消費しない。Daily/Real Regressionのjob timeoutは45分とし、Deep Dive 12回×120秒 timeout＋pacingに加えてScreening/Calibration・Evidence取得・Notion永続化の余裕を持たせる。

## 6. Notion保存仕様

### Stocked

- 条件: Final Score 60点以上
- 主な値: `Status=Stocked`、`Content Status=Stocked`、`Article Status=Not Planned`、`Subscription Visibility=Subscriber Only`
- 保存項目: Name、URL、Source、Engagement Score、Decision Score、Screening Score、Screening Reason、Source Summary、Published At、Analyzed At、License等。
- `Screening Reason`はStep 1の評価履歴として永久保持する。Pending Retry、Needs Editorial Review、Quality Failed、Persistence Failureの理由で上書きしない。
- GitHub候補のLicenseはStock保存時に保持し、Pending Retry復元時にも`licenseInfo.spdxId`として復元する。推測による補完はしない。

### Deep Dive

- 最大成功件数は3件。低スコア候補で本数を水増ししない。
- Deep Dive候補はFinal Decision Score 60点以上に加えて、当該RunでNotion Stock永続化に成功し`notion_page_id`を持つ候補だけとする。Stock保存失敗候補へ追加のGemini Deep Dive枠を消費せず、次回収集でStockから再試行する。Eligible Stock間の順序だけProfit Priorityで最適化する。
- Stockの既存Notionページを更新する。重複ページを作らない。
- 成功時は`Status=Deep Dive`、`Content Status=Deep Dive`、`Article Status=Ready`となる。内部Notion DBの`Subscription Visibility`はnote無料公開モードと分離し、Readyでも`Subscriber Only`を維持する。
- `Needs Editorial Review`は、生成済みDeep Dive本文を既存Stockページの内部Notion childrenへ保存する。状態は`Status=Deep Dive`、`Content Status=Deep Dive`、`Article Status=Needs Editorial Review`、`Subscription Visibility=Subscriber Only`とし、`Review Status=Public Approved`には変更しないため公開DB・会員公開DB・noteへは送らない。人間レビュー後にReadyへ昇格できる内部資産として保持する。再Review時は新稿を先にappendし、状態commit成功後に旧Review manuscriptをbest-effortでarchiveして古いReview本文の残存を防ぐ。
- Needs Editorial Review原稿とReady原稿はmanuscript captionで識別する。Review原稿をReady原稿と誤認して再生成本文をスキップしない。Ready commit成功後は旧Review manuscript blockをbest-effortでarchiveし、ページ内の旧稿混在を抑制する。
- Readyは「4つのQuality Gateを通過」かつ「Notion永続化に成功」の両方を満たす場合だけに確定する。Notion保存失敗は記事品質失敗ではなく`NOTION_PERSISTENCE_FAILED`として記録し、Ready件数へ加算しない。
- Notion Upgradeは本文childrenを先に保存し、成功後にDeep Dive／Readyプロパティをcommitする。children失敗時はReady状態へ更新しない。properties commit失敗時は、今回追加したchildrenをbest-effortでrollbackし、Pending Retryへ遷移する。Pending Retryの状態保存にも失敗した場合はTelegramで運用者へ通知する。
- 既にMarkdown manuscript childがあるRetryでは本文を再appendしない。これによりrollback失敗後の二重本文を防ぐ。
- URL重複判定は新規候補・Notion既存URLに共通のcanonicalizationを適用する。末尾`/`、fragment、`utm_*`、`fbclid`、`gclid`、`ref`、`source`を除去するが、意味のあるquery parameterは維持する。
- Cross-source identityには候補が明示的に保持する公式／一次URLに加え、HN item URL・Product Hunt discovery URLをmigration aliasとして利用する。これは旧Stock行との再重複防止専用で、タイトル類似だけによる推測dedupeは行わない。Legacy migrationの重複除去はさらに限定し、`Source`と正規化`Primary URL`が完全一致するAMBIGUOUS行だけを1 seedへ統合できる。この場合もTechnology identityは`AMBIGUOUS`のままとし、URL相違・タイトル一致・空URLは統合しない。
- arXivの429・503・timeoutはPending Retryのままにする。ID不正、title mismatch、実在確認失敗等の恒久的Source Integrity Failureは、既存Notionページがある場合に`Content Status=Quality Failed`、`Article Status=Not Planned`、`Grounding Status=Failed`へ反映する。未公開記事本文は保存しない。
- Stale判定はStock作成日時ではなく、最新の`Article Status=Ready`記事の`Analyzed At`を基準にする。Needs Editorial ReviewはStaleを隠さない。
- 会員公開DBへの同期条件は`Review Status=Public Approved` **AND** `Article Status=Ready`。内部DBをSource of Truthとしてreconciliationし、過去に同期済みでも承認取消・Review・Quality Failed等で条件を外れた内部レコードは会員DB側をarchiveする。内部DBに対応URLがない手動レコードは勝手に削除しない。

## 7. 記事・品質仕様

- note原稿は原則無料公開。paywall区分は出力しない。
- タイトルは必ず「。」または「？」で終える。
- 公開稿のReader-first構成は、タイトル → `30秒でわかるこの記事` → `元情報` → 人間らしい導入 → 本文（結論/Why/What/要点/判断/Action） → CTA → `Sources / Evidence` → Disclaimer を基本とする。
- `30秒でわかるこの記事`は「何が出た？」「なぜ重要？」「結論は？」の最大3項目。追加Gemini requestは使わず、4 Quality Gateを通過した既存Management Data / ARTICLEから0 APIで抽出し、先頭の完結文だけを表示する。
- `元情報`は主一次情報、発見経路、取得できる場合のみ公開・更新日を簡潔に示す。権利表記・補助Evidence・Discovery URL等の監査情報は末尾へ残し、冒頭をURL一覧にしない。
- 詳細出典は末尾の`Sources / Evidence`に集約し、主一次情報、発見経路、ライセンス/著作権注記、補助Evidence、関連Discovery情報を監査可能な形で保持する。
- 人間らしい導入では技術背景と実務上の問いを自然に展開し、冒頭サマリーと同じ説明を機械的に繰り返さない。
- Deep DiveではURL Context、一次情報、必要に応じたPDF・公式リンクを確認する。
- Google Search Groundingは既定でOFF。
- Deep Dive前に`Evidence-to-Decision Sufficiency`を意味ベースで確認する。確認対象の網羅性ではなく、取得済みの一次情報から、結論強度・Action・時点を安全に限定した記事が成立するかを判定する。
- Hard Requirementは、一次ソース解決、技術的主張、記事で数値を使う場合の数値条件、特定主体へ帰属する場合のActor Attributionである。制約、鮮度、比較、Action根拠はConditional Requirementとし、一律の停止条件にしない。
- 制約未確認時は、未確認をWhy NOT/Caveatへ明示し、実運用限界・本番導入を断定しない。研究・ベンチマーク記事の鮮度未確認時は「原資料公開時点」「この研究で確認された範囲」と時点を限定する。現在価格・現行提供状況・法令等は鮮度確認が必須である。
- ActionはLOW／MEDIUM／HIGHのリスクTierで扱う。弱いEvidenceでも限定PoC、評価項目追加、ログ可視化、比較テスト、見送りなどのLOW RISK Actionは許可できるが、全面導入・本番移行・大規模投資などHIGH RISK Actionは制約・鮮度・条件を含む強いEvidenceを必須とする。
- Action Risk Tierは生成前の安全制約だけでなく、生成されたAction本文も意味ベースで再分類する。弱いEvidenceにもかかわらずHIGH RISKへ強まった稿はQuality Gateで通さない。
- MEDIUM／HIGH RISK Actionが現Tierで支えられない場合は、追加Evidenceがあれば先に`SUPPLEMENT_REQUIRED`とする。補強後も支えられない場合は、一次情報から導ける具体的なLOW RISK Actionへ縮退する。現在価格・現行提供状況などの鮮度必須条件、一次ソース未解決、技術主張不足は縮退で回避しない。
- Evidence Sufficiencyは`SUFFICIENT`、`SUPPLEMENT_REQUIRED`、`INSUFFICIENT`の3状態とする。文字数の閾値だけで合否を決めない。
- `SUPPLEMENT_REQUIRED`の場合だけ、一次資料・公式Docs/README・論文PDF・補足資料の順で追加取得する。`MAX_EVIDENCE_SUPPLEMENT_ATTEMPTS`、`MAX_EVIDENCE_DOCUMENTS`、`MAX_EVIDENCE_TOTAL_CHARS`の上限を守り、同一URLを再取得しない。
- 最終成果物のEvidence URLはGemini grounding metadataだけに依存せず、Primary URL、実際に取得したEvidence Supplement資料、Grounding URLを監査順に統合する。Stock dedupeでは同一資産として扱うarXiv `abs`/`pdf`も、監査証跡では「実際にPDFを読んだ」ことを残すため別URLとして保持する。ReadyだけでなくNeeds Editorial ReviewのNotion `Evidence URLs`とレビュー原稿末尾にも同じ規則を適用する。
- 補強後も`INSUFFICIENT`なら`PRIMARY_EVIDENCE_INSUFFICIENT`をGate履歴へ記録し、公開・Quality Failed保存・Gemini呼出しを行わずBackfillする。
- Evidence Scope、数値、条件、制約、鮮度、Actor Attributionを品質ゲートで検証する。
- Geminiへ送る記事生成Prompt contextは従来どおり最大12,000文字とし、Fact/Evidence Gateだけは実取得したPrimary HTML/PDF/公式Docsを最大`VERIFICATION_CONTEXT_MAX_CHARS=180000`で保持する`verification_context`を参照する。長文は冒頭に加えて末尾のLimitations/Appendixも残し、後取得のSupplement PDF/DocsがLanding本文に押し出されないよう専用枠を確保する。追加Gemini requestは発生しない。
- 数値Fact照合では、日本語/英語・range表記・単位差を正規化する。例: `10-hour`と`10時間`、`50–80 percent`と`50〜80%`、`3–7x`と`3〜7倍`。同じ数値でもhardware/dataset/metric等の明示条件が矛盾する場合は従来どおりFailする。
- Source BoundaryではFact主張とLOW RISK Actionを分離する。`Cargo.lock`、設定ファイル、log等のローカル監査成果物は、監査/確認/検証Action内で一次資料への逐語一致を要求しない。一方、外部製品の未確認機能・API・価格・対応状況をAction文で補完することは許可しない。
- `LLM API`等、一般略語だけからなる複合語は固有製品名として扱わない。
- Human Appeal Gateは、架空の感情・使用体験に加えて、`現場で〜を進める立場として`、`日常の〜でも同じ傾向を感じます`等の実在しない職務経験/日常体験をReview対象にする。`私なら`、`私の見解では`等の編集判断、読者への経験質問は架空体験と区別する。
- Freshness follow-upは、release/launch/support/availability/公開/提供/発売等の状態変更予定に限定する。研究論文の`future work`だけでは製品鮮度確認を発火しない。
- 内部のDecision構造は固定し、noteで見せる導入・見出しだけを記事ごとに可変化する。
- 読者の疑問、発見、数字への留保、実務課題の4種類から導入を選ぶ。発見経路・原資料・技術背景を残しつつ、導入は2〜4段落で自然に構成する。
- 記事には観察または留保を最低1箇所置く。架空の感情・使用体験は生成しない。
- 「理由は3つ」「結論から言うと」等の定型句、箇条書き、疑問形、同一文末の過剰な反復をHumanization Gateで検出する。
- Humanization Gateの問題は、一次情報取得やFact Checkを再実行せず、既存の品質再編集（最大1回）で表現だけを修正する。
- Publication Readiness Gateでは、タイトル・導入・結論・Action・Decision Score・一次情報量を横断確認する。事実誤認はQuality Failed、根拠不足や判断の飛躍は`Needs Editorial Review`として分離する。`Fact Gate=FAIL`の稿はPublicationがREVIEWでもNeeds Editorial Reviewへ降格させず、必ずQuality Failed側へ送る。
- Human Appeal Gateを独立して設ける。過剰な曖昧化、具体Actionの「注視」への置換、説明的すぎるタイトル、編集後の筆者判断の消失を検出する。
- 再編集は根拠のない主張の該当箇所だけを直す。根拠付きの観察・判断・限定検証・見送り判断は残し、安全性のために記事全体を無難な一般論へ均さない。
- Human Appealの軽微な警告は記録して公開を妨げないが、判断の具体性・タイトルの役割が失われた場合は`Needs Editorial Review`へ送る。
- Quality Gateの正式関数名は、`validate_fact_gate`、`validate_editorial_gate`、`validate_publication_readiness_gate`、`validate_human_appeal_gate`。実行順もこの順序で固定する。
- 旧名の`validate_publication_readiness`と`validate_human_appeal`は、外部補助コードとの互換性のため正式関数を参照するaliasとしてのみ残す。Pipeline本体は正式名を使用する。

### 記事生成失敗時の扱い

記事が0件となる場合でも、収集・Screening・Calibration・Observed保存・Stock保存が成功していれば、Pipeline全体の失敗とは扱わない。記事生成を停止する主な理由は次のとおりである。

- `MAX_TOKENS`等による出力途中切れ
- 必須見出し、結論、Actionなど記事構造の欠落
- 一次情報にない数値・期間・固有名詞・保証表現の混入
- Fact Gateによる根拠外表現の検出
- Publication Readiness Gateによる根拠不足・判断飛躍の検出
- Human Appeal Gateによる具体的判断の消失、過剰な無難化、Actionの「注視」化
- Geminiの429・503・利用可能モデル枯渇などのPending Retry
- Notion永続化失敗（品質Gate通過後にReadyをcommitできない場合）

これらは品質を満たさない記事の公開を防ぐFail-Closedの結果であり、API枠を増やすだけでは解消しない。再実行時は、Pending Retryを最長待機順で救済するが、専用実送信上限2回/Runを超えず、Fresh候補用のDeep Dive request budgetを温存する。候補試行上限・モデル別Safety Capも超えない。

## 8. Observed履歴

保存先は`observed_history/`。1実行につき1JSONを作成し、同名をGitHub Contents APIで保存する。

主な保存項目:

- run_id、analyzed_at、total_collected、total_screened、stock_threshold
- batch_calls、recovery_calls、calibration_calls
- 各候補のID、Source、名称、URL、公開日時、Engagement
- raw_screening_score、final_screening_score、raw_commercial_value_score、commercial_value_score
- raw_shelf_life_score、shelf_life_score、shelf_life、deep_dive_priority_score、reason、calibrated
- screening_status、error_category、stocked
- Source ROI profile、当該RunのSource別fetch allocation

GitHub保存が失敗しても日次Pipelineは停止せず、ログとTelegramで通知する。

## 9. 運用・出力

- GitHub Actionsの日次Workflowから`python pipeline.py`を実行する。mainへのpushではUnit Test＋Synthetic Regression smokeを自動実行し、翌日のDailyまで不具合検知を遅らせない。
- production起動時はNotion内部DBの必須Property名・型をPreflightし、Schema不整合ならGeminiを1回も消費する前にFail-Closed停止する。
- Pending Retryは`last_edited_time ASC`で最も長く待っている候補から処理する。ただし`GEMINI_PENDING_RETRY_REQUEST_BUDGET=2`を既定値とし、旧失敗記事が当日のFresh候補用Deep Dive枠を食い潰さない。専用枠を使い切った候補は次Runへ残す。
- 月末にはNotion保存資産を基に会員向け月次ダイジェストを生成する。会員限定性を守るためraw GitHub URLへcommitせず、`monthly_digests/`をGitHub ActionsのPrivate Artifactとして90日保持する。
- アイキャッチはDecision Score閾値ではなく、Article StatusがReadyとなる公開可能記事に生成し、GitHubへ保存する。
- TelegramにはCollected、Screened、Screening API Calls、Calibration、Stock、Deep Dive Ready、Gemini予算に加え、model別・用途別のGemini API attempt内訳を通知する。
- Free Article → Subscription Attributionの設定・CSV集計手順は`SUBSCRIPTION_ATTRIBUTION_SETUP.md`を運用基準とする。note標準Dashboardの数値だけからsubscriber conversionを推測しない。

### Gate可視化と内部レビュー

- 日次実行ごとに、Pending Retry候補数、新規Deep Dive候補数、総処理候補数、Generation API完了、記事解析完了、Quality評価完了、Readyを分離して集計する。Evidence Sufficiency（補強要・補強成功・不足）、Gemini呼出し回避数、動的Retryの試行・成功・失敗・非Repairable/Budget理由によるSkip、`MAX_TOKENS`、構造不足、一次情報不足、4 Gateの脱落数、`Pending Retry`もGate Funnelに含める。`MAX_TOKENS`は最終稿だけでなく初稿/Retryを含む試行履歴のどこかで発生すれば保持する。Readyが0件でも必ずFailure Summaryを出力する。
- 候補ごとに、順位、URL、Decision Score、各Gateの実行結果、Reason Code、最終状態、保存可否、Evidence Sufficiencyの初回・最終結果、Decision Scope、安全なAction Risk Tier、Evidence Gap開示要否、確認資料数・チェック項目、Gemini呼出し有無、Retry診断情報をGate履歴へ記録する。実行済みGateは後段で`NOT_RUN`へ上書きしない。
- Grounding状態は`pre_generation`、初回生成、Retry、最終を段階別に保存する。RetryでGrounding metadataが欠けても、事前確認済みの一次ソース状態を失わない。
- Readyが0件の場合のTop Failure Causesには、`TECHNICAL_CLAIMS_INSUFFICIENT`等のEvidence Insufficient詳細Reason Codeを候補履歴から件数集計して表示する。`PRIMARY_EVIDENCE_INSUFFICIENT`だけに丸めない。
- Evidence Supplement候補は、既に抽出済みの研究リンクに限定しない。収集済みの公式サイト・Docs・プロジェクトURL・arXiv PDFを対象にし、同一URL再取得禁止と既存の2回／3資料／12,000文字上限を守る。Google Searchの既定OFFは維持する。
- arXivでは同一論文PDFをEvidence Supplement候補の最優先とする。`/prevnext`、`/IgnoreMe`、トップページ、`/search`、`/list`、`/help`、`/login`、`/format`等のナビゲーション・補助URLはEvidence SupplementおよびFreshness follow-up候補から除外し、補強回数を消費させない。
- Product Huntの`/r/...` URLは、取得時およびPending Retry時に一度だけ公式製品URLへ解決する。解決先の公式サイト、Docs、GitHub等の一次情報リンクをEvidence Supplement候補に追加し、技術主張不足でも候補がある場合は補強を先に試す。
- arXivの再照会で429・503・timeout等の一時障害が起きた場合は`Pending Retry`として扱い、Quality Failed原稿を保存しない。arXiv ID不正・title mismatch・実在確認失敗は従来どおりFail-Closedである。
- 実運用で過剰Failとなった`Model Hypnosis`、`Topological Attribution Distance (TAD)`、`When Agents Coordinate`は、固有タイトルによる特別扱いはせず、Quality Failedへ直行させず少なくとも`Needs Editorial Review`へ到達可能であることを固定Regression Caseとして検証する。
- `Needs Editorial Review`原稿は既存Notion内部DBの同一Stockページへ全文保存すると同時に`review_candidates/`へ内部Artifact保存するが、`Public Approved`にしないため公開DB・会員公開DB・noteへは送らない。`Quality Failed`原稿は従来どおり`quality_failures/`へのprivate artifact保存のみとし、Notion本文には保存しない。
- Evidence metadataは一次資料本文に明示された技術仕様、数値、API／package／function名を抽出する。`WIP`、`work in progress`、`not supported`、`unsupported`、`not implemented`、`does not support`、`experimental`も制約候補として扱うが、本文にない根拠は補完しない。
- `FACT_ACTOR_MISMATCH`は人・組織・発表主体・製品主体の帰属誤りだけに用いる。技術規格名・API名・関数名の一次資料外記述は`FACT_UNSUPPORTED_NAMED_FACT`として区別する。
- 記事構造は固定の見出し文字列ではなく役割で確認する。`気になった背景`、`ここが大きい`等が重要性の役割を満たす場合は許容する。Human AppealのDecision Voiceは、観察文だけでなく根拠付きの限定Action、比較、見送り、CI・回帰テスト・profilingも認識する。
- Score Narrative mismatchはAction Risk Tierと合わせて確認する。60点台でもLOW RISKの限定PoC・比較・検証は不整合にせず、低スコアでの全面導入や高スコアで理由のないWATCH等の実質的な矛盾だけをReview対象とする。
- Quality Retryでは初稿の`trigger_reason_codes`を履歴として保持しつつ、最終稿を再評価した残存問題だけを`final_reason_codes`と最終Gate Statusに反映する。
- `Taffy`（Decision Score 63／LOW RISK PoC）はFalse Positive Regression Caseとして登録する。`Go 1.27`のCI・回帰テスト・profiling Action、`OpenRouter`のMCP等技術名、およびPacingの数値・条件一般化もSafety Regressionで検証する。
- GitHub Actionsでは内部保存物と`gate_history/`、`regression_cases_pending/`を非公開Artifactとして14日間保持する。公開Repositoryへcommitしない。
- Telegramには件数と主要Gateのみを通知し、記事本文・未公開情報は送らない。Real Article Regressionも未公開原稿全文をWorkflow Logへ出さず、private artifactへだけ保存する。
- 外部レビュー用Markdownは、Pipeline状態、失敗Gate、Reason Code、Decision Score、固定Rubric、記事本文をまとめて出力する。

### False Positive／False Negativeの回帰化

- Pipelineが`REVIEW`／`FAIL`で外部レビューがA／Bの場合をFalse Positive候補、PipelineがReadyで外部レビューがC／Dの場合をFalse Negative候補とする。
- False NegativeはGround Truth確認後に`critical`として扱う。
- 不一致は`regression_cases_pending/`へ候補として保存するだけで、自動的にGate閾値を変更しない。Gate変更はGround Truth、既存Synthetic Regression、既知Hard Negative、新ケースの修正をすべて確認してから行う。

## 10. テスト

| テスト | 現行結果 |
|---|---|
| Python構文チェック | 成功 |
| Notion Persistenceテスト | 48件成功 |
| Adversarial / Failure Injection | 127件成功 |
| unittest discovery | 291件成功 |
| Safety Unit Test | 76件成功 |
| Synthetic Regression Suite | Full 500/500成功、critical failure 0（2026-08-21実行） |

追加済みの主な検証は、arXivナビゲーションURL除外、同一論文PDFのEvidence最優先、Freshness誤巡回防止、Evidence資料上限3、200候補が8 Batchになること、Batch間ペーシング、JSON欠落・不正値検出、Calibration適用、Observed履歴の保存、表示見出しと導入段落数の可変性、架空体験の抑止、観察・留保、研究段階から本番導入への飛躍、弱い根拠に対する煽り見出し、過剰Hedging、具体Actionの消失、タイトルの無難化、再編集によるDecision Voice劣化、正式Gate関数名・alias・実行順、短いが意味的に十分な一次資料、長い販促文の不足判定、補強成功、Evidence不足時にGeminiを呼ばないこと、Reason Code別の動的Retry、制約未確認時のLOW RISK Action、研究記事の時点限定、現在価格の鮮度必須、生成ActionのRisk Tier判定、HIGH RISK Actionの拒否、公式補強候補、arXiv一時障害のPending Retry化、Gate履歴とFunnelの段階別集計である。

## 10.1 Failure Injection / Adversarial Regression

実記事の蓄積を待たず、想定事故を人工的に再現して危険なFalse Negative／False Positiveを先に潰す。専用テストは`tests/test_adversarial_regression.py`に保持し、通常の`unittest discover`から毎回実行する。

主な固定検証:

- 数値自体が一致していても、hardware・dataset・metric等の明示条件が矛盾する場合はFact根拠として通さない。
- `3.4x`／`3.4倍`、`1/40`／`40分の1`、sec／秒、ms／ミリ秒等の同義表現は誤Failしない。
- Evidence metadataの英単語判定はword boundaryを用い、`rapid`内の`API`、`latest`内の`test`等の部分一致をEvidence FOUNDと誤認しない。
- URLが存在するだけではPrimary Source Resolvedとせず、source-native本文／公式本文の実取得を必要とする。外部記事付きHNではHNコメントだけを一次情報扱いしない。
- HTTP取得はredirectごとにpublic URL検証を行い、公開URLからlocalhost/private IPへ転送されるSSRFを遮断する。
- URL canonicalizationはscheme/host case、既定port、query順、arXiv abs/pdf/version差を正規化する。Cross-source重複は、候補自身が既に保持する公式／一次URLの共有だけで保守的に判定し、タイトル類似だけで別案件を落とさない。
- Public DB同期は`Review Status=Public Approved`だけでなく`Article Status=Ready`も必須とし、Needs Editorial Reviewの誤公開を二重防止する。
- Monthly DigestおよびStale判定ではNeeds Editorial Reviewを完成Deep Diveとして扱わず、Readyだけを完成記事として扱う。
- Deep Dive local budget、transport retry budget、reserve判定が設定上限を超えないことをFailure Injectionで固定する。
- Quality Retry前後のHuman Appeal／Decision Voiceを比較し、具体Actionが単なる「注視」へ崩壊する等の実質劣化を検出する。`trigger_reason_codes`と`final_reason_codes`は分離して保持する。
- Gate組合せをAdversarial化し、`Fact FAIL × Publication REVIEW`がNeeds Editorial Reviewへ誤遷移しないことを固定する。
- Pending Retry公平性、Notion Schema Preflight、Persistent Counter予約順、**repository-local quota scope・旧key/project scope migration・API usage audit**、Public DB承認取消archive、Product Hunt recent-window、Freshness関連性、Workflow timeout/concurrency、月次Digest private artifactを固定Regression化する。
- Gemini実送信効率Regressionとして、Persistent Safety Cap拒否時にDeep Dive local budgetを消費しないこと、同一Runで到達済みmodelをsession exhausted化して次候補で再試行しないこと、Pending Retry実送信を2回/Runに制限すること、非Repairable Evidence理由でQuality Retryを抑制すること、初稿`MAX_TOKENS`を最終Funnelまで保持することを固定する。
- Needs Editorial Reviewでも補強PDF/Docsを最終Evidence URLへ残すこと、Notion Stock保存失敗候補を同RunのDeep Dive対象から除外すること、旧HN/Product Hunt discovery URLを明示aliasとして重複判定できることを固定Regression化する。
- `test_adversarial_regression.py`は直接実行と`unittest discover`で同じテスト集合を実行する。
- Profit PriorityをFailure Injection化し、Commercial ValueがStock閾値を迂回しないこと、Notion未永続化候補を押し上げないこと、Commercial再順位付け、EVERGREENの許容差付きPortfolio枠、Profit Priority無効化時の旧Decision順復帰、Profit補助項目欠落時のDecision行維持、Calibration/Observed履歴の独立保存を固定する。
- Content Portfolio BalanceをFailure Injection化し、同Topic偏重時だけ僅差の別Topicを繰り上げること、大幅に弱い別Topicを強制しないこと、`OTHER`/欠落Topicでは順位を動かさないこと、唯一のEVERGREEN枠を保護すること、無効化時に従来Priority順へ戻ること、Observed履歴へTopicを保持することを固定する。
- Source ROI LearningをFailure Injection化し、冷開始50件/Source、全4 Source最低25枠、状態破損Fail-Safe、実Notion Stockだけの歩留まり計上、学習後の高ROI配分を固定する。さらに4 Sourceの最大枠が共通値であること、同一ROIなら4 Sourceが対称配分されProduct Huntだけが優遇・抑制されないことを固定する。
- 2026-08-21 Real Article Gate Calibrationとして、AI Post-Trainingの`10時間`、VLAの`50〜80%`/`3〜7倍`、Rustの`Cargo.lock`監査、Harnessのresearch `future work`を一般化したRegressionへ固定する。加えて架空の職務/日常体験をFalse Negativeとして止め、長大Landingでも後取得PDFがverificationから落ちないことを検証する。固有タイトル・URLによる特例は作らない。

2026-08-21時点の結果: Adversarial 127/127、Notion Persistence 48/48、Safety 76/76、Subscription Attribution 11/11、Decision Intelligence 33/33、全Unit 295/295、Synthetic Regression Full 500/500、critical failure 0。

Notion Token境界: 既存Internal DBは`NOTION_API_KEY`、Technology Intelligence / Decision History DBは`NOTION_DECISION_INTELLIGENCE_API_KEY`を使用する。Migrationは旧DB readと新DB writeを別Tokenに分離し、専用Token欠落時に既存Tokenへ暗黙fallbackしない。

## 11. 主な環境変数

`GEMINI_QUOTA_PROJECT_ID=<Google Project ID, optional>`、`GEMINI_PERSISTENT_DAILY_COUNTER=true`、`GITHUB_FETCH_LIMIT=50`、`HN_FETCH_LIMIT=50`、`ARXIV_FETCH_LIMIT=50`、`PRODUCTHUNT_FETCH_LIMIT=50`、`PRODUCTHUNT_LOOKBACK_HOURS=72`、`MAX_SCREENING_CANDIDATES=200`、`ENABLE_SOURCE_ROI_LEARNING=true`、`SOURCE_ROI_HISTORY_RUNS=30`、`SOURCE_ROI_RECENCY_DECAY=0.93`、`SOURCE_ROI_MIN_SCREENED=50`、`SOURCE_ROI_MIN_DEEP_DIVE_ATTEMPTS=2`、`SOURCE_ROI_MIN_MATURE_SOURCES=2`、`SOURCE_ROI_MIN_FETCH_PER_SOURCE=25`、`SOURCE_ROI_MAX_FETCH_PER_SOURCE=75`、`SOURCE_ROI_EXPLORATION_WEIGHT=0.15`、`ENABLE_PROFIT_PRIORITY=true`、`DEEP_DIVE_DECISION_WEIGHT=0.65`、`DEEP_DIVE_COMMERCIAL_WEIGHT=0.35`、`EVERGREEN_PORTFOLIO_MIN=1`、`EVERGREEN_PRIORITY_TOLERANCE=8`、`ENABLE_PORTFOLIO_BALANCE=true`、`PORTFOLIO_MIN_DISTINCT_TOPICS=2`、`PORTFOLIO_TOPIC_PRIORITY_TOLERANCE=6`、`SCREENING_BATCH_SIZE=25`、`SCREENING_BATCH_PACING_SECONDS=10`、`ENABLE_GLOBAL_CALIBRATION=true`、`GLOBAL_CALIBRATION_MIN_RAW_SCORE=55`、`GLOBAL_CALIBRATION_BATCH_SIZE=50`、`ENABLE_OBSERVED_HISTORY=true`、`OBSERVED_HISTORY_DIR=observed_history`、`OBSERVED_HISTORY_GITHUB_DIR=observed_history`、`NOTION_SAVE_THRESHOLD_SCORE=60`、`TOP_N_FOR_DEEP_DIVE=3`、`GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS=9000`、`GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET=12`、`MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS=7`、`MAX_EVIDENCE_SUPPLEMENT_ATTEMPTS=2`、`MAX_EVIDENCE_DOCUMENTS=3`、`MAX_EVIDENCE_TOTAL_CHARS=12000`、`VERIFICATION_CONTEXT_MAX_CHARS=180000`。

## 12. 依存関係

今回のDeep Dive改修では、新しいPythonライブラリを追加していない。既存の`ai-intelligence-factory/requirements.txt`をそのまま使用する。

- `google-genai`
- `Pillow`
- `requests`
- `pypdf`

GitHub ActionsはWorkflow内で`pip install -r requirements.txt`を実行してからPipelineを起動する。したがって、今回の仕様更新に伴う`requirements.txt`の再生成・変更は不要である。


## 12. Decision Intelligence DB — Phase 1 Shadow Write

最上位事業要件は「無料note＝集客」「有料Technology Intelligence DB＋Decision History＋月次サマリー＝収益商品」。Phase 1では既存Internal Pipeline DBを変更せず、商品DBをside-pathとして追加する。既存`Decision Score`、`Status / Content Status / Article Status`、Stock閾値、Evidence、4 Quality Gates、Pending Retry、Ready定義は変更しない。

### 12.1 DB構成

- 既存Internal Pipeline DB: 記事生成・Retry・Ready等の運用状態。既存意味を維持する。
- Technology Intelligence DB: `1 Technology / Project = 1 current record`。Canonical Entity IDをUpsert keyとする。
- Decision History DB: INITIALまたは意味のあるCHANGEだけをappendする。毎日無変化Snapshotは作らない。

### 12.2 Decision ScoreとAdoption Score

既存Decision Scoreは記事化価値・ニュース価値・Business/Technical Impact等を含み、Stock時とDeep Dive時でも採点構成が異なるため、Adoption判断へ意味変更して流用しない。商品DBでは独立した`Adoption Score`を同じDeep Dive Gemini callのMANAGEMENT DATA内で生成する。追加Gemini requestは0。

Adoption Score内訳:
- Evidence Quality 25
- Production Maturity 25
- Use-case Utility / Fit 20
- Reliability / Security Risk 15
- Integration / Migration Feasibility 10
- Ecosystem / Support Durability 5

`Adoption Status`はWATCH / TEST / ADOPT / AVOID。ADOPTはEvidence Confidence=HIGHかつProduction Readiness=HIGHを必須とし、人気や新しさだけで決めない。

### 12.3 Entity Resolution

- GitHub: owner/repo
- arXiv: versionを除いたpaper ID
- Product / Framework等: 明示的なPrimary/official URLを保守的にcanonical化
- HN discovery URLだけでTechnology本体を確定できない場合はAMBIGUOUS
- タイトル類似だけのfuzzy mergeは禁止
- Source / Entity Alias / Evidence URLは再評価時に累積し、最新Signalだけで過去Evidenceを上書きしない

### 12.4 History transaction safety

- 新規currentは`HISTORY_PENDING`で作成し、INITIAL History確認後に`ASSESSED`へ確定する。
- Existing変更はHistory-firstでappendし、その後currentをpatchする。
- `History Event ID`で再送を冪等化し、History成功/current patch失敗後の次Runで二重追記しない。
- CHANGE Event IDには直前`Last Change At`をtransition anchorとして含め、将来同じスコア遷移が再発した場合は別Historyとして保持する。
- `HISTORY_PENDING`中に新評価が変わった場合は、pending currentの旧評価でINITIALを復旧した後、新評価をCHANGEとして追加する。
- Event ID collision、Canonical Entity ID collisionはFail-Closedする。

### 12.5 Isolation / Rollback

`ENABLE_DECISION_INTELLIGENCE_DB=false`が既定。OFF時は新DBへNetwork accessしない。ON時のみSchema preflightをGemini呼出し前に実行する。商品DB persistence failureは無料note記事のQuality/Ready stateを巻き戻さない。RollbackはFeature Flagをfalseへ戻すだけで、既存Internal DBへの逆Migrationは不要。

Legacy Migrationは必ずdry-run→plan artifact確認→applyの順で実施し、既存Internal DBはread-only。既存Decision Score/DecisionをAdoption Score/Statusへ変換せず、`LEGACY_PENDING`としてseedする。

Phase 1のNotion property詳細、TEST DB作成、Secrets、Migration手順、Subscriber Viewは`DECISION_INTELLIGENCE_SETUP.md`を正式運用手順とする。Phase 2のTracking Eligibility、Change-driven/Periodic Review、History由来What Changed? Monthly DigestはShadow Write検証後に実装する。

## 13. Revenue Product Phase 2 — Decision Intelligence商品完成仕様（2026-08-22）

Phase 1 Shadow Write後の正式商品ロジックとして、無料note記事価値と有料Technology追跡価値を分離する。Phase 2はLegacy Migrationを変更せず、既存4 Quality Gates・Internal Stock/Ready状態・Decision Scoreの意味を維持する。

### 13.1 Tracking Eligibility
Screening structured outputで`tracking_eligible`と`tracking_reason`を独立判定する。記事Final Score 60未満でもFinal 55以上かつ追跡価値があるRESOLVED Technologyは`SCREENED`としてTechnology DBへseedできる。AMBIGUOUSは自動商品評価しない。

### 13.2 Product Review / Legacy bootstrap
有料DBの再評価は無料記事Deep Diveと別のrun-local最大3 request枠、最大2 Technology/Runで行う。ただしPipeline全体50 requestとPersistent model/day counterを共有し、Free Tier Safetyを迂回しない。Legacy Inventoryが永久に後回しにならないよう、RESOLVED Legacyを最大1件/Run予約する。Evidence不足はNext Reviewへ延期し、毎日同一候補を再試行しない。

### 13.3 Deferred Deep Dive
Deep Dive 12/12、Provider unavailable、global budget停止で未試行となった上位Backfill候補は期限付きQueueへ退避する。翌Run最大1件。FLASH 2日、TREND 14日、EVERGREEN 60日。Queue保存失敗、Queue capacity overflow、処理後の再保存失敗はNotion Pending RetryへFail-safeし、候補を黙って失わない。

### 13.4 Source ROI v2
503 / quota / provider unavailable / Deep Dive run budget stopはSourceの品質・収益性を示さないためROI denominatorから除外する。Quality Gate failureはSource/題材の実質的な歩留まりとして残す。旧v1履歴はProvider障害汚染の可能性があるためv2移行時に学習へ持ち越さない。

### 13.5 Meaningful Change / History
Score差5未満の微小揺れ、同義Risk言い換えではCHANGEを作らない。Readiness / Confidence / Evidence / Riskカテゴリ / Statusの実質変化をHistory化する。WATCH⇄TESTはScore差3未満をhysteresisで抑制する。Legacy初回はINITIAL。INITIAL Event IDはTechnology単位で一意かつ再送冪等とする。

### 13.6 Subscriber安全分離
会員にはInternal Technology DBのViewを直接共有しない。別のSanitized Subscriber Technology DBへ、`ASSESSED`かつTracking Eligibility=trueかつ非ARCHIVEDのTechnologyだけを同期する。内部管理列をコピーしない。同一内容はPATCHせず、Source/Evidenceの順序差も無視する。

### 13.7 What Changed? Monthly
旧「今月の記事一覧」ではなくDecision History起点で、Status変更・Score上昇・急落・新規評価を月次商品化する。`Period ID=YYYY-MM`を冪等キーにし、Decision Historyは全件ページネーションする。Safety limit超過やPeriod collisionは部分商品を生成せずFail-Closed。Dailyは直近3完了月をcatch-up確認し、月末は当月も対象にする。

### 13.8 Product delivery maintenance
Subscriber sync / Monthly catch-upはFresh記事0件、duplicate-check停止、Screening quota停止等の主要early-returnでも実行する。無料記事候補の有無によって有料商品保守が止まらない。

### 13.9 正式運用手順
Phase 2のDB schema、Secrets/Variables、Feature Flag、段階導入は`REVENUE_PRODUCT_PHASE2_SETUP.md`を正式手順とする。Subscriber/Monthlyは別DB完成前はFeature Flag=falseを維持する。

---

# 追加正式仕様：Free Article Delivery Reliability（2026-08-22）

## 目的

無料noteは集客・認知の一次エンジンであり、Technology Intelligence / Decision Historyは課金商品である。したがって「Quality Failedを安全に止められること」だけでは事業完成条件としない。Fact Safetyを維持したまま、一次情報が十分な日に公開可能記事へ到達する歩留まりを最大化する。

ただし、`1日1本を何があっても公開する` は禁止する。一次情報不足・Provider障害・非修復Fact defectではReady=0を許容し、誤情報公開より売上KPIを優先しない。

## Free ArticleとProduct Reviewの分離

Free Article Deep Diveは記事本文と次の8管理項目だけを生成する。

1. Source Summary
2. What
3. Why Important
4. Decision
5. Decision Reason
6. Decision Score
7. Action
8. Article Value

Adoption Score / Adoption Status / Evidence Confidence / Production Readiness / Main Risk / Best For / Avoid ForはProduct Review専用とし、記事Promptで生成しない。旧出力のparser互換は維持する。

## Publication Reliability Slot

Deep Dive visible slotsのうち最大1枠を、追加Gemini APIなしのPublication Probabilityで補正できる。

- `ENABLE_PUBLICATION_RELIABILITY_SLOT=true`
- `PUBLICATION_RELIABILITY_SLOTS=1`
- `PUBLICATION_RELIABILITY_MIN_DECISION_SCORE=65`
- `PUBLICATION_RELIABILITY_MIN_ADVANTAGE=8`

Publication Probabilityは記事価値そのものではなく、Primary Source直結性・Source種別・metadata completeness・GitHub license等から「今日完成させやすいか」を推定する補助値。残り枠はDecision/Commercial/Portfolio優先を維持する。

## Deterministic Publication Rescue

`ENABLE_DETERMINISTIC_PUBLICATION_RESCUE=true`。

Gemini Quality Retryを消費する前に、既にGateで局所特定された欠陥のみ0 APIで減算修正できる。

許可：
- unsupported hypeの削除/弱化
- unsupported numeric claimを含む文の削除
- unsupported named factを含む文の削除
- fabricated personal experience文の削除

禁止：
- 新しいFactの追加
- Evidence不足の補完
- Generic unsupported claimの創作修正
- title内のunsupported numeric/named factの自動修復
- Actionを空にしてまでReady化

修正後はFact / Publication / Humanの実Gateを再実行し、通らなければ通常Retry/Fail-Closedへ戻す。

## Negation / Calendar false-positive対策

強い語の否定判定は固定文字数windowではなく同一文単位で行う。`今すぐ…推奨しません`、`デファクトスタンダードというわけではありません`等を強い導入推奨と誤判定しない。

`YYYY年M月`はcalendar表現として扱い、duration numeric claimと混同しない。

## Model scheduling priority

無料集客を先に保護する。

1. Fresh Deep Dive
2. Deferred Deep Dive（前Runで未試行）
3. Pending Retry（過去に実試行して失敗）
4. Product Review（有料DB評価）

Product Reviewは記事生成後に回す。Product Reviewの失敗でFlash modelをrun-local unavailableにした後、まだFresh記事を試していない、という状態を禁止する。

## Release Gate

Unit/Syntheticだけでは記事事業の完成を宣言しない。Run 97実失敗稿をReal Article Regression fixtureとして維持し、既知のfalse-positive/局所修復可能failureが再発しないことを確認する。

本番Release後は通常Dailyを1回実行し、Ready数・Generation success・Fact failure・Provider failure・Deterministic Rescue・Gemini使用量を監査する。Stock/Evidence/Generationが成立しているのにReady=0が継続する場合はBusiness Degradationとして再修正対象とする。

---

## 2026-08-22 Run 98 Quality Hardening（正式追補）

Run 98本番稼働と生成4記事の人手監査により、Free Article Reliabilityへ以下を正式追加する。

- Screeningは25件Batchを維持し、出力上限5000 tokens + 完全JSON object salvage + missing-ID-only Recoveryを採用する。壊れたobjectの推測修復は禁止。
- Publication Rescueはsubtractiveであることを維持する。ただし3文以上または重要数値を削除する場合は自動Ready禁止。初回ならQuality Retry 1回で再構成する。
- Dynamic Retry FunnelはAttemptedを伴わないSuccessを禁止し、Deterministic Rescueと計測を分離する。
- Eyecatch可否はDecision ScoreではなくArticle Ready gateを基準とする。
- Eyecatch表示仕様（2026-08-22確定）: 1280×670、Source別背景画像の左側に半透明Decision Cardを重ねる。記事タイトルは画像内へ重複表示しない。主表示は「意思決定スコア (Decision Score) X/100」と進捗バー、下段はDeep Dive正式内訳から「技術的破壊力 (Technical Impact) X/25」「緊急度 (Urgency) X/20」を表示する。下段値は`Score Breakdown`から0 APIで抽出し、欠損時は推測せず`—`表示とする。バー色はブランド表現として赤固定、長さだけDecision Scoreに比例させる。

- Fact Relation Gateを追加し、「AがBを提供」「XがYを提唱」「AがBを採用」等のEntity relationは同一Evidence文脈で関係性そのものを確認する。
- Product Hunt / Hacker NewsはDiscovery Source。評価根拠は公式サイト、Docs、GitHub、論文等へPrimary Source Resolutionする。Discovery metadata単独ではProduct evaluationのPrimary Evidenceにしない。
- 記事構造は問題提起型／実験型／数字型／意外性型／比較型の5型を安定ローテーションし、過去見出しは後方互換のみに保持する。
- Final Japanese Polishを0 APIでGate前に実施し、明確な助詞重複・語句重複等を安全な範囲で修正する。

詳細な検証結果は `RUN98_QUALITY_HARDENING_VALIDATION_2026-08-22.md` を正とする。

---

## Multilingual Title Normalization（2026-08-22 追加正式仕様）

### 目的
中国語・韓国語・Cyrillic等の非Latin原題を文字化けと誤認しないよう、原題の追跡性と日本語運用時の可読性を分離する。追加Gemini APIコールは使用しない。

### 正本と表示名の分離
- `nameWithOwner` / `originalTitle`: 収集元の原題をNFKC正規化して保持。Entity Resolution / URL Dedup / Source Integrityの正本として使う。
- `displayName`: NotionおよびTechnology Intelligenceの人間向け表示専用。Identity判定には使用しない。
- `sourceLanguage`: 0 APIのUnicode script判定（ja / en / zh-CN / ko / ru / und）。

### 表示ルール
- 日本語・英語: 従来タイトルを変更しない。
- 非Latin原題: 英語tagline/descriptionの安全なキーワード分類から、日本語カテゴリ名 + 原題で表示する。
  - 例: `电商出图吧` + e-commerce/product image context → `EC商品画像生成ツール「电商出图吧」`
- 十分な分類根拠がない場合は翻訳を捏造せず、`海外プロダクト「原題」` 等の保守的表示を使う。

### 原題保存
非Latinタイトルは既存`Source Summary`へ次を先頭追記する。
- `Original Title: ...`
- `Language: ...`
新規Notion必須プロパティは追加しないため、既存35-property preflightを壊さない。

### 既存行の自動補修
`get_existing_repo_urls()`で既に取得したNotionページ情報を再利用し、追加Readなし・Gemini 0 APIで最大25件/Runを補修する。補修対象は非Latin原題かつ未正規化の行のみ。`Name`と`Source Summary`だけをPATCHし、URL・原題・Canonical Entity ID等は変更しない。失敗時はwarningのみでDaily本体を止めない。

### Unicode Dedup Safety
タイトル照合キーはASCII限定正規化を廃止し、Unicode NFKC + casefold + Unicode word文字を保持する。中国語等が空文字キーへ潰れて誤重複する問題を防止する。


## 2026-08-22 Eyecatch Decision Score Color Scale
- Eyecatch progress-bar length is proportional to Decision Score.
- Score-band colors are fixed as: 0–59 Slate Gray `#64748B`; 60–69 Cyan `#22D3EE`; 70–79 Blue `#3B82F6`; 80–89 Purple `#8B5CF6`; 90–100 Gold `#F5B942`.
- These colors express Decision Score intensity only; they MUST NOT be interpreted as Adoption Status.
- Red is reserved for future AVOID / warning semantics.
- Eyecatch generation eligibility remains `Article Ready`, not a Decision Score threshold.

---

## 2026-08-22 Run 99 Gate Precision / Eyecatch Final 追補

Run 99本番監査により、Fact Relation GateのHard Failは高精度な明示関係主張に限定する。`開発体制`等の裸の名詞や技術名列挙をactor→object関係へ変換してはならない。主体・対象・関係動詞が文法的に明示され、Evidence内の同一関係で支持できない場合のみHard Failとする。これによりFalse Positiveを減らす一方、`A社がBを提供`、`X氏がYを提唱`等の高リスク帰属誤りは引き続きFail-Closedする。

False Negative Evidence判定はmetadataの`FOUND`だけを根拠にしない。benchmark/runtime/hardware/code availabilityは、Source Context内に具体的結果・条件・実体が存在する場合だけ「Evidenceに存在する」とみなしてARTICLEの「不明/未公開」と矛盾判定する。

Hacker News / Product HuntはDiscovery Source。Reuters等の二次ニュース媒体は取得できてもベンダー製品主張のPrimary Authorityではない。価格・仕様・リリース等は公式発表/Docs/GitHub等へ解決する。著者本人の技術ブログは、その本人の実験・意見についてPrimaryとして扱える。

公開ARTICLEでは内部管理コード`NOW / TRY / WATCH / WAIT / AVOID`を禁止する。Retryにも同制約を再注入し、最終0 API Polishはdecision contextのmanagement labelだけを自然文へ変換する。`Apple Watch`やcode block等の通常技術表現は変更しない。

Eyecatch最終仕様は1280x670 Source別背景＋左Decision Card。カード内は十分なpaddingを確保し、Header / Decision Score / progress bar / Technical Impact / Urgencyの情報群を上下中央に光学配置する。数値はGoogle Font Lato Boldを最優先し、GitHub Actionsで`fonts-lato`を導入する。フォントファイルはRepositoryへ同梱しない。進捗バーはScore帯に応じGray/Cyan/Blue/Purple/Gold、生成条件はArticle Readyである。


## Run 100 Article Audit Artifact — 2026-08-22

Dailyの`private-gate-review-<run_number>`を、Gate JSONだけでなく人間が記事本文を直接監査できるDaily監査パッケージへ拡張する。追加Gemini APIは使用しない。

- `article_audit/articles/ready/<candidate>/final.md`: Ready確定後の最終公開稿のみ。
- `article_audit/articles/quality_failed/<candidate>/generated_original.md`: 初回生成稿。
- `article_audit/articles/quality_failed/<candidate>/after_quality_retry.md`: Quality Retry後稿（存在時）。
- `article_audit/articles/quality_failed/<candidate>/final_after_rescue.md`: 最終Deterministic Rescue後稿。Rescueが不合格でも実際のRescue後本文を保存する。
- `article_audit/articles/pending_retry/<candidate>/current.md`: Pending Retry時点の最新利用可能稿。
- `article_audit/articles/needs_editorial_review/<candidate>/current.md`: Needs Editorial Review稿。
- `article_audit/eyecatch/`: Ready記事の最終Eyecatch。
- `article_audit/RUN_SUMMARY.md`: Candidate / Source / Decision Score / Final Status / Failure Reason / 対応Markdownの索引。

未公開本文はRepositoryへcommitせず、Actions Artifactにのみ保存し、既存どおり14日retentionとする。Article Audit保存失敗は記事生成・Notion永続化の成否を上書きしない観測系Fail-Openとし、ログへ明示する。

---

## Run 101 Human Audit Precision（2026-08-22）

Run 100 Article Auditで実生成本文を人間監査した結果、記事生成品質そのものよりもGate偽陽性が公開歩留まりを抑えているケースを確認したため、品質基準を緩和せず判定精度を修正した。

### Evidence Alias / Acronym
- 一次情報に略語が存在する場合に限り、明示的な同義語グループをEvidence照合へ追加する。
- 初期対象: `MCP ↔ Model Context Protocol`、`RAG ↔ Retrieval Augmented Generation`、`TTS ↔ Text to Speech`。
- 略語は単語境界一致を必須とし、`RAG` が `storage` の部分文字列として誤一致するようなEvidence捏造を禁止する。
- AliasはEvidenceの存在認識だけを補助し、製品機能・主体・バージョン・数値を新規推論しない。

### Editorial Soft Warning
- `mechanical ordinal structure` は監査上の警告として保持するが、単独では公開Hard Blockにしない。
- 箇条書き比率過多、反復的AI文体、過剰見出し等の実質的Editorial defectは従来どおりブロック対象。
- Soft Warning単独ではQuality Retryを消費しない。

### Cross-Article Template Diversity
- 5種の表示プロファイルは同一Run内で使用回数を均衡化する。
- 同一記事のQuality Retryでは初回割当を維持し、見出し型がRetryごとに揺れない。
- 状態はrun-localのみ。永続化せず、記事内容・Fact判定・Decision Scoreには影響させない。

### Run 100実記事から固定した回帰条件
- 一次情報が`MCP`と記載している場合、記事中の`Model Context Protocol`をUnsupported Named Factと誤判定しない。
- `第一に／第二に／第三に`だけでFact/Editorial Quality Failedにしない。
- 同一RunでESP32記事とKobo記事が同一表示プロファイルへ連続衝突しない。
- 未確認の`Enterprise Sync`等はAlias追加後もUnsupportedとして検出する。
- 既存Fact Relation Hard Negative（Timescale→pgvector、Karpathy→未裏付け提唱等）は維持する。

---

## Run 102 Publish Yield Precision（2026-08-22）

### 最上位事業原則
AI Intelligence Factoryは記事生成品質そのものを目的化せず、低コストの顧客獲得・継続課金・高粗利化を最上位目的とする。無料note記事は市場検証と送客の入口であり、重大なFact/Evidence問題を止めながら、十分に良い記事を不必要に廃棄しないことも品質保証に含める。

### Gate Severity
既存4 Gateの正式名称・順序は維持するが、Reasonごとに公開停止強度を別軸で保持する。

- `HARD_BLOCK`: Fact誤認、数値誤認、Evidence/Decision矛盾、読者を重大に誤解させる過剰断定、架空の個人体験等。公開不可。
- `REVIEW`: Fact安全性ではなく、意思決定価値または重大な可読性が不足する状態。例: Actionが「注視」だけへ崩壊、Decision Voice消失、本文の過半が箇条書き。最大1回の局所Retry対象とし、解消しなければNeeds Editorial Review。
- `SOFT_QUALITY`: 導入の弱さ、平凡なタイトル、反復語尾、機械的ordinal、軽微な見出し/Polish等。Warningとして監査するが、それだけでは公開を止めない。
- `OPERATIONAL`: Notion保存失敗、provider障害等。記事品質とは分離する。

未知の将来Editorial/Human Appeal ruleは自動的にSOFTへ倒さず、原則REVIEWとしてFail-safeする。

### 状態遷移
1. Fact / Editorial / Publication Readiness / Human Appealを従来どおり実行する。
2. 全ReasonをSeverity付きで正規化する。
3. HARD/REVIEWがなくSOFTのみなら`PASS_WITH_WARNINGS`として即Ready候補へ進み、Quality Retryを消費しない。
4. HARDのうち0 APIで安全に除去できる既知箇所はDeterministic Rescueを先に試す。
5. Evidence不足等の非修復HARDにはGemini Retryを使わない。
6. 修復可能HARD、またはDecision Valueに関わるREVIEWだけ最大1回Quality Retryする。
7. Fact PASS後もHARD/REVIEWが残る場合は、明示的Publication FAILを除きNeeds Editorial Reviewへ保存して公開しない。
8. Fact FAILまたは明示的Publication FAILが残る場合はQuality Failedとする。

### Profit Protection
SOFTを通す目的は記事本数の最大化ではなく、実市場データを得る機会損失と無料枠浪費を減らすことである。一方、`action_collapsed_to_generic_monitoring`、`decision_voice_missing`、架空使用体験、Evidenceを超える推奨は「読者が何をすべきか」という商品価値・信頼に直結するためSOFT化しない。

### Publish Yield観測
固定目標値は設定しない。Daily Funnelでは以下を併記する。

- Candidate Publish Yield = Ready / Deep Dive Candidates Attempted
- Generated Publish Yield = Ready / Generation Completed
- Candidates with HARD reasons
- Needs Editorial Review
- Ready with SOFT Warnings
- Retry Triggered by HARD
- Retry Triggered by REVIEW
- Retry Avoided (SOFT only)

`Editorial Gate Failed`という誤解を招く表示はuser-facing Funnelでは`Editorial Warning`へ変更し、旧counterは互換目的で内部保持する。

### Article Audit
Ready稿でもSOFT WarningをArticle Auditへ残す。`RUN_SUMMARY.md`はFinal Statusに加えDispositionとQuality Warnings / Failure Reasonを表示する。Ready記事の警告は`Failure Reason`ではなく`Quality Notes`としてfinal.mdへ保存する。

### API原価
SOFT Qualityだけの改善を目的とするQuality Retryは禁止する。追加外部APIは導入しない。Gemini Free Tier前提、Deep Dive最大Retry回数1回、Evidence Gate、Rescue Loss Limit、Article Audit、production isolationは維持する。


---

## Run 103 Reader-First Article Format（2026-08-22）

### 目的
無料noteの最初の10〜30秒で「何の記事か / なぜ重要か / どう判断すべきか / 根拠はどこか」を理解できるようにし、長文を読む前の認知負荷と離脱要因を減らす。記事のFact/Evidence基準を緩めず、追加API原価0で読者体験だけを改善する。

### 公開稿の順序
1. 記事タイトル
2. `30秒でわかるこの記事`
   - `何が出た？`
   - `なぜ重要？`
   - `結論は？`
3. `元情報`
   - 主一次情報
   - 発見経路
   - 公開・更新日（取得できる場合のみ。推測禁止）
4. Human Editorial Styleの導入
5. 本文・判断・Action
6. 会員向けCTA（設定済みの場合のみ）
7. `Sources / Evidence`
8. Disclaimer

### 30秒要約の安全設計
- 新規Gemini requestを追加しない。`What / Source Summary / Why Important / Action / Decision Reason`とGate通過ARTICLEの結論節を再利用する。
- 各項目は先頭の完結文を優先し、最大135文字程度へ0 APIで圧縮する。文章を新規創作して事実を足さない。
- 結論はARTICLE最終判断を優先し、次にAction、Decision Reasonを使用する。利用できない場合だけ内部Decisionを読者向け自然文へ決定論的に変換する。
- `NOW / TRY / WATCH / WAIT / AVOID`は冒頭要約では文脈を問わず公開禁止。大文字standalone codeも0 APIで自然文へ置換する。
- 日付が解析不能・欠落の場合は公開・更新日を非表示にし、推測しない。

### Evidence二層化
- 冒頭は主一次情報を1件だけ示し、URL一覧・権利注記を置かない。
- 末尾`Sources / Evidence`には従来の監査情報を保持する。補助Evidenceは最大3件の現行上限を維持する。
- Hacker News等のDiscovery Source表記を権利注記内で重複させず、上部元情報と末尾Evidenceで各1回にする。

### 非変更範囲
- 4 Quality Gates、Gate Severity、Evidence-to-Decision Sufficiency、Fact Relation Gate、Primary Source Authority Gate、Rescue Loss Limit、Notion Ready条件、Article Audit、Gemini予算、Deep Dive順位、Source ROI、Subscription Attributionの意味は変更しない。
- Reader-first headerはQuality Gate通過後の最終Markdown組み立てで追加するため、生成Promptのtoken面積とGemini呼出し回数を増やさない。


---

## Run 114 Product Review Reliability（2026-08-23）

### 目的
Run113でEvidence-ready候補を最大3件まで到達させられるようになった後に実地で顕在化した、Product Review出力の2つの損失要因を修正する。

1. GeminiがHTTP 200でも不正JSONを返し、Evidence-ready候補とGemini requestを廃棄する問題。
2. 実在する公式機能名が初期Verification Contextに含まれず、Source Boundary GateがFalse Rejectする問題。

### Structured Output
- Product Reviewは既存`gemini-3.6-flash`等の既存Model Poolを利用し、追加Provider/API経路を作らない。
- `response_mime_type=application/json`に加えて`response_json_schema`を指定する。
- Category、Adoption Score、6 Components、Status、Evidence Confidence、Production Readiness、Main Risk、Best For、Avoid For、Short Rationale、Next Review DaysをSchemaで拘束する。
- Providerの`response.parsed`がdict/Pydantic dumpとして利用可能なら優先し、なければJSON textを解析する。
- code fenceや前後transport textだけは0 APIで除去可能。欠損値・壊れた値の創作修復は禁止する。
- なお構造化出力が解析不能の場合に限り、同一候補を既存`PRODUCT_REVIEW_REQUEST_BUDGET`内で論理的に1回だけ再要求できる。`review_slots_used`は増やさない。

### Source-Boundary Reconciliation
- `source-boundary unsupported named fact`だけを対象とする。Numeric/Hype/Relation/Evidence不足等の別Gateは対象外。
- Assessment本文は書き換えず、根拠側だけを補強する。
- Product Review前に明示的に発見済みの公式Homepage/Docs/Primary Source URLだけをSeedにする。
- GitHub Repository HTMLのsite-wide navigation scrapingは禁止を維持し、GitHub metadata/READMEから明示された公式Docsを使う。
- Seed pageから同一first-party host配下のリンクだけを追跡し、unsupported named factに対応するlabel/pathを持つ子ページだけを最大2件選ぶ。
- 1候補あたりHTTP fetchは最大4回。Geminiは0回。
- 取得本文中にunsupported named factの完全名が実在した場合のみVerification Contextへ追加する。
- 根拠が見つからない、外部hostへ出る、取得失敗の場合は従来どおりFail-Closed。
- Reconciliation後はEvidence SufficiencyとDecision Intelligence Validatorを再実行し、全Gateを通った場合だけNotionへ保存する。

### Gemini予算
- Evidence reconciliationは0 Gemini。
- Structured Output Schema自体は追加Gemini requestなし。
- JSON破損時のlogical retryだけは既存Product Review request budgetを1回消費する。
- 新しいDaily budget、専用model、別API keyは追加しない。

### 監査メトリクス
Product Review resultに以下を追加する。
- `structured_retries`
- `structured_retry_recovered`
- `boundary_reconciliation_attempted`
- `boundary_reconciled`

### 非変更範囲
- Run113 Cross-Source Evidence ResolutionのEvidence-ready slot semantics。
- Quality Gates、Primary Source Authority、Fact Relation、Numeric/Hype Gate。
- Subscriber Sync / Decision Historyの保存意味。
- 通常Dailyの収集・Screening・Calibration・記事Deep Dive・記事生成順序。
- Product Review Max Reviews / Request Budgetの既存上限。


---

## Run 115 Product Review Adversarial Hardening（2026-08-23）

### 目的
Run114の独立反証監査で、既存テストがすべてPASSしていても見逃せる3種の死角が確認されたため、Product Reviewを追加APIなしでFail-Closedに強化する。

1. first-party SeedがHTTP redirectでthird-partyへ移動した後も本文をEvidenceとして採用できる問題。
2. Provider Structured OutputがJSONとして成立していても、必須field欠損・未知enum・余分なfield・component不整合・range逸脱等のSemantic Schema違反を局所Parserが受理できる問題。
3. Structured retryのテストがMock中心で、実Product Review Request Budgetの消費・上限を直接証明していなかった問題。

### Redirect後のfirst-party再検証
- Source-Boundary Reconciliationはrequest URLだけでなくHTTP取得後の`final_url`も再検証する。
- `final_url`がSeedのfirst-party host範囲外なら、本文・リンク・Evidence documentをすべて破棄する。
- Reject理由は`redirect_outside_first_party`として監査情報へ残す。
- third-party本文にunsupported named factが完全一致していても解決済みとは扱わない。
- 同一first-party host内のredirectだけは従来どおり利用可能。

### Local Semantic Schema Validation
Provider側`response_json_schema`を唯一のTrust Boundaryとは扱わず、保存前にapplication codeでも再検証する。

- required field完全一致。
- `additionalProperties=false`相当として未知fieldを拒否。
- Category / Adoption Status / Evidence Confidence / Production Readinessのenumを厳密検証。
- 6 Componentsのkey完全一致。
- component値・Adoption Score・Next Review Daysのinteger/rangeを厳密検証し、boolをintegerとして受理しない。
- 6 Components合計とAdoption Scoreの完全一致。
- Main Risk / Best For / Avoid For / Short Rationaleは空文字禁止。
- 未知Categoryを`OTHER`へ黙って丸めない。Schema違反として1回だけstructured retry対象にする。
- retry後も違反なら従来どおりFail-Closedで保存しない。

### Structured Output Prompt
- output shape、enum一覧、range、key一覧は`response_json_schema`へ集約する。
- PromptにはDecision semanticsだけを残し、Schema契約の重複記述を削減する。
- Components合計=Adoption Score、ADOPT条件、一次情報限定、主用途からCategory判断等の意味制約はPromptに残す。

### Gemini / Product Review Budget
- Semantic Schema failureのlogical retryは同一候補について最大1回。
- 既存`PRODUCT_REVIEW_REQUEST_BUDGET`とGlobal Gemini Budgetの双方に空きがある場合だけ送信する。
- Product Review Budget=1で初回を消費済みなら2回目のProvider送信は禁止。
- retryは`review_slots_used`を増やさないが、Product Review request数は実際に1追加消費する。
- 新規Gemini lane、追加API key、追加Daily budgetは作らない。

### 反証テストの強化
Run115専用テストは正常系だけでなく、以下の敵対入力を直接固定する。

- local HTTP 302でfirst-party URLから異なるhostへredirectし、redirect先本文にunsupported named factを置く。
- missing/extra field、未知Category、component欠落、component range逸脱、score sum不一致、bool score、blank text、review day range逸脱。
- `response.parsed`がSemantic違反なら正常な`response.text`へ勝手にfallbackしない。
- Product Review Request Budget=2では初回+structured retryの2回を実消費。
- Budget=1では2回目を送信せず、fake provider responseが未使用で残ることを確認。

さらにMutation/Negative-Controlとして、redirect guard、Category enum guard、Product Review budget guardを一時的に破壊し、対応反証テストがすべて赤になることを確認する。Mutation後は`pipeline.py` SHA256を元へ完全復元する。

### 非変更範囲
- Run113 Cross-Source Evidence ResolutionのEvidence-ready slot semantics。
- Run114 Source-Boundary Reconciliationの対象をnamed fact failureに限定する原則。
- Primary Source Authority / Fact Relation / Numeric / Hype / Evidence-to-Decision Gate。
- Decision History / Subscriber Sync / Notion保存意味。
- 通常Dailyの収集、Screening、Calibration、記事Deep Dive、記事生成、Eyecatch。
- Product Review Max Reviewsおよび既存Request Budgetの設定値。

---

## Run 116 Bounded First-Party Discovery（2026-08-23）

### 目的
Run115の実Bootstrap Applyで、Structured Output・Budget・Fail-Closedは正常化した一方、`mlflow/mlflow`の実在公式機能`Tracking Server`が初期Verification Contextに含まれず、Source-Boundary Reconciliationが4 fetch内で公式Docsへ到達できずFalse Rejectした。Run116はこのRecall不足だけを、Gemini追加0回・bounded HTTP・Fail-Closed維持で修正する。

### Bounded First-Party Discovery
- 対象は従来どおり`source-boundary unsupported named fact`のみ。Numeric / Relation / Hype / Evidence不足等の別Gateは対象外。
- Assessment本文は書き換えない。根拠側だけを補強し、再度同じValidatorを通す。
- Product Review前に明示的に得た公式Homepage / Docs / Primary SourceだけをSeedにする。
- まず公式Seed本文を最大2ページ確認し、Seedが露出する同一first-party linkを優先する。
- それでも未解決の場合だけ、Seed pathから決定論的に推定したfirst-party sitemapを最大3件取得する。
- sitemap indexを発見した場合、同一first-partyの子sitemapを残りの推測sitemapより優先する。
- sitemapから収集するURLは最大1,200件、named factとのURL lexical scoreで上位最大4件だけを本文取得候補にする。
- HTML/text本文の実取得はSeed・direct link・sitemap候補を合計して最大6件。無制限crawlは禁止。
- sitemap XML自体はEvidenceとして保存しない。
- third-party URL、third-party sitemap entry、redirect後にfirst-party外へ出た本文・linkはすべて破棄する。
- URLがnamed factに一致していても根拠とはみなさない。取得本文内にnamed factの完全token sequenceが存在する場合だけVerification Context / Evidenceへ追加する。
- `Tracking Server`は`Tracking-Server`等の区切り揺れを許容するが、`Tracking Serverless`のようなprefix一致は不採用。
- 根拠が見つからない場合は従来どおりFail-Closedで保存しない。

### コスト / API
- Discovery / sitemap / first-party page取得はHTTPのみでGemini 0回。
- `_generate_via_chat`のproduction call site数はRun115から増やさない。
- Product Review Request Budget / Global Gemini Budget / max_reviewsの意味は変更しない。
- Boundary Reconciliationが成功しても同一Assessmentの再validationだけを行い、追加Geminiは送信しない。

### 監査
Reconciliation resultは後方互換の`fetches`に加えて以下を返す。
- `body_fetches`
- `discovery_fetches`
- `discovered_urls`
- `ranked_candidates_considered`
- `documents_added`
- `unresolved_names`

### 非変更範囲
- Run115 Structured Output / Local Semantic Schema / retry budget hardening。
- Run113 Evidence-ready slot semantics。
- Primary Source Authority / Evidence-to-Decision / Fact / Relation / Numeric / Hype各Gate。
- Decision History / Subscriber Sync / Notion保存意味。
- 通常Dailyの収集、Screening、Calibration、記事Deep Dive、記事生成、Eyecatch。
- GitHub Actions workflowおよびInventory Bootstrap input contract。

