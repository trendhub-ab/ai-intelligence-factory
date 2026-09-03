# AI Intelligence Factory — 現行Production仕様

最終更新: 2026-09-03  
現行Functional Baseline: **Run209 — Gemini timeout RPD fail-closed**  
Documentation Governance Baseline: **Run210 — Documentation Freshness Guard**  
Paid Member Sync Baseline: **Run211 — paid member sync ordering**  
Paid Member UX Baseline: **Run215 — final current-authority action dedup**  
Paid Member Commerce/Onboarding Baseline: **Run217 — zero-API monetization readiness / member home**  
Repository Organization Baseline: **Run201 — repository garbage cleanup without intended runtime behavior change**  
Production Source of Truth: **`main`**

## 0. この仕様書の位置づけ

このファイルは「現在のProductionで何を守るか」を短く明示する現行契約である。

参照優先順位は次の通り。

1. `main` の実行コード、テスト、GitHub Actions workflow
2. 本ファイルの現行Production契約
3. `README.md` の運用・リポジトリ構造
4. `GEMINI_QUOTA_SETUP.md` 等の領域別Operator仕様
5. `docs/archive/` の過去Run仕様・検証記録

旧仕様は監査用であり、Run130以降の挙動をarchive文書から推測してはならない。

## 1. 事業・商品契約

AI Intelligence Factoryの事業構造は次で固定する。

**無料note記事 → 会員募集LP → noteメンバーシップ → 会員限定Notion Decision Intelligence + Digest**

- 無料note記事はAcquisitionチャネル。
- 有料価値は高密度な意思決定DBと会員向けDigest。
- 記事単体を有料note商品へ戻すことを前提にしない。
- subscriber PIIをGitHubの集計・attribution artifactへ持ち込まない。
- Public releaseは人間の最終操作とし、note自動化はprivate draftまで。
- Paid memberの正規入口はRun217で定義する`AI Intelligence｜会員ホーム`とし、内部Source pageや旧Presentation DBを商品入口として案内しない。
- LPでDigestを提供物として掲げる限り、Digest自動生成が停止中でも各月の提供サイクルを無提供にしてはならない。必要に応じて現在DBだけを使うhuman/zero-model Digestで履行する。

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

- 必須観測Source: GitHub / Hacker News / arXiv / Product Hunt
- Screening全体上限: 200候補
- Screening batch: 25件
- Raw Decision Score 55以上をGlobal Calibration対象とする現行設計
- Final Decision Score 60以上をStock保存対象とする現行設計
- Deep Diveは上位最大3件を基本とし、失敗時は次点Backfillを許容する
- Decision品質とCommercial Valueを混同しない
- Profit/Portfolio最適化は品質閾値・Evidence・Fact条件を迂回しない
- Observed履歴、Source ROI、deferred state等のProduction continuity dataを保持する

具体的な環境変数・重み・model候補・quota値は将来変更され得るため、実行コードとworkflowの値を優先する。

### 3.1 Pending Retry fast lane — Run206 / Run207

`pending_retry_validation.py` は、すでにScreening済みの高価値Pending Retryだけを再処理する低コストRecovery entrypointである。

- fresh collection / screeningを行わない。
- Screening Score降順で処理し、同点は既存安定順を維持する。
- 1記事成功で即停止する。
- 専用Gemini request budgetは**最大3回**。
- fast laneでは1回目のHTTP 503で当該modelをそのrun中cooldownし、`provider failure → valid generation → one quality recompose`の余地を残す。
- Persistent daily counter、global Deep Dive/run budget、Evidence/Fact/Reader/Publication gateは迂回しない。
- Public note releaseは行わない。

通常Productionのtransient 503 policyはRun205契約を維持し、fast lane専用overrideをProduction全体へ波及させない。

### 3.2 Reader Value repair — Run208

`run208_reader_value_repair.py` は、Pending Retry fast laneに限りReader-only failureを1回だけ再構成できる。

- 対象は既存reader bridgeがrepairableと判定したReader Value理由のみ。
- `dense_report_cluster` / `repetitive_insight` 等のReader-only失敗に限定する。
- Fact/Evidence blocker、過剰主張、非Reader Hard/Review理由が混ざる場合は発火しない。
- 1 processで最大1回。
- Evidenceを削ってReady化することは禁止。

## 4. 品質・Evidence契約

現行Productionでは、記事を売るため・投稿本数を増やすためにFact/Evidence/Decision品質を下げない。

維持すべき不変条件:

- Fact / Evidence / Decisionの整合性
- Primary Sourceを優先するEvidence authority
- Publication readinessのFail-Closed
- Human Appeal / reader-first編集品質
- 非エンジニアでも核心が理解できる平易さ
- Evidenceを削って「読みやすさ」を作らない
- 比喩・会話調は理解を助ける場合に使い、Evidenceそのものとして扱わない
- Reader Experience系の診断を理由に、重大なFact/Evidence gateを緩めない

## 5. Production runtime layer

`production_pipeline.py`は現行Production entrypointであり、以下を明示順でinstallする。

- `run203_runtime_state_channel.py`
- `gemini_timeout_rpd_fail_closed.py`
- `gemini_transient_recovery.py`
- `run172_production_reliability.py`
- `run173_operational_yield.py`
- `run174_monthly_digest_integrity.py`
- `run175_semantic_fact_precision.py`
- `run176_scope_fidelity.py`
- `run177_paid_funnel_alignment.py`
- `run178_eyecatch_editorial_layout_optimizer.py`
- `run179_eyecatch_font_refinement.py`
- `run180_eyecatch_semantic_layout.py`
- `run181_eyecatch_visual_balance.py`
- `run182_eyecatch_conclusion_emphasis.py`
- `run183_eyecatch_emphasis_scale.py`
- `reader_value_review_bridge.py`
- `run208_reader_value_repair.py`
- `run194_publication_contract.py`

これらはRun番号が古く見えても現役Production codeである。整理目的だけで削除・rename・統合してはならない。

### 5.1 Runtime state — Run203

`run203_runtime_state_channel.py` は、Gemini Persistent Counter等のProduction continuity stateをruntime-state channelとして扱う。

- Gemini reservation前にwritability / state preflightを行う。
- Production stateの書込み不能を楽観的に無視しない。
- `.runtime/` は生成ゴミではなく保護対象。

### 5.2 Gemini timeout RPD — Run209

`gemini_timeout_rpd_fail_closed.py` は、transport/watchdog timeoutでもprovider側RPDが消費され得るというAI Studio実測に合わせ、**pre-send reservationを巻き戻さない**。

- 3.5 / 3.6 / 3.7 FlashのFactory daily safety ceilingは**18**を維持する。
- Provider上限まで使い切る方向へ変更しない。
- timeout時の`release_unobserved`はProduction RPD残量を増やす目的には使わない。
- 過去の`released_unobserved`は監査履歴として残り得る。
- Google AI Studio Rate LimitsのProject-wide表示を最終的な外部実態として優先する。

詳細は`GEMINI_QUOTA_SETUP.md`を参照する。

### 5.3 Paid member product sync — Run211

会員向けNotion商品は、内部Technology/Subscriber DBから派生する表示DBを並列更新しない。Run211以降の権威ある順序は次で固定する。

**Source/Product Review更新 → Subscriber Decision Brief Sync → Member Presentation Sync**

- Daily / ONE-SHOT完了後は、まず`Subscriber Decision Brief Sync`が会員向けbridgeを整える。
- `Member Presentation Sync`はその成功後だけ自動実行し、Source workflowと並列に走らせない。
- `Subscriber Inventory Bootstrap`は**apply**のみ上記同期チェーンへ接続する。
- **Inventory plan**は0-API/read-only契約を維持し、下流のNotion書込みを発火させない。
- Subscriber Decision BriefとMember Presentationは`member-derived-notion-writes`で直列化し、同じ会員商品を同時更新しない。
- この派生同期はGemini APIを使用しない。
- `主なリスク` / `向いている用途` / `向いていない用途`等はSourceに存在する値を会員表示へ同期し、生成し直さない。
- `関連記事`はSourceの`関連記事（内部）`に実在する確定URLがある場合だけ伝播する。Public note releaseはhuman-onlyのため、公開URLが未確定なら空欄を許容し、推測URLを生成しない。

### 5.4 Paid member presentation copy authority — Run212

`run212_member_review_copy.py` は、Run201で監査用archiveへ移した過去Product Reviewを「現在の判断」として復活させず、読者向け説明コピーだけを限定利用するPresentation層である。

- `docs/archive/repository-cleanup-2026-09-02/external-review-history/` は引き続きhistorical/audit領域であり、active `external_reviews/` namespaceへ戻さない。
- archive由来で再利用できるのは `plain_summary` と `topic_trigger` のみ。
- archive `plain_summary` は現在値がMember UXのdeterministic fallbackと一致する場合だけ置換できる。
- archive `topic_trigger` は現在Topicがgenericな場合だけ置換できる。
- 現在DBに固有の非fallback summaryがある場合は現在値を優先する。
- archive由来の `short_rationale` / `main_risk` / `best_for` / `avoid_for` は空にしてから既存Human UXへ渡し、過去判断を現在値へ混入させない。
- score / status / Evidence / primary URL等のCurrent Decision Intelligence stateはRun212のarchive pathから変更しない。
- `20xx年x月時点`、`現時点`、`最新`、更新継続性を断定する等の時間依存archive copyは再利用せずFail-Safeで捨てる。
- 将来active `external_reviews/` が存在する場合はactive reviewをarchiveより優先し、既存Run170 behaviorを維持する。
- Run212はGemini/provider request pathを持たず、派生会員同期はzero-Geminiを維持する。

### 5.5 Paid member topic specificity — Run213

`run213_member_topic_specificity.py` はRun212の安全境界を保持したまま、Run212後にも残るdeterministic generic topicだけを現在情報で補うPresentation層である。

- Run212を先にinstallし、archiveのauthority境界を一切緩めない。
- post-Run212 `今回の話題` がgenericな場合だけ、**現在の `判断理由`** をtopic fallbackとして利用できる。
- 現在の `判断理由` が空・malformed・genericならFail-Safeで既存topicを維持する。
- 既存の非generic topicは上書きしない。
- topicへ現在判断理由を昇格した後はRun170.4の既存role separationを通し、`判断理由`がtopicと同文にならないよう現在のrisk/decision contextから分離する。
- archive `short_rationale` や過去risk等をRun213が再び判断権威として利用することは禁止する。
- `Safety 根拠` / `Transfer 根拠` のような既知の機械翻訳副作用だけを狭く修正し、product name / URL / score / status / Evidence / categoryを変更しない。
- Run213はGemini/provider request pathを持たず、新しい事実・評価・判断を生成しない。

### 5.6 Paid member action specificity — Run214

`run214_member_action_specificity.py` はRun213までの現在情報を維持したまま、会員DBの `次にやること` が安全な共通テンプレートへ過度に集中する問題を、現在の文脈だけで改善するPresentation層である。

- Run213を先にinstallし、Run212/213のauthority境界を一切緩めない。
- 対象はRun170.4が生成する**既知のdeterministic action templateだけ**。Source由来・手動・個別に書かれた非template actionは上書きしない。
- 元のaction本文、検証件数、人数、期間、比較指標等の既存手順は保持し、新しい閾値や評価基準を作らない。
- 文脈は**現在の `向いている用途` (`best_for`)を最優先**し、存在しない場合だけRun213後の**現在の非generic `今回の話題`**を利用する。
- `向いている用途` / `今回の話題` のどちらも安全に利用できない場合はFail-Safeで既存actionをそのまま維持する。
- score / status / Evidence / Fact / risk / primary URL / category / Product Review等のCurrent Decision Intelligence stateを変更しない。
- archive由来の過去判断・過去riskをaction authorityとして再利用しない。
- Run214はGemini/provider request pathを持たず、新しい事実・評価・判断を生成しない。

### 5.7 Paid member final action dedup — Run215

`run215_member_action_final_dedup.py` はRun214の安全境界を維持し、実DB監査で残ったaction重複だけを解消するPresentation層である。

- **具体的な現在の `向いている用途` は引き続き最優先**する。
- 実DB監査で確認された2種類のdeterministicな広域 `向いている用途` fallbackは、固有文脈として扱わない。
- 上記generic `向いている用途` と、Run213後の**現在の非generic `今回の話題`**が同時に存在する場合だけ、action文脈をcurrent topicへ切り替える。
- current topicがgeneric/空欄なら、重複解消だけを目的に文章を捏造せずRun214の既存best-for文脈を維持する。
- Run214のaction本文、件数、人数、期間、比較指標、明示的な非template actionは変更しない。
- score / status / Evidence / Fact / risk / primary URL / category / Product Review等のCurrent Decision Intelligence stateを変更しない。
- archive由来の過去判断・過去riskをaction authorityとして利用しない。
- Member Presentation workflowはPresentation/BodyともRun215 wrapperをentrypointとする。
- Run215はGemini/provider request pathを持たず、新しい事実・評価・判断を生成しない。

### 5.8 Paid member commerce / onboarding — Run217

Run217は記事生成・判断ロジックを変更せず、支払後の顧客が正しい商品へ到達できる状態を固定するzero-API商品運用Baselineである。

- 正規会員入口は`AI Intelligence｜会員ホーム`。
- Member Home Page ID: `3d0479ff-dca9-819e-9da0-c951225de6b3`。
- 現行Member Presentation DB ID: `d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1`。
- 現行Member Presentation Data Source ID: `d1461b6f-0940-4bf9-803a-6686a37c4ba2`。
- 会員ホームは同じ現行Data Sourceを参照する`① 今すぐ見る3件` / `② 実務判断だけ` / `③ すべての判断DB`を基本導線とする。
- 旧100件Presentation Data Source `ec2ac2b3-89b6-4242-89b9-e94060826fca` は`⚠️ 旧版・使用禁止｜AI・技術一覧（100件・更新停止）`へ改名済みであり、会員招待先・商品URLとして使用しない。
- 旧DBは監査目的で保持し、Run217を理由に削除しない。
- LP CTAはnote membershipへ接続する。入会確認後のNotion案内は内部`mlflow/mlflow` pageではなく会員ホームを使用する。
- `会員限定Digest｜2026年9月 初回版`は現行DBの確定情報だけで作成し、Gemini/model requestを使用していない。
- `今月の重要変化`と`今すぐ見る3件`は意味を分離する。重要変化0件の月初に、活性を演出する目的でPriority Top3を重要変化へ偽装しない。
- 詳細Operator仕様は`docs/reference/RUN217_ZERO_API_MONETIZATION_READINESS.md`を正とする。

## 6. Publication Contract / note Ready契約

note投稿対象は、単にContent Intelligence側が`Ready`であるだけでは不十分。

自動投稿候補になるためには少なくとも次を満たす。

- note Ready queueで投稿可能状態である
- 現行automatic publication policy fingerprintに一致するpersisted manuscriptを持つ
- manuscript captionのSHAと本文bytesが一致する
- 必須eyecatch assetが存在する
- historical paid-area control marker等の危険なlegacy条件を含まない

古い契約、hash不一致、asset不足の行を無理に復活させない。安全条件を満たさない既存destination rowは、現行sync policyに従いReady取消/取下げとなり得る。

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

`.github/workflows/note-create-draft.yml`の現行契約:

1. GitHub-hosted Ubuntuでzero-browser / zero-Gemini preflightを行う。
2. publish-safe candidateが0件なら`no_eligible_ready`として正常終了し、GCP Chrome VMを起動しない。
3. candidateがある場合のみVM起動を許可する。
4. preflightで選択した`sync_id`を固定してVM jobへ渡し、queue順変更による別記事選択を防ぐ。
5. VM側でも現行Publication Contractを再検証する。
6. 作成するのはprivate note draftのみ。
7. 公開は人間がnote上で確認後に行う。

明示`sync_id`の不一致、Notion/API障害、Publication Contract違反、asset不足等の真の異常はFail-Closedを維持する。

note draft pathはGemini/model requestを行わない。

## 8. GCP / browser cost contract

- publish-safe candidateが0件ならGCP note Chrome VMを起動しない。
- 実draft時のみpersistent Chrome VMをon-demandで使用する。
- VMはworkflow後に停止確認を行い、guest側failsafeも維持する。
- `note-cloud-preflight.yml`は記事候補preflightではなく、GCP VM / self-hosted runner / Chrome環境診断用の別workflowとして保持する。

## 9. 保護対象データ

次は生成ゴミではなくProduction continuity / 公開参照資産であるため、通常のrepository cleanupで削除・移動しない。

- `.runtime/`
- `observed_history/`
- `source_roi_history/`
- `deferred_deep_dive/`
- `eyecatch_images/`
- `assets/`

特に`eyecatch_images/`はNotion等からURL参照されている可能性がある公開資産であり、単純dedupeやrenameを禁止する。

## 10. テスト・変更管理

- `tests/`のRun番号付きtestは、古い名前だけを理由に削除しない。現在のinvariantを検証している可能性がある。
- similarly named workflowも役割を確認してから扱う。
- Production codeのsemantic refactorはrepository cleanupとは分離する。
- main反映前にRepository-wide Falsification Guard、zero-API regression、Synthetic smoke、関連CIを通す。
- Cleanup PRでproduction Pythonの削除・renameを行う場合は、別途明示的なequivalence proofが必要。

### 10.1 Documentation Freshness Guard — Run210

Canonical documentationを「後で更新する」運用は禁止する。Production変更と仕様更新を同一変更セットで扱う。

Run210以降、CIは少なくとも次を機械検証する。

- `production_pipeline.py`のactive runtime layerが本仕様書にすべて記載されていること。
- 現行Functional Baseline / Documentation Governance BaselineがREADMEと本仕様書で整合すること。
- Gemini Flash safety ceiling 18、Daily PAUSED、AI Studioを最終外部実態とするquota契約が`GEMINI_QUOTA_SETUP.md`とworkflowで矛盾しないこと。
- Pending Retry fast laneの最大3 request / 1回Reader repair契約がCanonical docsから欠落していないこと。
- Run211以降は、Inventory apply → Subscriber Decision Brief Sync → Member Presentation Syncの派生商品同期順序と、Inventory planのread-only境界も監視する。
- Run212以降は、archive Product Reviewを再利用する場合でも読者向けcopy-onlyに限定し、現在Decision Intelligenceの判断・Evidence・risk等へ昇格させない。
- Run213以降は、残存generic topicの最終fallbackがcurrent `判断理由`のみに限定され、archive判断や新しいFact生成へ広がっていないこと。
- Run214以降は、共通 `次にやること` の具体化がcurrent product contextに限定され、非template action・既存検証条件・Decision/Evidence stateを変更しないこと。
- Run215以降は、specific `向いている用途` を維持しつつ、既知generic best-for fallbackだけをcurrent non-generic topicへ退避できる。重複解消自体を目的に新しい文脈を生成してはならない。
- Run217以降は、README / Canonical docs / Operator仕様が正規会員ホームと現行Presentation DBを同じ値で指し、旧100件DBを現行商品として案内しないこと。

将来RunでProduction runtime layer、quota安全契約、Pending Retry、Publication/note安全契約、会員商品同期契約を変更する場合、**コードだけをmainへ入れてはならない**。Canonical docsを同じPRで更新し、Documentation Freshness GuardをPASSさせる。

## 11. Repository organization

rootは現在のoperator/canonical documentsと実行entrypointを優先し、過去Runの説明資料は`docs/archive/`へ置く。

Run200/201の整理内容と「意図的に整理しなかったもの」は`docs/archive/repository-cleanup-2026-09-02/`配下を参照する。