# AI Intelligence Factory 現行仕様

最終更新: 2026-08-20  
基準ファイル: `ai-intelligence-factory/pipeline.py` / `.github/workflows/daily.yml`

> 本仕様書は、直近のDeep Dive記事生成改善（出力途中切れ対策、限定的な増枠、Backfill強化）を反映した現行基準である。Pipeline本体の既定値とGitHub Actionsの環境変数指定が異なる場合は、GitHub Actionsの環境変数が優先される。現在は両方ともDeep Dive 12回設定で統一されている。

## 1. 目的と情報設計

AI・技術情報を毎日自動収集し、価値を段階的に選別して蓄積する。

| 層 | 対象 | 保存先 | 目的 |
|---|---|---|---|
| Observed | Screeningした全候補 | JSON履歴・GitHub | 観測、再浮上検知、トレンド分析 |
| Stocked | Final Score 60点以上 | 内部Notion DB | 検索・比較できる意思決定資産 |
| Deep Dive | Stocked上位から最大3件 | 既存Notionページを更新、note原稿等 | 一次情報に基づく詳細分析 |

Observedの全件をNotionへ保存しない。NotionにはFinal Score 60点以上のみを保存し、情報密度を維持する。

## 2. 日次処理フロー

1. Pending Retryを優先処理する
2. GitHub、Hacker News、arXiv、Product Huntを収集する
3. OSSライセンス安全性を確認する
4. Notion既存URL・ローカル重複を除外する
5. Source-balanced Round Robinで候補を構成する
6. 最大200件を25件ずつBatch Screeningする
7. Raw Score 55点以上をGlobal Calibrationする
8. 全Screening結果をObserved JSONへ保存し、GitHubへも保存する
9. Final Score 60点以上をNotion Stockとして保存する
10. Stock上位から最大3件をDeep Diveし、失敗時は次点をBackfillする
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
- Source障害はFault Isolationで局所化し、他Sourceの処理は継続する。
- Round Robinにより、先に連結されたSourceだけで上限を使い切らない。
- ローカル重複はURL末尾スラッシュや主要tracking parameterの差を正規化して除外する。

## 4. ScreeningとCalibration

### Batch Screening

- `SCREENING_BATCH_SIZE=25`
- 200候補の場合、通常は8回のGemini Flash-Lite呼出し。
- Batch間は`SCREENING_BATCH_PACING_SECONDS=10`秒待機する。
- 入力はID、Source、名称、説明、Engagement、Published At、URLのみ。本文・README・論文PDFの取得は行わない。
- 評価観点は技術的新規性、実務インパクト、意思決定への影響、緊急性、市場波及性、情報源の信頼性。
- Source間でEngagementの絶対値を直接比較しない。
- 出力はJSON配列（`id`、`score`、`reason`）。ID欠落、重複、未知ID、score範囲外、JSON不正を検出する。
- 欠落候補だけを最大10件のRecovery Batchで再試行する。正常結果は再送しない。

### Global Calibration

- `ENABLE_GLOBAL_CALIBRATION=true`
- Raw Score 55点以上のみを対象に、最大50件ずつ横断比較する。
- Calibration後の`final_score`をNotion保存・順位付け・Deep Dive候補選定に使用する。
- Calibration失敗時は、有効なRaw Scoreを保持して処理を継続する。

## 5. Gemini API保護

- Screening Model Pool: Flash-Lite系モデル（既定: `gemini-3.5-flash-lite`、`gemini-3.1-flash-lite`）
- Deep Dive Model Pool: Flash系モデル（既定: `gemini-3.6-flash`、`gemini-3.7-flash`、`gemini-3.5-flash`）
- 429、404、503等ではモデルPool内でFallbackする。
- Persistent Daily CounterでAPIキー・モデル単位の利用量を永続管理する。
- 実行内Gemini安全上限は50リクエスト。Deep Dive用に3リクエストを予約する。
- Screening Retry Budgetは4、Deep Dive Retry Budgetは1。無限Retryはしない。
- クォータ・通信障害はQuality FailedではなくPending Retry／未判定として扱う。

### Deep Dive記事生成の現行設定

- 1実行あたりのDeep Dive request budgetは既定12回。`GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET`で変更できる。
- 1回のDeep Dive出力上限は既定9,000トークン。管理データと記事本文を同時に出力するため、旧設定6,000トークンで発生した`MAX_TOKENS`による途中切れを抑制する。
- Deep Dive候補の試行上限は既定7件。成功記事数の目標は最大3件であり、4位以降をBackfillに使用する。
- Quality Gate不合格、出力途中切れ、一次情報不足、Pending Retryなどが発生しても、候補試行上限とAPI予算の範囲内で次点候補へ進む。
- Evidence Sufficiencyが`INSUFFICIENT`の候補はGemini Deep Diveを呼ばず、API枠を消費せずに次点候補へ進む。
- Quality Retryは最大1回。Reason Codeごとの対象箇所だけを直し、前稿を基準に根拠のある構成・主張を維持する。文字数を理由とした一律の短縮指示は行わない（`MAX_TOKENS`時の構造完全化指示を除く）。
- 12回への増枠は記事成功数を保証するものではない。根拠外表現、一次情報不足、Publication Readiness、Human Appealの不合格は引き続き公開しない。

### GitHub Actionsとの設定整合

`pipeline.py`の既定値と`.github/workflows/daily.yml`の`GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET`は、現在ともに12回で統一されている。GitHub Actionsの日次実行ではWorkflowの環境変数指定が適用される。

## 6. Notion保存仕様

### Stocked

- 条件: Final Score 60点以上
- 主な値: `Status=Stocked`、`Content Status=Stocked`、`Article Status=Not Planned`、`Subscription Visibility=Subscriber Only`
- 保存項目: Name、URL、Source、Engagement Score、Decision Score、Screening Score、Screening Reason、Source Summary、Published At、Analyzed At、License等。
- `Screening Reason`はStep 1の評価履歴として永久保持する。Pending Retry、Needs Editorial Review、Quality Failed、Persistence Failureの理由で上書きしない。
- GitHub候補のLicenseはStock保存時に保持し、Pending Retry復元時にも`licenseInfo.spdxId`として復元する。推測による補完はしない。

### Deep Dive

- 最大成功件数は3件。低スコア候補で本数を水増ししない。
- Stockの既存Notionページを更新する。重複ページを作らない。
- 成功時は`Status=Deep Dive`、`Content Status=Deep Dive`、`Article Status=Ready`となる。
- Readyは「4つのQuality Gateを通過」かつ「Notion永続化に成功」の両方を満たす場合だけに確定する。Notion保存失敗は記事品質失敗ではなく`NOTION_PERSISTENCE_FAILED`として記録し、Ready件数へ加算しない。
- Notion Upgradeは本文childrenを先に保存し、成功後にDeep Dive／Readyプロパティをcommitする。children失敗時はReady状態へ更新しない。properties commit失敗時は、今回追加したchildrenをbest-effortでrollbackし、Pending Retryへ遷移する。Pending Retryの状態保存にも失敗した場合はTelegramで運用者へ通知する。
- 既にMarkdown manuscript childがあるRetryでは本文を再appendしない。これによりrollback失敗後の二重本文を防ぐ。
- URL重複判定は新規候補・Notion既存URLに共通のcanonicalizationを適用する。末尾`/`、fragment、`utm_*`、`fbclid`、`gclid`、`ref`、`source`を除去するが、意味のあるquery parameterは維持する。
- arXivの429・503・timeoutはPending Retryのままにする。ID不正、title mismatch、実在確認失敗等の恒久的Source Integrity Failureは、既存Notionページがある場合に`Content Status=Quality Failed`、`Article Status=Not Planned`、`Grounding Status=Failed`へ反映する。未公開記事本文は保存しない。
- Stale判定はStock作成日時ではなく、最新のReady／Deep Dive記事の`Analyzed At`を基準にする。
- `Public Approved`のものだけを会員公開DBへ同期できる。

## 7. 記事・品質仕様

- note原稿は原則無料公開。paywall区分は出力しない。
- タイトルは必ず「。」または「？」で終える。
- 構成はタイトル、`はじめに`、結論、Why、What、要点、筆者ならどうするか、結局の順を基本とする。
- 導入部では発見経路、原資料、技術背景を示す。
- 出典には発見経路、原資料、原資料URL、関連情報、著作権注記を記載する。
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
- 補強後も`INSUFFICIENT`なら`PRIMARY_EVIDENCE_INSUFFICIENT`をGate履歴へ記録し、公開・Quality Failed保存・Gemini呼出しを行わずBackfillする。
- Evidence Scope、数値、条件、制約、鮮度、Actor Attributionを品質ゲートで検証する。
- 内部のDecision構造は固定し、noteで見せる導入・見出しだけを記事ごとに可変化する。
- 読者の疑問、発見、数字への留保、実務課題の4種類から導入を選ぶ。発見経路・原資料・技術背景を残しつつ、導入は2〜4段落で自然に構成する。
- 記事には観察または留保を最低1箇所置く。架空の感情・使用体験は生成しない。
- 「理由は3つ」「結論から言うと」等の定型句、箇条書き、疑問形、同一文末の過剰な反復をHumanization Gateで検出する。
- Humanization Gateの問題は、一次情報取得やFact Checkを再実行せず、既存の品質再編集（最大1回）で表現だけを修正する。
- Publication Readiness Gateでは、タイトル・導入・結論・Action・Decision Score・一次情報量を横断確認する。事実誤認はQuality Failed、根拠不足や判断の飛躍は`Needs Editorial Review`として分離する。
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

これらは品質を満たさない記事の公開を防ぐFail-Closedの結果であり、API枠を増やすだけでは解消しない。再実行時は、Pending Retryを優先しつつ、Deep Dive request budget・候補試行上限・モデル別Safety Capを超えない。

## 8. Observed履歴

保存先は`observed_history/`。1実行につき1JSONを作成し、同名をGitHub Contents APIで保存する。

主な保存項目:

- run_id、analyzed_at、total_collected、total_screened、stock_threshold
- batch_calls、recovery_calls、calibration_calls
- 各候補のID、Source、名称、URL、公開日時、Engagement
- raw_screening_score、final_screening_score、reason、calibrated
- screening_status、error_category、stocked

GitHub保存が失敗しても日次Pipelineは停止せず、ログとTelegramで通知する。

## 9. 運用・出力

- GitHub Actionsの日次Workflowから`python pipeline.py`を実行する。
- 月末にはNotion保存資産を基に会員向け月次ダイジェストを生成する。
- アイキャッチはDecision Score 60点以上で生成し、GitHubへ保存する。
- TelegramにはCollected、Screened、Screening API Calls、Calibration、Stock、Deep Dive Ready、Gemini予算を通知する。

### Gate可視化と内部レビュー

- 日次実行ごとに、Pending Retry候補数、新規Deep Dive候補数、総処理候補数、Generation API完了、記事解析完了、Quality評価完了、Readyを分離して集計する。Evidence Sufficiency（補強要・補強成功・不足）、Gemini呼出し回避数、動的Retryの試行・成功・失敗、`MAX_TOKENS`、構造不足、一次情報不足、4 Gateの脱落数、`Pending Retry`もGate Funnelに含める。Readyが0件でも必ずFailure Summaryを出力する。
- 候補ごとに、順位、URL、Decision Score、各Gateの実行結果、Reason Code、最終状態、保存可否、Evidence Sufficiencyの初回・最終結果、Decision Scope、安全なAction Risk Tier、Evidence Gap開示要否、確認資料数・チェック項目、Gemini呼出し有無、Retry診断情報をGate履歴へ記録する。実行済みGateは後段で`NOT_RUN`へ上書きしない。
- Grounding状態は`pre_generation`、初回生成、Retry、最終を段階別に保存する。RetryでGrounding metadataが欠けても、事前確認済みの一次ソース状態を失わない。
- Readyが0件の場合のTop Failure Causesには、`TECHNICAL_CLAIMS_INSUFFICIENT`等のEvidence Insufficient詳細Reason Codeを候補履歴から件数集計して表示する。`PRIMARY_EVIDENCE_INSUFFICIENT`だけに丸めない。
- Evidence Supplement候補は、既に抽出済みの研究リンクに限定しない。収集済みの公式サイト・Docs・プロジェクトURL・arXiv PDFを対象にし、同一URL再取得禁止と既存の2回／3資料／12,000文字上限を守る。Google Searchの既定OFFは維持する。
- Product Huntの`/r/...` URLは、取得時およびPending Retry時に一度だけ公式製品URLへ解決する。解決先の公式サイト、Docs、GitHub等の一次情報リンクをEvidence Supplement候補に追加し、技術主張不足でも候補がある場合は補強を先に試す。
- arXivの再照会で429・503・timeout等の一時障害が起きた場合は`Pending Retry`として扱い、Quality Failed原稿を保存しない。arXiv ID不正・title mismatch・実在確認失敗は従来どおりFail-Closedである。
- 実運用で過剰Failとなった`Model Hypnosis`、`Topological Attribution Distance (TAD)`、`When Agents Coordinate`は、固有タイトルによる特別扱いはせず、Quality Failedへ直行させず少なくとも`Needs Editorial Review`へ到達可能であることを固定Regression Caseとして検証する。
- `Needs Editorial Review`と`Quality Failed`の原稿・根拠メタデータは、公開DB・会員公開DB・noteへ送らず、`review_candidates/`または`quality_failures/`へ内部保存する。
- Evidence metadataは一次資料本文に明示された技術仕様、数値、API／package／function名を抽出する。`WIP`、`work in progress`、`not supported`、`unsupported`、`not implemented`、`does not support`、`experimental`も制約候補として扱うが、本文にない根拠は補完しない。
- `FACT_ACTOR_MISMATCH`は人・組織・発表主体・製品主体の帰属誤りだけに用いる。技術規格名・API名・関数名の一次資料外記述は`FACT_UNSUPPORTED_NAMED_FACT`として区別する。
- 記事構造は固定の見出し文字列ではなく役割で確認する。`気になった背景`、`ここが大きい`等が重要性の役割を満たす場合は許容する。Human AppealのDecision Voiceは、観察文だけでなく根拠付きの限定Action、比較、見送り、CI・回帰テスト・profilingも認識する。
- Score Narrative mismatchはAction Risk Tierと合わせて確認する。60点台でもLOW RISKの限定PoC・比較・検証は不整合にせず、低スコアでの全面導入や高スコアで理由のないWATCH等の実質的な矛盾だけをReview対象とする。
- Quality Retryでは初稿の`trigger_reason_codes`を履歴として保持しつつ、最終稿を再評価した残存問題だけを`final_reason_codes`と最終Gate Statusに反映する。
- `Taffy`（Decision Score 63／LOW RISK PoC）はFalse Positive Regression Caseとして登録する。`Go 1.27`のCI・回帰テスト・profiling Action、`OpenRouter`のMCP等技術名、およびPacingの数値・条件一般化もSafety Regressionで検証する。
- GitHub Actionsでは内部保存物と`gate_history/`、`regression_cases_pending/`を非公開Artifactとして14日間保持する。公開Repositoryへcommitしない。
- Telegramには件数と主要Gateのみを通知し、記事本文・未公開情報は送らない。
- 外部レビュー用Markdownは、Pipeline状態、失敗Gate、Reason Code、Decision Score、固定Rubric、記事本文をまとめて出力する。

### False Positive／False Negativeの回帰化

- Pipelineが`REVIEW`／`FAIL`で外部レビューがA／Bの場合をFalse Positive候補、PipelineがReadyで外部レビューがC／Dの場合をFalse Negative候補とする。
- False NegativeはGround Truth確認後に`critical`として扱う。
- 不一致は`regression_cases_pending/`へ候補として保存するだけで、自動的にGate閾値を変更しない。Gate変更はGround Truth、既存Synthetic Regression、既知Hard Negative、新ケースの修正をすべて確認してから行う。

## 10. テスト

| テスト | 現行結果 |
|---|---|
| Python構文チェック | 成功 |
| Notion Persistenceテスト | 43件成功 |
| unittest discovery | 112件成功 |
| Safety Unit Test | 69件成功 |
| Synthetic Regression Suite | Full 500/500成功、critical failure 0（2026-08-20実行） |

追加済みの主な検証は、200候補が8 Batchになること、Batch間ペーシング、JSON欠落・不正値検出、Calibration適用、Observed履歴の保存、表示見出しと導入段落数の可変性、架空体験の抑止、観察・留保、研究段階から本番導入への飛躍、弱い根拠に対する煽り見出し、過剰Hedging、具体Actionの消失、タイトルの無難化、再編集によるDecision Voice劣化、正式Gate関数名・alias・実行順、短いが意味的に十分な一次資料、長い販促文の不足判定、補強成功、Evidence不足時にGeminiを呼ばないこと、Reason Code別の動的Retry、制約未確認時のLOW RISK Action、研究記事の時点限定、現在価格の鮮度必須、生成ActionのRisk Tier判定、HIGH RISK Actionの拒否、公式補強候補、arXiv一時障害のPending Retry化、Gate履歴とFunnelの段階別集計である。

## 11. 主な環境変数

`GITHUB_FETCH_LIMIT=50`、`HN_FETCH_LIMIT=50`、`ARXIV_FETCH_LIMIT=50`、`PRODUCTHUNT_FETCH_LIMIT=50`、`MAX_SCREENING_CANDIDATES=200`、`SCREENING_BATCH_SIZE=25`、`SCREENING_BATCH_PACING_SECONDS=10`、`ENABLE_GLOBAL_CALIBRATION=true`、`GLOBAL_CALIBRATION_MIN_RAW_SCORE=55`、`GLOBAL_CALIBRATION_BATCH_SIZE=50`、`ENABLE_OBSERVED_HISTORY=true`、`OBSERVED_HISTORY_DIR=observed_history`、`OBSERVED_HISTORY_GITHUB_DIR=observed_history`、`NOTION_SAVE_THRESHOLD_SCORE=60`、`TOP_N_FOR_DEEP_DIVE=3`、`GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS=9000`、`GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET=12`、`MAX_DEEP_DIVE_CANDIDATE_ATTEMPTS=7`、`MAX_EVIDENCE_SUPPLEMENT_ATTEMPTS=2`、`MAX_EVIDENCE_DOCUMENTS=3`、`MAX_EVIDENCE_TOTAL_CHARS=12000`。

## 12. 依存関係

今回のDeep Dive改修では、新しいPythonライブラリを追加していない。既存の`ai-intelligence-factory/requirements.txt`をそのまま使用する。

- `google-genai`
- `Pillow`
- `requests`
- `pypdf`

GitHub ActionsはWorkflow内で`pip install -r requirements.txt`を実行してからPipelineを起動する。したがって、今回の仕様更新に伴う`requirements.txt`の再生成・変更は不要である。
