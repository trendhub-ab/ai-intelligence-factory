# AI Intelligence Factory — 現行Production仕様

仕様最終変更日: **2026-10-26**
Production最終照合日: **2026-11-01**
Production Source of Truth: **`main`**
Canonical Specification: **本ファイル**
Production Contract Fingerprint: **`9b14bb4e2d1fd2d55d5da7a787dd20a328d32ca7957e456eeedffc59513db641`**
実装監査基準SHA: **`774211333c9103d7bed92d46fa6d2824ec521953`**

> 本書は、現在のAI Intelligence Factory（AIIF）がProductionで「何を実行し、何を禁止し、どこをFail-Closedにするか」を示す唯一の全体仕様入口である。
> 実装監査基準SHAは、本書の意味内容を人間が最後に横断照合した`main`の基準点である。Production Contract Fingerprintは、現行Productionの実行コード・workflow・runtime asset等の実バイトから機械計算し、仕様書自身・tests・docsは含めない。mergeでHEAD SHAが進んでも、Production bytesが同一ならFingerprintは同一である。
> 過去のRun番号、検証レポート、Recovery文書、`docs/reference/`、`docs/archive/`、Git履歴は設計理由・監査証跡として参照できるが、現在の実装・安全契約を上書きしない。

---

## 0. Authority / 参照優先順位

現行仕様の優先順位は次の通り。

1. **`main` の実行コード・テスト・GitHub Actions**
2. **本ファイル `AI_Intelligence_Factory_最終仕様書.md`**
3. `PAID_PRODUCT_CONTRACT.md`
4. `NOTION_ACCESS_POLICY.md`、`GEMINI_QUOTA_SETUP.md` 等の領域別Operator契約
5. `docs/reference/`
6. `docs/audits/`
7. `docs/archive/`、過去Run追補、Git履歴

原則:

- 本書とコードが矛盾する場合は **`main` が正**。
- Run番号は履歴識別子であり、現行仕様のAuthorityではない。
- Recovery専用・診断専用・固定ID専用の過去surfaceを、文書だけを根拠にProductionへ戻さない。
- Evidence / Fact / Publication / Reader / Note / Eyecatch のFail-Closed契約を文書整理の都合で弱めない。
- Productionの意味が変わる変更は本書の本文も同じ変更単位で同期する。
- Productionの意味が変わらない内部修正でも、Production surfaceが変わった場合はProduction最終照合日とProduction Contract Fingerprintを同期し、現行仕様と矛盾しないことを証明する。

---

## 1. Factoryの目的とProduct Architecture

AIIFは「ニュース自動要約機」ではない。

目的は、海外AI / Techの一次情報を、

**収集 → 重複排除 → Evidence確認 → Deep Dive → エンティティ統合 → 既存評価更新 → 記事化 → 意思決定資産化**

まで一貫して処理し、読者と会員が「何が変わったか」「使えるか」「何をするか」を短時間で判断できる状態へ変換すること。

### 1.1 無料面

- note無料記事
- X等の集客導線
- 検索・SNS流入
- Human Narrativeによる理解・読了
- 一次情報とEvidenceへの導線

無料記事自体を品質の低いティザーにしない。無料面も信頼形成の商品入口として完成品質を要求する。

### 1.2 有料面

有料商品は **Use-Decision Intelligence**。

中心価値:

> **「このAI、使える！」を、根拠付きで判断できる。**

主要構成:

1. Decision Brief
2. Technology / Decision Intelligence DB
3. Evidence / リスク / 利用条件
4. Decision History
5. 次のActionへ落とす判断メモ

現行標準価格は **月額1,980円**。noteは販売チャネルの一つであり、Factoryそのものではない。

---

## 2. Production Execution Contract

### 2.1 Scheduled Daily

Scheduled Dailyは **PAUSED**。

- `.github/workflows/daily.yml` はhard-disabled。
- cronを持たない。
- workflow_dispatchされてもProductionを動かさない。
- 自動Dailyを勝手に復活させない。

Production Dailyは **Manual ONE-SHOT** が正規経路。

### 2.2 Manual ONE-SHOT

正本Workflow:

- `.github/workflows/daily-one-shot.yml`

明示確認:

- `confirm=RUN_ONCE`

現行モード:

- `full`
- `article_validation`
- `pending_retry_validation`
- `ready_rescue_validation`
- `production_e2e_validation`
- `stale_ready_batch_revalidation`
- `local_skills_canary_validation`
- `local_skills_production_validation`

未知modeはProduction初期化前にFail-Closed。

### 2.3 ChatOps

通常のProduction発火は専用Control Issue経由の `AIIF ChatOps ONE-SHOT Bridge` を使える。代表コマンド:

- `/aiif run full`
- `/aiif run article_validation`
- `/aiif run pending_retry_validation`
- `/aiif run ready_rescue_validation`
- `/aiif run production_e2e_validation`
- `/aiif run production_e2e_preflight`
- `/aiif run local_skills_canary_validation`
- `/aiif run local_skills_production_validation`
- `/aiif run v2_shadow_deep_dive`
- `/aiif note sync`
- `/aiif note sync <32-hex sync_id>`
- `/aiif note audit <32-hex sync_id>`
- `/aiif note regenerate <32-hex sync_id>`
- `/aiif note regenerate_resume <32-hex sync_id>`
- `/aiif ready asset_recovery <32-hex sync_id>`

Control Issue、owner、run_attempt等を認証し、GH_PATで既存manual workflowを1回だけdispatchする。Bridge自身がProduction処理を直接実行しない。exact target commandは32-hex identityを厳格に要求し、別記事へfallbackしない。

`/aiif run v2_shadow_deep_dive` は `.github/workflows/v2-shadow-deep-dive.yml` だけを明示dispatchするV2診断経路であり、V1 Production authorityを変更しない。Notion / note / Ready / publication / delivery ledgerへのProduction mutationを行わず、診断artifactだけを生成する。

`/aiif note audit <32-hex sync_id>` は既存private draftのread-only監査専用で、`.github/workflows/note-private-draft-audit.yml` だけをexact targetへdispatchする。Bridge自身のGemini/model call、draft mutation、Production実行、public releaseはすべて0 / falseとし、監査対象を別記事へfallbackしない。同一Issue commentの再配送・重複eventは、そのcomment IDへのdurable claimをdispatch前に確認し、同じcommentから監査workflowを二重dispatchしない。

exact private-draft auditは、stable edit routeを直接開けることだけを実在証明にしない。まず同一persistent Chrome sessionで認証済み `https://note.com/settings/profile` を開き、creator名がexact `AIF - AI Intelligence Factory` であること、かつ同settings page内のlinkがexact `https://note.com/trendhub_biz` profileを指すことの両方でaccount ownershipをread-only証明する。public profile上の可視 `設定` controlには依存しない。次に同じopaque `note下書きID` が認証済みsessionの公式 `https://note.com/notes` 一覧へ存在することを確認する。これらを満たした後だけdirect editor routeでtitle / body / eyecatchを監査し、account ownershipまたはofficial-list proofが不成立ならFail-Closedする。

`/aiif run full` は現行運用上 **`human_narrative`** を明示してDaily ONE-SHOTへ渡す。

既存Ready下書きの再生成は `.github/workflows/ready-draft-regenerate-once.yml` を正規ONE-SHOTとする。

- `regenerate`: 現行Productionでexact targetを再生成し、現行Gate通過後に同じprivate draftへ反映する。
- `resume_persisted`: 既に現行Content IntelligenceへReadyとしてpersist済みのexact targetだけを、Provider生成なしで同じprivate draftへ反映する。
- どちらも新規draft作成とpublic releaseを禁止する。

Ready asset persistence障害の限定Recoveryは `.github/workflows/ready-asset-recovery-once.yml` を使い、ChatOpsは `.github/workflows/chatops-ready-asset-recovery.yml` からexact targetだけをdispatchする。

### 2.4 Editorial Style

ONE-SHOTが受理するStyle:

- `classic`
- `human_narrative`
- `duo_narrative`
- `v3_p5`（手動選択時のみ、LocalSkills + 凍結P5 Writerの表現方針）

未知StyleはFail-Closed。`duo_narrative` はフェルン／クレハを使う任意Styleであり、通常のFull Dailyでは自動選択しない。ONE-SHOTのdefaultは従来どおり `classic` で、`v3_p5` は自動選択されない。 `v3_p5` は記事を正式公開する前の検証モードに限定し、本来の五段階生成を追加Deep Dive callで実行する。

### 2.5 Production Entry Point

正本entrypoint:

- `production_pipeline.py`

runtime layer順序の正本:

- `runtime_layers.py`

個別Run moduleからProductionを迂回起動しない。

---

## 3. Intelligence Source Contract

### 3.1 必須4 Source

Fresh acquisitionのProductionポートフォリオは次の4系統。

1. **GitHub** — 実装・OSS動向
2. **HackerNews** — 市場・開発者反応と発見
3. **ArXiv** — 研究・先行技術
4. **OfficialVendor** — ベンダー一次情報

現行ONE-SHOTの基本取得上限は各Source **50件**、Screening最大 **200候補**。

### 3.2 X

Xは **任意Discovery origin**。

- `full` のときだけX discoveryを有効化できる。
- ProductionのApify Actor正本は **Xquik `xquik~x-tweet-scraper`**。ONE-SHOT workflowとruntimeの双方をこのActorへ固定する。
- 監視対象は固定watchlistの **20 unique handles**。1回のbounded Actor runで取得し、上限は **100件 / 1 profileあたり5件 / 直近12時間** とする。
- Actor inputは `twitterHandles` + `mode=profileTweets` を使い、出力は `rich / camelCase / flat` に固定する。
- Apifyのrun-level charge capは **`APIFY_MAX_CHARGE_USD=0.05`** を維持する。X discoveryのために無制限のprofile別runを行わない。
- Xquikのdiagnostic rowはSignalへ昇格させない。`zero-output` は直近windowに該当投稿がない正常なempty profileとして数え、provider errorにはしない。それ以外のdiagnosticはprovider errorとして記録する。
- 旧 `simple.actor~x-profile-posts` はProduction正本ではない。移行中のstale runtime overrideだけはXquikへ安全に読み替え、新規workflowでは使用しない。
- X投稿本文そのものをEvidenceにしない。
- 技術的Factはリンク先一次情報で確認する。
- 必須4 Sourceの配分をXで置換しない。
- Publication Source上は `X（一次情報への発見経路）` と明示する。
- X / Apify障害で必須4 Source Dailyを停止させない。

### 3.3 Product Hunt

**Product Huntはactive Production Sourceではない。** 旧enumやhistorical artifactに残っていても、Fresh取得・Publication Source・現行商品価値の必須Sourceへ戻さない。

### 3.4 OfficialVendor

OfficialVendorはベンダーごとにSource枠を分裂させない。Vendor / regionはmetadataで識別する。

同一release-note pageが更新される場合、`aif_revision` をContent Event identityとして使用できる。安定したbase URLはEvidence / Technology identity側の情報として保持し、イベント重複判定と混同しない。

---

## 4. Provider / Gemini Routing / Cost Contract

### 4.1 Screening

現行Full ONE-SHOTのScreening候補:

- `gemini-3.5-flash-lite`
- `gemini-3.1-flash-lite`

Persistent daily budget:

- 3.5 Flash-Lite: 450
- 3.1 Flash-Lite: 450

Screeningは大量候補の低コスト選別を担当し、記事本文の最終品質を担わない。Lite laneからFull Flash laneへScreening fallbackしない。

#### 4.1.1 V2 Shadow Semantic Screening / Evidence Variable Fallback

System V2のprovider-backed shadow deep diveは **診断専用** であり、V1 Production authorityを変更しない。明示的なmanual one-shotでのみ、次のbounded sequenceを実行できる。

1. deterministic / provider-free cheap screening
2. cheap screeningを通過した候補のうち最大20件を1 batchでSemantic Screeningへ送る
3. Semantic ScreeningはV1と同じLite lane、`gemini-3.5-flash-lite` / `gemini-3.1-flash-lite` をProvider Healthで並べ替え、provider / transport / contract failure時だけ次のdistinct modelへfallbackする。最大2 model requests
4. Semantic laneが全滅した場合は既存deterministic rankingへ縮退し、Evidenceを阻害しない
5. Semantic結果はSelection Valueを補助し、deterministicに再rankingする
6. rank-1候補だけをEvidenceへ送り、V1と同じFull Flash lane、`gemini-3.6-flash` / `gemini-3.5-flash` / `gemini-3.7-flash` / `gemini-3.8-flash` / `gemini-3-flash-preview` をProvider Healthで並べ替え、provider / transport / contract failure時だけ次のdistinct modelへfallbackする。最大5 model requests
7. 有効なEvidence判定が返った時点で停止する。`evidence_sufficient=false` も正常な判定であり、別modelへ送って判定を覆さない。rank-2 rescueもしない
8. Evidence laneが全滅した場合だけwinnerなしでFail-Closedする

1回のV2 provider-backed shadow runで許可するmodel HTTP attemptは **最大7回（Lite最大2 + Flash Evidence最大5）**。正常時はSemantic 1回 + Evidence 1回の **2回** で終了する。同一modelへのretryは行わず、distinct-model fallbackだけを許可する。400 / 401 / 403等、modelを変えても解消しない共有設定・認証系errorでは無駄なfallbackを打ち切る。

Semantic Screeningは4つのboolean（AI relevance / decision value / change novelty / applied reader value）だけをstrict JSON contractで返し、結果は **rescue / upside-only** としてdeterministic Selection Valueを下げない。同一batchの全候補を検証してから加点・診断値を一括反映し、1候補でも契約不正なら一部加点を残さずdeterministic rankingへ完全縮退する。raw Gemini response / prompt / secretをartifactへ保存しない。

V2のRequired 4 Source（OfficialVendor / GitHub / HackerNews / ArXiv）のlive acquisitionは、外部HTTPの一時障害をSource固有の場当たり的処理ではなく共通のbounded reliability契約で扱う。通常は1 GETで終了し、`timeout` / `connection` / HTTP 429 / HTTP 5xxだけ同一logical readを最大1回retryする。429以外の4xx、invalid JSON/XML等の非transient failureはretryしない。1 Source familyの失敗で他Source familyを停止させず、OfficialVendorの複数vendor、GitHubの複数repository等の既存冗長性も維持する。Artifactへはattempt count、retry有無、safe failure category等の診断だけを残し、URL query、raw response、secretを保存しない。既存live readerの公開error category互換は維持し、`http_5xx` 等の詳細分類はdiagnostics側のauthorityとする。

Semantic Screeningの識別性能は、provider-freeのGold-label benchmarkで回帰評価できる。Gold labelは人間が固定し、モデル出力で正解ラベルを書き換えない。4 boolean dimensionごとにTP / FP / FN / TN、Precision / Recall / F1を計算し、macro指標、exact-match、all-positive saturation率も出力する。CIのGold benchmarkはGeminiを呼ばず、同じGold corpusと予測JSONを使うoffline evaluator / CLIだけを検証する。したがってPromptやmodel routingを変更しても、同一正解セット上で性能差を比較できる。

V2はV1のProvider Health履歴とlane rankingを **read-only** で参照する。V2自身はhealth historyを書き換えず、Provider障害を記事品質FAILへ混同しない。

このV2 shadow laneはNotion / note / Ready / publication / delivery ledgerを更新せず、`production_mutation_authorized=false` を維持する。V2結果だけでProductionへ昇格・公開しない。

### 4.2 Deep Dive / Article Models

現行Full ONE-SHOTの明示allowlist:

- `gemini-3.7-flash`
- `gemini-3.8-flash`
- `gemini-3.6-flash`
- `gemini-3.5-flash`
- `gemini-3-flash-preview`

モデル別persistent daily budgetは各18。

公開用記事の初稿・Human Narrative / Quality RetryはFull Flash系のみを候補にする。Flash-Lite系はScreening、分類、Evidence整理、JSON抽出等の非公開補助処理に限る。上位Writer候補が503、timeout、quota等で利用不能なら記事をReadyへ進めず、Pending Retry等の非Ready状態で止め、note下書きへ配送しない。

通常Deep Diveは `thinking_level=low`、Quality Retryは `medium`。本文の `max_output_tokens` は `GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS`（既定9000）。Deep Dive run budgetは **12 provider-visible requests** を上限とする。

### 4.3 Health-aware routing

Article routingは固定順だけで決めない。

- 24時間のProvider実績を優先
- sparse時は直近20 attemptまで補完
- recency half-lifeは3時間
- successは順位を上げる
- 503 / timeout / errorは順位を下げる
- run-local unavailable / exhausted circuitを尊重
- health stateは記事本文やpromptを保存しない
- health stateのread/write失敗は記事生成自体を止めない

履歴が同条件なら、Routerのcold-start tie-breakは概ね **3.6 → 3.5 → 3.7 → 3.8 → 3 Flash Preview**。ただし実際のmodel setはWorkflow allowlistとquota状態を優先する。

V2 provider-backed shadowも同じProvider Health履歴とlane rankingをread-only参照するが、V2自身はhealth stateを書き換えない。

### 4.4 503 / Retry ownership

google-genai SDK内部のtransient retryはProductionで無効化し、**Factoryを唯一のretry owner** とする。

provider-verified 503では同一modelへ無駄な再送を重ねず次のdistinct modelへ進む。Quality repairは最大 **2 distinct models**。429 / RPD / RPM / timeout / 404は既存quota・circuit契約に従い、無制限retryしない。

V2 provider-backed shadowでも同一model retryは行わず、各lane内のdistinct-model fallbackだけを許可する。Semantic lane全滅時はdeterministicへ縮退し、Evidence lane全滅時だけwinnerなしでFail-Closedする。

### 4.5 Product Review

Product Reviewは記事Deep Dive内に混在させない。Full Dailyでは:

- main Production中の `PRODUCT_REVIEW_MAX_PER_RUN=0`
- 旧bootstrapも0
- 後段の **Portfolio-aware Product Review** を専用passとして1回実行
- review max: 2
- request budget: 3

Product Review runtimeは記事Publication / Reader / Eyecatch layersを持たず、Provider / quota safetyだけを使う。

---

## 5. Candidate Identity / Dedupe / Existing-Article Admission

### 5.1 URL dedupe

`candidate_identity.py` が保守的にcanonicalizeする。除外してよいもの:

- `utm_*`
- `fbclid`
- `gclid`
- `ref`
- `source`
- default port
- presentation-level trailing slash差

ArXivは `abs/pdf/version/.pdf` の差を同一paper IDへcanonicalizeする。意味のあるpath/queryを勝手に消さない。

### 5.2 Content EventとEvidence identityを分離

OfficialVendorのpage-level revisionは、revision付きURLを **Content Event key** とする。stable primary URLまで同一dedupe集合へ混ぜて、後続revisionを旧イベント扱いにしない。

同じTechnologyでも、materially new Eventまたは新しいOfficialVendor `aif_revision` は新しいArticle候補になり得る。Technology identityはgrouping metadataであり、過去Articleを永久blockするIDではない。

### 5.3 Technology Entity Resolution

Technology IntelligenceのEntity Resolutionは **保守的** に行う。

優先:

1. 明示的GitHub owner/repo
2. arXiv paper ID
3. root-likeな公式 / 外部project URL
4. それ以外はAMBIGUOUS / legacy ID

禁止:

- fuzzy titleだけでTechnologyをmerge
- UNBOUND Evidence URLをidentity aliasへ昇格
- GitHubのcollections / enterprise / solutions等のglobal navigationをrepo entity扱い
- 発見記事の深いURLを自動的にdurable Technology identityへ昇格

Evidence URLがidentityに寄与できるのは、`IDENTITY_ANCHOR` 等の明示的なbound stateを持つ場合に限る。

### 5.4 Published Terminal / automatic regeneration

既存Articleの自動再生成は `automatic_regeneration_decision()` の共通契約に従う。

許可:

- delivery stateが正に `not_queued` または `waiting` と証明できる場合のみ

Fail-Closed:

- delivery authority未設定 / 読取不能
- empty / malformed / ambiguous state
- `投稿準備中` / `投稿済み` 等のdelivery-started state
- `保留` / `取下げ` 等のhuman-blocked state
- published evidenceがある既存article

Ready Rescue / existing editorial recovery / Pending RetryはProvider予算を使う前にこの契約を通す。Freshの新規candidate acquisitionはこの既存Article terminal contractで塞がない。個別記事IDやタイトルのblacklistで再発防止しない。

---

## 6. Article Generation — A+ Local Skills Editorial Orchestration

### 6.1 基本思想

現行Productionは **Gemini + Local Skills A+**。

役割分担:

- **Local Skills**: pre-write skeleton、Evidence boundary、deterministic canonicalization、provider-free safe fallback
- **Gemini**: 人間らしい文章、リズム、引力、比喩、表現
- **Gates / deterministic logic**: Fact / Evidence / Reader / Publicationの最終制御

Local SkillsはGeminiを全面置換するのではなく、Geminiの表現力を安全な構造の中で使う。

### 6.2 A+ Pre-Write Contract

Gemini Writer call前にLocal Skillsが次を固定する。

- MANAGEMENT DATAの意味を先に確定
- 「何が変わったか → 判断との関係 → 必要条件 → 制約/反証 → Action」の骨格
- 専門語初出時の平易説明
- DecisionとActionの意味整合
- 歴史・事件・研究・制度等を無理に「導入」記事へ変換しない
- required qualifiersを削除しない
- Evidence不足を物語性で補わない

A+導入のために追加Provider callを要求しない。

### 6.2c Gemini共通永続利用回数台帳（runtime-state、2026-10-25）

- GitHub `main`の必須PR・CI保護を変更せず、Gemini永続Counterは既存の書込可能ブランチ`runtime-state`、正本パス`.runtime/gemini_daily_usage.json`に統一する。既存`article-revalidation-apply.yml`の運用ブランチを全モデル使用ワークフローに展開し、mainの古い2026-09-02台帳を正本へ戻さない。
- Daily ONE-SHOT／P5 A–E／Inventory／Issue 668/683/698再検証／Ready再生成・アイキャッチ・Recovery／実記事Regressionはすべて同じ保存先とrepository scopeを共有する。GH_PATによるContents APIのCAS `sha`、HTTP 409競合時の再読込、provider送信前の予約、model別・Run別上限、共通Gemini concurrency lockを維持する。
- `runtime-state`への試験書込・再読込は利用回数0件で成功（commit `a3c5ff91f910887c3138369dc406332cd4e9adda`）。初回実呼び出し時はAmerica/Los_Angeles日付に合わせて既存Counterが日次正規化される。手動AI Studioなどrepository外の呼び出しはカウント対象外であり、Google providerのquotaを保証するものではない。
- `issue668-stage2-live-rerun.yml`はmainへのpush連動による意図しない実API再発火を防ぐため`workflow_dispatch`専用とし、主担当者による明示起動を要する。既存のモデル選択やEvidence/Fact/Publication Gateは変更しない。
- Counter書込エラー時にはGemini呼び出し前にfail closedする。counter無効化・保護mainへの書込再導入・run専用別台帳・同時実行制限解除は認めない。
- **2026-10-26 Flash実モデル上限統合（PR #878）**: 3.5→3.6、3.7→3.8の旧名称と現行名称はそれぞれ同一の実モデル上限（最大18回／America/Los_Angeles日）として使用回数を合算する。旧名称の履歴・by_kindは破壊せず、既存`runtime-state:.runtime/gemini_daily_usage.json`・repository scope・GitHub CAS 409再評価を正本とする。Flash-Liteは別枠。Nextからも同じリポジトリの同一scopeへ送信前に予約する。別リポジトリのActions tokenは自動的にはV1の書込権限を持たないため、Nextでは専用の最小権限tokenを別途設定し、未設定やCAS失敗は送信前にfail closedする。Google AI Studio手動利用はこの台帳の観測対象外。

### 6.2b P5 A–E原因切り分け ChatOps（2026-10-24、未昇格の実験）

- P5 A/B/C/D/Eの比較試験は、既存Control Issue #71への完全一致コマンド `/aiif run p5_ablation_once` から起動できる。ただしコマンドは`chatops-one-shot.yml`が`main`上で承認済みの場合に限る。運用中のDaily/Classic/V1/V2を変更しない。
- 専用 `p5-creative-ablation-manual.yml` は `workflow_dispatch` のみ、本人`trendhub-ab`、`github.run_attempt == 1`、共有Gemini concurrency lock、元記事を固定し、5原稿について実験固有の累計8回上限を設けず、各アーム最大3回の構造化エラー再試行と既存の永続Gemini日次Safety Capで制御する。A/C/Eの第1選択は`gemini-3.8-flash`、B/Dの第1選択は`gemini-3.6-flash`。3.8の構造化された404/429/503に対して3.6への切替を1回許可し、3.6の構造化された429/503についても同一モデルで最大2回の追加試行を許可する。90秒・180秒の待機、各案の最大3試行および共有Geminiの永続日次Safety Capを守る。非構造化エラー、JSON不正、品質不良、権限エラーは再試行せずFail-Closed。実験本体はレビュー済みの固定commit `9e76864d2d3d31facae881a05356b941e3cc9fe3`（PR #874の暗号化保存修正を含む実験コード）をcheckoutし、別branchの最新HEADを自動追随しない。旧pin `922ef5b49b76683529957d37ead155d459e886dc` はフォールバック非対応のため本実験には使用しない。ChatOps実行記録に表示するpinもcheckout実値へ一致させる。旧8回計測済みのRun #40178724927の暗号化チェックポイントは、公開ゲートを緩和せずEのみ再開できる。既存のRun #40181099067はGemini追加送信0回で事前拒否したため新正本にしない。Run #40185716168ではE生成とJSON検証が成功したが、旧暗号化保存ゲートの8回上限により新規artifactなしで失敗した。PR #874で暗号化保存の残存上限を撤廃し、E再開時の10回累計も暗号化保存できることをprovider-freeテストで確認する。新たな自動発火条件は導入しない。
- 公開GitHub Actionsに原稿を平文保存することは禁止。既存Telegramの受信先をbot APIで`private`チャットと検証した後だけAPI実行する。原稿/5工程/ブラインド対応表はRunnerの私用一時領域でFernet暗号化し、公開Actionsには暗号文だけを7日間保存。復号鍵は別経路の検証済みprivate Telegramに通知する。失敗時も完成済みの案が1本以上あればINCOMPLETE_TECHNICAL_NO_GOの暗号化途中成果を保存し、ブラインド対応表を維持する。前回FAILED P5 Run IDを任意指定して再開する場合、Telegramで受領した鍵をActionsリポジトリSecret `P5_RESUME_FERNET_KEY`に登録することを必須とし、鍵をworkflow_dispatch入力・Issue・ログに書いてはならない。再開時は旧RunからGemini試行数を引き継いで監査記録に残す一方、累計試行数のみでは拒否せず、保存済み案を再生成しない。過去の未暗号化失敗Runは復旧できない。グループ/チャンネル、欠落した認証情報、API quota不足、暗号化・鍵配送失敗はFail-Closed。復号鍵・未公開原稿をIssue、PR、Actions logsに載せない。
- CI GREENは記事品質の人間評価ではない。混在モデルの各原稿で実際に使用したモデルと切替実績はブラインド評価後の非公開照合ファイルだけに記録する。今回のA–E間の品質差はモデルと条件の交絡があるため、因果的なプロンプト効果と断定しない。原稿は本番Note/Notionへ一切自動配送せず、既存Evidence/Fact/Publication Gatesは保持する。
- 実験PR #863の原稿生成系はDraft・未マージ。起動PR #864は2026-10-24にmainへマージ済みだが、オーナー本人の明示コマンドがない限りP5 API実行を開始しない。固定pinの追従修正PR #867は2026-10-25にmainへマージ済み。混在モデル実験コードPR #868のレビュー済み固定commitを参照した起動PR #869は2026-10-25にmainへマージ済み。再開機能改修PR #870と今回の新固定pin・非公開チェックポイント対応PRは本番品質ゲートの昇格ではなく独立した事前レビュー対象とし、正式MERGE GOなしにmainへマージしない。ChatOps拡張は実験の明示的入口に限り、本番原稿生成契約の書換えではない。

### 6.2a V3 P5 original five-stage Writer（2026-10-24 統合開発候補）

- **唯一のP5正本はPR #852（commit `95016a65701979063f56130bf181bca831661f5d`）**。本リビジョンでは廃止された派生案を開発判断に使用しない。`local_skills/v3_p5_contract.py` / `local_skills/v3_p5_prompts.py` はそのP5原稿・五段階束プロンプトを移植し、比較基準として保持する。P5の今後の改善自体は凍結しない。
- `AIIF_EDITORIAL_STYLE=v3_p5` を明示選択した時だけ、既存LocalSkills A+ Pre-Writeの後に、**Writer Reaction → Editorial Discovery → Cognitive Shift → Persona Article Generation → Fact-Safe Review** をP5本来のJSON成果物5キーで生成する。五段階は一つのGemini Deep Dive callで実施する。
- **Productionは計2回のDeep Dive callが必要**。第1回で従来のMANAGEMENT DATA / Decision / Actionを生成。第2回で一次Source Native Context / Structured Evidence / LocalSkills制約 / 第1回のDecisionを入力としてP5の五段階束を生成し、Fact-Safe Reviewの全文をcanonical ARTICLEへ置換する。既存のMANAGEMENT DATA / Gate Thresholdsは変更しない。追加callも既存model pool・実行予算・プロバイダ安全機構の対象とし、別API権限やバックドアを持たせない。
- 不完全なP5 JSON、5段階欠落、未検証の一次Source、空の最終稿、違反する文章、モデルエラーは**Fail-Closed**。第1回の説明原稿へ黙ってfallbackせず、Gateを迂回しない。
- 既存の二層構成は変えない。前半の「どんな内容？／なぜ重要？／結論は？／元情報」はProducer組み立てで一度だけ表示。後半はP5ライター本文。記事末尾の「Sources / Evidence」および主一次情報の重複出典表示はオーナーの決定に従い維持する。
- ONE-SHOTのデフォルトは従来どおり `classic`。`v3_p5` は**現段階では検証モード限定**とし、Full Dailyでの公開・下書き配送はオーナーの品質確認／MERGE GOまで許可しない。実記事で主観90点達成はまだ証明されていない。記事の品質・Fact/Reader/Publication Gateを実測評価する。

### 6.3 Provider-free fallback

Local fallbackは何でも生成してよい逃げ道ではない。使用条件:

- structured MANAGEMENT DATAが完成済み
- Evidence stateがSUFFICIENT
- Decision scopeがsafe
- Fact / Evidence / Source / Grounding系の失敗が残っていない
- Quality Retry文脈でProviderが利用不能、またはretry policyがlocal fallbackを許可

Fact不足をLocal Writerで埋めない。

### 6.4 Local Skills validation modes

`local_skills_canary_validation`:

- measurement-only
- downstream note syncなし
- Productionへ勝手に書き込まない

`local_skills_production_validation`:

- bounded Production persistence validation
- Gemini送信は最大1回の検証境界
- article / Ready stateは検証可能
- このstageではdownstream note synchronizationを禁止

### 6.5 Human Narrative / Naturalness

`human_narrative` は事実を脚色するStyleではない。

許容:

- 読者が場面を想像できる導入
- 軽い比喩
- 現実的なツッコミ
- 技術と仕事の距離を縮める表現

禁止:

- 架空の体験談 / 架空の会話をFact扱い
- Evidenceにない因果
- 誇張された断定
- 同じ会社員ネタ等のテンプレ使い回し

Source-specific Hookを優先し、一次情報固有の数字・出来事・矛盾・制約へ早く接続する。Generic business proseや過剰な煽り、抽象的な大団円等のNaturalness signalはQuality Retryの具体的feedbackに使えるが、それ自体でHard GateやReady閾値を増やさない。

---

## 7. Article / Reader / Gate Contract

品質目標は「Gateを通す」ことではなく、**理解でき、面白く、判断に使える完成稿**。

現行の重要Gate群:

- Source Boundary
- Evidence Sufficiency
- Fact / Numeric Evidence
- Technical Claim Precision
- Scope Fidelity
- Japanese Surface Integrity
- Editorial Naturalness
- Human Appeal / Reader Value
- Reader Repair
- Publication Readiness
- Final Publication Surface
- Publication Contract

Human Appealの中核品質が `WEAK` の原稿は最大1回のQuality Retry。Retry後も `WEAK` ならNeeds Editorial Review等の非Readyへ送り、note下書き配送を禁止する。軽微な表面表現だけのSOFT warningは、Human AppealがACCEPTABLEなら警告付きReadyを許可できる。

### 7.1 Fail-Closed

以下は文章力で救済しない。

- 根拠不足
- Entity不一致
- unsupported numeric claim
- 主体帰属不明
- source boundary違反
- public title / body不整合
- stale policy
- final surface破損
- `【ARTICLE】` / `MANAGEMENT DATA` / `NOTE_DRAFT_START/END` 等の内部制御マーカー漏洩

### 7.2 Reader-first public format

現行Public manuscriptは記事固有のNarrative Leadを保持した上で、主要見出しを次に統一する。

- **どんな内容？**
- **なぜ重要？**
- **結論は？**
- **元情報**

「何が出た？」の重複labelは使わない。元情報には主一次情報と発見経路を表示する。未知の技術・製品・略語は初出で非専門読者に役割が分かる日本語へ橋渡しする。

### 7.3 Decision語彙

NOW / TRY / WATCH / WAIT / AVOIDをそのままpublic本文へ漏らさない。歴史・研究・事件・制度・ベンチマーク等を無理に「導入する／しない」へ翻訳せず、対象に合うAction（確認、比較、検証、追跡、基準点化等）を使う。

---

## 8. Publication / Ready Contract

Readyは単なるSelect値ではない。現行Ready blockは少なくとも次を証明する。

- Publication Contract ID
- Editorial Style
- current policy SHA
- manuscript SHA-256

`publication_contract.py` のsemantic policy fingerprintはPublic bytesへ影響するcode群から自動計算する。

したがって:

- policy codeが変われば過去Readyがstaleになることがある
- staleは正常
- property上Readyだからといって現行Readyとは限らない
- body SHA不一致をcurrent Readyとして扱わない
- provenanceを偽装してReadyを維持しない

### 8.1 Single canonical manuscript persistence

Content Intelligence pageがReadyとしてcommitされた後、そのページのmanuscript blockは **byte-exact current canonical body 1本だけ** に収束させる。

- 元のtwo-phase Notion transaction / rollback契約は維持する
- current exact manuscriptが存在することを確認してからstale / legacy / duplicate blockをclean upする
- Notion rich_text segmentationはtransport-onlyで、join後のmanuscript bytesを変えない
- cleanup後にfresh readbackし、残存blockが1本かつexact current bodyであることを証明する
- readback / cleanup / exact-body proofに失敗した場合はReadyを維持せず **Pending RetryへFail-Closed**

古い原稿を監査目的で同じReady page本文内へ残す運用は禁止する。履歴はGit/監査資産等で保持し、current Ready本文と混在させない。

### 8.2 Visual-only repair

Article policyがstaleでも、過去本文がReady caption family・正しいmanuscript SHA・exact title一致を満たす場合、**visual-only repair** のためだけにbyte-authenticated本文を利用できる。

この経路はarticle bodyをrestampせず、titleを変えず、article regenerationせず、public releaseせず、現行Eyecatch Contractだけを更新する。

### 8.3 Exact Ready Asset Persistence Recovery

通常のrecent-row scanで届かない、またはeyecatch asset persistenceでReady化に失敗したexact articleには限定Recovery laneを使える。

- exact 32-hex Content Intelligence page IDをdirect GETする
- Fresh acquisition / recent-row scanを使わない
- Provider call前にPublished Terminal / delivery authorityを確認する
- same Content Intelligence pageへ `persist_results=True` で現行Production article stackを通す
- truthy manuscript返却だけを成功とみなさない
- generation後に同じpageをfresh readし、`Article Status=Ready` を証明できた場合だけ成功
- Ready proof後だけ `note-ready-sync.yml` をdispatch可能
- new draft / public releaseは禁止

---

## 9. Eyecatch Publication Contract

Eyecatchは単なるPNGではない。Public titleと現行rendering policyにbindされたasset。

### 9.1 Geometry / Format

最終asset必須:

- PNG
- RGB
- **1280 × 670**
- Noto Sans JP production font
- 日本語fontがない場合はFail-Closed

### 9.2 Approved Eyecatch V2 master

現行Editorial V2は、ユーザー承認済みの **白背景・右側に青いガラス調AIコア** のrasterをimmutable visual sourceとする。synthetic redrawで置換しない。

Background master:

- source: 1536 × 804
- production master: 1280 × 670 WEBP
- cropなしのstraight downscale
- 6個のBase64 text partsから復元
- SHA-256: `5f1ab5f8ddc807825ad8fa29fdb96b5a165742af73b779223b7fccf8547a77fd`
- decode / format / size / SHA mismatchはFail-Closed
- Run551追加Provider call: 0

上部構成:

**brand → dynamic reader-purpose badge → editorial hook → validated title → footer**

主要geometry / typography:

- left 48
- badge top 140 / height 44 / font 24
- hook top 204 / font 33
- title top 310
- lead title font 74 / left 45
- impact title font 85 / left 42
- title line gap 8
- footer top 592 / font 19
- brand font 32

### 9.3 Headline integrity

保存PNGには以下を埋め込む。

- public title SHA
- approved expected headline
- actual rendered headline
- glyph pixel proof

検査時に:

- expected / renderedが空でない
- expectedとrenderedが空白除外で完全一致
- glyph pixel proofが実画像と一致
- 画像外へ文字がはみ出さない
- `...` / `…` を含まない
- headlineが不完全な日本語文節で終わらない

を要求する。

不完全終端の代表例:

- `は、`
- `が、`
- `けれど、`
- `しかし、`

Run248のemphasis repairも、完全なupstream titleを上記のような意味未完の短縮headlineへ変えてはならない。Run248 quality calibrationはEyecatch policy hashの対象であり、保存前と保存済みPNG検証の双方で不完全文節をFail-Closedにする。

### 9.4 Japanese line-break integrity

Headlineは原則1〜3行。禁止例:

- `新し｜い`
- `管｜理者`
- `エー｜ジェント`
- `Chat｜GPT`

保護する単位:

- 漢字複合語 + 送り仮名
- カタカナ語
- 英数字product / model token
- 明示的空白境界

収まらない場合は自然な意味境界へ改行 → 3行化 → 許容範囲内font縮小を優先し、語中改行や省略記号で無理に収めない。

Eyecatch semantic layout Providerは補助処理としてbounded:

- `gemini-3.6-flash` → `gemini-3.5-flash` の順で各1回
- 各Provider sendは30秒watchdog
- watchdog不可ならProviderを呼ばずFail-Closed
- 503 / timeout / invalid layoutは次Providerまたはdeterministic layoutへfallback
- layout待機がDaily全体timeoutを占有することを禁止

### 9.4a V1 semantic eyecatch copy / optional encrypted run-crossing cache

V1 semantic layoutがvalidな完成コピーを作成してレンダリングまで成功した場合、同一inputでの再実行はprovider-free copyを優先する。通常Productionのpublic eyecatch call-siteはNotion本文と同じ `build_clean_note_manuscript(...)` 結果の `clean_manuscript` を `article_text` として渡す。ローカルおよび遠隔暗号化copy cacheのfingerprintは公開タイトル・要約・**最終確定本文の全バイト相当のUTF-8テキスト**を含み、本文の末尾だけが更新されてもcache missとする。モデルへの実際の本文excerptは既存のbounded prompt範囲に留め、Gemini callの回数やReady Gateを変更しない。

- ローカル `.copy.json` はrun内の一時保存に限定し、Gitへcommitしない。
- public repositoryの `runtime-state` にcopy/記事タイトル/要約/本文をplaintextで保存しない。
- optional遠隔保存は `eyecatch_copy_runtime_store.py` のFernet認証暗号で封印したrecordのみ。pathも秘密鍵によるHMACで匿名化する。
- `AIIF_EYECATCH_COPY_FERNET_KEY` が未設定/不正、Actions tokenが権限不足、branchが `runtime-state` 以外の場合、遠隔cacheを無効化する。GitHub Actions secretに安定したFernet鍵を登録するまでrun跨ぎの再利用は有効にならない。
- Contents API取得時のsource digest不一致、復号不能、status!=200/404はcache miss扱いとし、valid layout以外を再利用しない。
- 409競合時は既存recordを再読込し、blind overwriteしない。403等の権限障害はcacheを保存せず、元のPublication / Eyecatch fail-closed gateは弱めない。
- 追加Gemini callは0。V2のapproved master、note配送、Notionは変更しない。
- 実記事Run #39543411060で検出された `article_text` 引数のラッパー拒否をRun248（最終公開視覚品質ラッパー）とRun296（画像ラッパーとsemantic prompt）で修正し、確定本文をRun180へ透過的に引き渡す。Run296の承認済みGenRec例外画像は変更しない。追加モデル呼出し・品質Gate緩和なし。これはprovider-freeコード結線の保証であり、実記事のReady・画像保存成功の保証ではない。
- 本番鍵の手動登録と鍵をチャット/PRに露出させない運用は `docs/operations/eyecatch-copy-activation.md` に従う。`eyecatch-copy-activation-proof.yml` は `main` 上の `workflow_dispatch` のみを許容し、Actions secretで**合成データのみ**を別runner保存→復元→削除する。Daily・Gemini・note/Notion書込みは行わない。
- CIや合成データ検証のGREENは、本番記事での生成・再利用の実証とは区別し、本番秘鍵が未登録なら遠隔cacheを無効のままとする。

### 9.5 Asset version binding

Eyecatch file名tokenはPublic title SHA + Eyecatch policy SHAへbindされる。image + sidecar manifestを対で扱い、古いPNG URLが残るだけではcurrent assetと認めない。

### 9.6 Existing note cover-only apply / stable draft identity

既存private draftへcoverだけを差し替える場合:

- exact sync_id
- exact current asset
- exact existing private draft
- persisted `note下書きID` を唯一のstable draft routing authorityとする
- Chrome historyからdraftを探索しない
- visual-repair projectionでも `note下書きID` を落とさない
- `note.com` と `editor.note.com` のhost差は、opaque edit path / draft identityが同一なら同一draftとして扱える
- opaque draft identityが異なるrouteはFail-Closed
- title unchanged
- body unchanged
- new draft作成禁止
- public release禁止
- 差し替え前coverをbackup
- failure時restore
- reload後に新coverのpersistを再確認

### 9.7 Subscription Attribution runtime-state write

Subscription Attribution JSONをGitHubへ保存する場合、readとwriteのbranch authorityを分離しない。

- target branchは `EYECATCH_GITHUB_BRANCH`
- GETも同じbranchを `ref` 指定
- 既存ファイルがある場合はそのbranch上のcurrent blob SHAを取得しPUT payloadへ含める
- PUTの`branch`も同じ `EYECATCH_GITHUB_BRANCH`
- default branchをGETし別branchへSHAなしPUTする経路は禁止

---

## 10. Content Intelligence → Note Delivery Contract

### 10.1 Content Intelligence DB

Content Intelligenceは **Content Event / Article単位** のSource of Truth。保持するもの:

- 発見元
- 元情報URL / 一次情報URL
- Screening / Deep Dive結果
- Decision / Score
- article status
- article manuscript
- Ready provenance
- eyecatch
- publication candidate state

Ready page本文は8.1のsingle canonical manuscript invariantに従う。

### 10.2 Note Ready DB

`note_ready_sync.py` はzero-model。

通常同期で必要:

- Source rowが記事状態Ready
- active public source
- current-policy Ready manuscript
- manuscript SHA一致
- current Eyecatch asset

Human workflow fieldsは自動同期で上書きしない。保護対象:

- 投稿状態
- note公開URL
- 投稿予定日
- 投稿日

### 10.3 Current-run delivery causality

Full ONE-SHOT終了後、`run624_delivery_causality.py` が **今回runで実際にReady保存された候補だけ** を監査する。

- funnel ready_countとcandidate Ready数が一致
- article_saved=true
- valid source URL
- candidate rank有効
- 全current-run Ready targetをexact setで保持

Current-run Readyが0件なら古いReadyを勝手に次のdraft候補へ回さない。複数なら全件を個別exact targetで `note-ready-sync.yml` へdispatchする。

記事品質としてのReadyと新規note draft配送対象は分離する。

- queue rowなし / `投稿状態=投稿待ち` → 新規draft配送候補
- `投稿状態=投稿準備中` / `投稿済み` → already_delivered、再生成・再draft作成禁止、exact配送は成功no-opまたは既存ledger reconciliation
- `投稿状態=保留` / `取下げ` → 人間判断を優先しFail-Closed
- note配送状態を確認できない場合もFail-Closed

### 10.4 Reconcile-existing fan-out / exact sync retry

`note-ready-sync` preflightが `reconcile_existing` かつ `should_start_vm=true` を返した場合、durable-ledger reconciliationの正規対象としてnote VM child workflowへfan-outする。`eligible_ready` だけをVM起動条件にしてreconciliationを落とさない。

ChatOpsはbare `/aiif note sync` を保持しつつ、`/aiif note sync <32-hex sync_id>` でexact targetだけを再同期できる。exact target retryは別記事へfallbackしない。

### 10.5 Downstream fan-out

成功した通常ONE-SHOTはGH_PATで明示dispatchする。

- `note-ready-sync.yml` はcurrent-run delivery causalityに従ってdispatchする。
- `cross-db-contract-guard.yml` は成功した通常ONE-SHOTの後段Guardとしてdispatchする。
- `subscriber-decision-brief.yml` は **member-facing Subscriber / Decision Intelligenceに実質変更があった場合だけ** dispatchする。

Subscriber Decision Briefの変更判定は、同じFull ONE-SHOT内のPortfolio-aware Product Review / Context-First passが既に生成したmutation receiptだけを使う。`subscriber_sync.created` / `updated` / `archived` または `subscriber_updated` が1件以上なら変更あり、すべて0なら同期をSKIPする。判定のために追加のNotion全件scanやGemini callを行わない。

`subscriber-decision-brief.yml` 自体、Inventory Bootstrap `[apply]` からの独立した正規trigger、Member Presentationへの順序契約は維持する。Dailyから不要な全件同期だけを抑止し、会員向けDecision Brief機能そのものは無効化しない。

passive `workflow_run` subscribeによる二重writeを正規経路にしない。

---

## 11. Note Draft / Publication Contract

### 11.1 Private Draft

note automationの自動到達点は **private draft**。Public releaseは人間のみ。

公開本文へ内部生成制御ラベルを出さない。parser / note normalizationは旧出力互換として既知の内部制御ラベルをdeterministicに除去し、Final Publication Surfaceで内部マーカーが1件でも残ればFail-Closed。内部マーカー除去を理由にFact / Evidence / Decision本文を削除しない。

新規private draft配送は、本文・画像・タイトル等のmutation前にpersistent Chrome sessionがexact `trendhub_biz` accountを所有していることをread-onlyで証明する。

- `https://note.com/settings/profile` へ認証済みで到達できること
- creator nameがexact `AIF - AI Intelligence Factory` であること
- 同settings page内のprofile linkがexact `https://note.com/trendhub_biz` を指し、同一sessionが当該profileを所有していること
- public profile上の可視 `設定` controlへ依存しないこと
- logged-out時のbootstrapはnote.com stateだけを1回使用し、別accountを成功扱いしないこと
- stable edit route保存・reload後のtitle / body / eyecatch確認だけでは配送成功にしないこと
- 公式 `https://note.com/notes` 一覧で、まずlegacy exact hrefに同じopaque `note下書きID` が現れる場合をread-only proofとして受理すること
- hrefにdraft IDを露出しない現行UIでは、exact `{title}を編集` buttonを1件だけ要求し、そのbuttonからeditor routeへ遷移したURLのopaque draft identityが保存済み `note下書きID` と完全一致する場合だけ受理すること
- exact編集buttonが0件のまま、複数、非editor route、またはdraft ID不一致ならFail-Closedすること
- account ownershipまたはarticle-list proofが曖昧・不成立ならFail-Closedし、`queue_confirmed`へ進めないこと
- このproof自体はpublic release、追加Gemini call、追加Notion writeを行わないこと

既存private draftのread-only監査も同じidentity proofを共有し、direct editor routeの存在だけで成功扱いしない。期待accountと公式 `/notes` 一覧のexact draft identityを先に証明できない場合は、本文・eyecatch監査へ進まずsafe diagnostic codeでFail-Closedする。

### 11.2 Existing draft repair / exact regeneration

汎用exact repair lanes:

- Ready eyecatch finalize
- Ready note body resync
- Ready note cover apply
- Ready existing-draft regenerate
- persisted Ready existing-draft resume
- Ready asset persistence recovery

いずれもexact sync_idと既存stateをFail-Closed確認する。既存draft修復を理由に別記事・新規draftへ逃げない。

Ready existing-draft regenerationは少なくとも:

- Note Ready側が `Ready` / `投稿準備中`
- 既存 `note下書きID` があり、そのIDをdraft identity authorityとする
- `note公開URL` と `投稿日` が空
- Provider/source mutation前に既存private draftのedit routeへread-only到達確認
- 現行Production Gateが再生成結果を受理
- Content Intelligenceは同じexact pageへpersist
- note反映は同じdraft routeのtitle / body / current eyecatchだけ
- same edit route、title、body、eyecatchのpersistを再検証
- new draft / public release禁止

`persist_results=True` のProduction生成結果はnon-persistent report契約で判定しない。explicit tuple statusがあればそれを尊重し、plain manuscriptの場合はfresh lifecycle readで **article status=`Ready` かつ content status=`Deep Dive`** を確認できた場合だけaccepted。

`resume_persisted` はProduction生成とReady persistが成功した後にdelivery wrapperだけ停止した場合の限定resume:

- source lifecycleをfresh readで `Ready / Deep Dive`
- exact targetをqueue reconciliation
- destination page / draft ID / posting state binding不変
- generated count 0
- `production_pipeline.main()` を呼ばない
- Provider generation / Gemini call 0
- persisted current Ready manuscript / eyecatchを同じprivate draftへ反映
- new draft / public release禁止

### 11.3 Human publication reconciliation

Full Dailyは過去に人間が公開したnoteを `note_publication_reconcile.py` でread-only RSS確認できる。

- model call 0
- note editor write 0
- public release 0
- exact title 1件一致
- exact queue row 1件一致
- source page identity一致

の場合だけNote Ready DBへ投稿済み・note公開URL・投稿日を記録する。

### 11.4 Publication date provenance

**Content Intelligenceの「公開日」** と **noteの「投稿日」** は別物。

- Content Intelligence 公開日 = 一次Source側のpublication / update provenance
- note 投稿日 = 人間がnoteで公開した日

note RSS reconciliationでSource側公開日を上書きしない。Hacker News timestampを外部一次記事の公開日へ昇格させない。

---

## 12. Technology Intelligence / Decision History / Member Product

### 12.1 Technology Intelligence DB

Technology IntelligenceはArticle一覧ではなく、**durable Technology / Project entityのcurrent state** を持つ。

主な情報:

- canonical entity ID / aliases / official URL
- sources
- adoption score / status
- evidence confidence / production readiness
- main risk
- best / avoid use
- tracking / assessment state
- last evidence update / next review
- current article / source state

同じTechnologyの再評価はArticle rowを増やすだけではなくcurrent stateを更新する。

### 12.2 Decision History DB

Decision Historyはappend-oriented history。score delta、status change、previous score/status、risk/evidence change、snapshot type、entity ID、event IDを記録する。

### 12.3 Content Intelligenceとの違い

**Content Intelligence DB** = 「何が起きたか」。Content Event / 記事候補 / 記事生成・Ready・note連携の正本。
**Technology Intelligence DB** = 「その技術を今どう評価するか」。複数Source / Eventを統合したTechnology current state。

### 12.4 Member / Subscriber derived surfaces

Member PresentationはTechnology / Decision stateから生成するderived surface。

- canonical member DBをAuthority
- presentation都合でDecision/Evidenceを書き換えない
- legacy DBへ戻さない
- 不要なGemini callを追加しない
- Subscriber Decision Briefは会員向けDBの実質変更時だけDailyから更新し、変更0のDailyで全件再走査しない
- Inventory Bootstrap `[apply]` からの同期と、Subscriber Brief成功後のMember Presentation順序は維持する

### 12.5 Monthly Decision Brief

Member sync後にexact monthly briefをzero-modelで更新する。今月のTop判断、ADOPT / TEST中心の実務判断、重要なscore / decision change、主リスク、次の一手、DB / 公式情報へのリンクを含む。更新方式はcontent-first replacementで、新bodyのNotion受理前に旧bodyを消さない。「変化がない」場合も判断情報として明示する。

---

## 13. Portfolio / Profit / Learning Contract

Full Productionは単純な新着順だけでDeep Diveしない。

現行主要設定:

- TOP_N_FOR_DEEP_DIVE = 3
- Profit Priority有効
- Decision weight = 0.65
- Commercial weight = 0.35
- Evergreen最低1
- Topic diversity最低2
- Source ROI learning有効
- Source ROI history 30 runs
- recency decay 0.93

Source ROIは過去のscreened / deep dive / stock / Ready効率からfetch配分を学習するが、Evidence / Source diversity契約を壊して一Sourceへ全振りしない。

---

## 14. Safety / Cost / Side-effect Contract

優先順位:

1. Evidence / Fact integrity
2. Publication safety
3. Provider budget保護
4. 不要な外部write回避
5. 低コスト運用
6. Ready yield / business value最大化

禁止:

- 診断のためだけにGemini APIを勝手に消費
- Provider障害を記事品質FAILと混同
- 503で無制限retry
- current-run Ready 0件なのに過去Readyをdraft
- test / auditの副作用としてnote公開
- note publication自動化
- secret/tokenをartifactやrepositoryへ保存
- Notionの人間管理fieldを品質同期で上書き
- Gateを通すためのEvidence捏造
- stale Readyをmanual property変更だけでcurrent扱い
- published / delivery-started articleを自動再生成
- member-facing変更0のDailyでSubscriber Decision Brief全件同期を無条件発火

X / ApifyもFull時だけ明示的に有効化し、charge / record上限を持つ。

---

## 15. CI / Repository Governance

### 15.1 Core PR Guards

現行mainの主要保護:

- Integration Reconciliation CI
- Repository-wide Falsification Guard
- Notion Access Policy Guard
- Workflow Reference Guard
- Cross DB Contract Guard等の領域別contract check

Required / protective checksは過去文書の文言一致ではなく、**実行可能なSafety invariant** を監査する。

### 15.2 Canonical Specification Freshness Guard

`specification_freshness_guard.py` をzero-provider / deterministic guardとしてRepository-wide Falsification Guardへ接続する。

Production Contract Fingerprintの対象:

- tracked Production Python / shell surfaces
- `local_skills/`
- `.github/workflows/` / `.github/actions/`
- `assets/`
- runtime dependency/config files

対象外:

- `AI_Intelligence_Factory_最終仕様書.md` 自身
- `tests/`
- `docs/`
- `.runtime/`

CIは少なくとも:

1. 現行Production surface bytesからFingerprintを計算
2. 本書記載Fingerprintと完全一致を要求
3. git historyから最新Production-surface変更日を求め、本書のProduction最終照合日と完全一致を要求
4. metadata欠落・形式不正・Fingerprint不一致・照合日staleをFail-Closed
5. full historyが必要なためcheckoutは `fetch-depth: 0`

Production surfaceが変わったのに本書を更新しないPRはGREENにしない。tests/docsのみの変更はFingerprintを変えず、無意味な仕様書churnを要求しない。

### 15.3 Deterministic regression

可能な限りzero-provider / deterministic / hermetic / synthetic smokeを先に実行する。実Provider / Notion / note書き込みが必要な検証は明示ONE-SHOT / maintenance workflowへ分離する。

### 15.4 Dependency

Production Pillow:

- `Pillow>=12.1.0,<13.0.0`

CI known-green:

- `Pillow==12.3.0`

Eyecatch layout / font / pixel proofの互換性をCIで守る。

---

## 16. 廃止・復活禁止事項

以下を現行Productionへ戻さない。

- Groq + Gemini coexistence
- Groq / Qwen shadow provider
- Product Hunt active acquisition
- Scheduled Daily cron
- old current-policy Ready recovery workflow
- Ready metadata rebase workflow
- fixed-ID / fixed-SHA / fixed-period recovery tooling
- 45記事Recoveryを未完backlogとして再開
- 旧記事をcurrent-run Readyとしてdraftするfallback
- note自動公開
- 古いeyecatch PNGをURL存在だけでcurrent扱い
- `...` / `…` でheadline truncationを許容
- 不完全文節で終わるeyecatch headline
- 日本語語中改行を文字幅都合で許容
- EvidenceとContent Event identityの混同
- fuzzy titleだけのTechnology entity merge
- Product Reviewを記事Deep Dive中へ重複混在
- Chrome historyをprivate draft identity authorityとして使うこと
- 複数の旧Markdown manuscriptを1つのReady Content Intelligence pageへ残すこと
- member-facing変更0のDailyからSubscriber Decision Brief全件同期を無条件発火すること

---

## 17. Documentation Governance

### 17.1 唯一の全体入口

Factory全体を理解するときは、まず本書を読む。ただし最終Authorityは `main`。

### 17.2 Production変更時の更新ルール

Production surfaceが変わるPRでは、**本書の同期をmerge条件**とする。

必須:

- `Production最終照合日` を最新Production変更日へ更新
- `Production Contract Fingerprint` をcurrent bytesへ更新
- Productionの意味・契約が変わった場合は該当本文も同じPRで更新
- 本書の意味内容自体を変えた場合は `仕様最終変更日` も更新
- `実装監査基準SHA` は人間が横断照合したmain基準点を記録

「本文変更不要」と判断した内部修正でも、Production bytesが変われば照合日とFingerprintを更新し、仕様との矛盾なしを明示する。逆にtests/docsだけの変更ではこの更新を要求しない。

この契約は注意書きではなく **CI fail-closed contract** とする。日付だけを新しくして古いFingerprintを残す、またはFingerprintだけ更新して古い照合日を残す状態もGREENにしない。

### 17.3 本文更新必須の代表変更

- Provider / model routing
- Screening / Deep Dive pool
- Source architecture
- Candidate dedupe / Entity Resolution / Published Terminal
- Publication / Ready contract
- Article / Reader Gateの意味
- A+ / Local Skills Production経路
- Editorial Style
- Eyecatch rendering / integrity / approved master
- Subscription Attribution / runtime-state asset persistence
- Content Intelligence manuscript persistence
- Note Ready / Draft / Publication reconciliation
- exact existing-draft regeneration / persisted resume / Ready asset recovery
- Daily / ChatOps entrypoint
- Current-run delivery causality
- Paid Product / Member surface
- Technology / History DB authority
- Repository全体の大規模整理

内部リファクタだけで意味が変わらない場合はRun番号や履歴を本書へ増やさない。

### 17.4 過去資料

`docs/reference/` / `docs/audits/` / `docs/archive/` は設計理由、障害記録、検証結果、回帰由来、監査証跡としてのみ使う。

---

## 18. Current-state Summary — 2026-10-17

現在のFactoryは次を正式基準とする。

- **Execution:** Scheduled DailyはPAUSED。Manual ONE-SHOTのみ。
- **Full Daily:** ChatOps経由では `human_narrative`。
- **Entry point:** `production_pipeline.py`。
- **Runtime:** `runtime_layers.py` が正本。
- **Screening:** Gemini 3.5 Flash-Lite / 3.1 Flash-Liteのみ。
- **V2 Shadow:** deterministic cheap screening → health-aware Semantic Screening（3.5 Flash-Lite / 3.1 Flash-Lite、最大20候補を1 batch、最大2 model attempts、全滅時はdeterministicへ縮退）→ Selection Value再ranking → rank-1 health-aware Evidence（3.6 / 3.5 / 3.7 / 3.8 / 3 Flash Preview、最大5 model attempts、valid false判定でも停止）。通常model callは2、最悪時上限7、Evidence lane全滅時のみwinnerなしでFail-Closed。V1 Provider Healthをread-only参照し、Production mutationは0。
- **V2 Acquisition Reliability:** OfficialVendor / GitHub / HackerNews / ArXivの一時障害は共通bounded GET契約で扱い、timeout / connection / 429 / 5xxだけ最大1回retry。非transient failureは再送せず、Source failureを他Sourceへ波及させない。safe attempt diagnosticsをartifactへ残す。
- **V2 Gold Benchmark:** human-labeled Gold corpusを用いたprovider-free評価で4 Semantic dimensionsのPrecision / Recall / F1、macro、exact-match、saturationを算出。CIではGemini call 0。
- **Article Deep Dive:** Gemini 3.6 / 3.5 / 3.7 / 3.8 / 3 Flash Previewをhealth-aware Full Flash laneで運用。Flash-Liteは公開Writerから除外。
- **503:** Factory single retry owner + bounded distinct-model fallback。
- **A+:** Local Skills skeleton + Gemini prose + deterministic Gates + safe local fallback。
- **Active acquisition:** GitHub / HackerNews / ArXiv / OfficialVendor。
- **X:** Discovery専用。Apify ActorはXquik `xquik~x-tweet-scraper`。20 handlesを1 bounded run、最大100件・5件/profile・12h、charge cap $0.05。X本文はEvidenceにしない。
- **Product Hunt:** retired。
- **Dedupe:** URL canonicalization + OfficialVendor revision event identity。
- **Published Terminal:** delivered/published existing articleは自動再生成しない。pre-publication delivery stateを正に証明できる場合だけ自動Recovery可。
- **Entity Resolution:** conservative、bound Evidenceのみalias可、fuzzy title merge禁止。
- **Reader format:** Narrative Lead + どんな内容？ / なぜ重要？ / 結論は？ / 元情報。
- **Ready:** policy SHA + manuscript SHA + style provenance。
- **Content Intelligence Ready body:** current canonical manuscriptをexact 1本だけ保持。複数旧稿残存はFail-Closed対象。
- **Eyecatch V2:** 承認済み白背景＋右側青ガラスAIコア、zero-provider overlay、動的badge、hook、title、footer。
- **Eyecatch integrity:** 1280×670、PNG pixel proof、ellipsis禁止、語中改行禁止、不完全文節終端禁止、Run248もpolicy hash対象。
- **Stable note draft identity:** persisted `note下書きID` をauthorityとし、note.com / editor.note.comのhost差よりopaque draft path一致を優先。
- **New private draft proof:** mutation前にexact `trendhub_biz` / `AIF - AI Intelligence Factory` ownershipをsettings pageから証明し、保存後は公式 `/notes` 一覧でlegacy exact hrefを優先、ID非露出時はexact `{title}を編集` button → editor routeから同じopaque draft IDを証明して初めて成功とする。
- **Subscription Attribution:** GitHub GET/PUTは同じ `EYECATCH_GITHUB_BRANCH` を使用し、既存更新はbranch上current SHAをPUTへ渡す。
- **Note delivery:** current-run Ready全件をexact target判定へ送る。`reconcile_existing` はdurable-ledger reconciliationとしてVM fan-out可能。
- **Exact note sync:** bare syncに加え32-hex target指定のChatOps再同期を持つ。
- **Exact note audit:** 32-hex target指定のChatOpsから既存private draftをread-only監査し、expected account ownershipと公式 `/notes` のexact draft identityを先に証明する。同一Issue commentの重複deliveryはdispatch前のdurable claimで抑止し、Gemini/model call・draft mutation・Production実行・public releaseを行わない。
- **Existing draft regeneration:** exact sync_id、既存draft identity、未公開stateを固定し、現行Gate通過後も同じdraftだけ更新。
- **Persisted resume:** `Ready / Deep Dive` をfresh確認し、Provider generation / Gemini call 0でpersist済み本文とeyecatchを同じdraftへ反映。
- **Ready asset recovery:** exact Content Intelligence pageをdirect GETし、terminal guard → current Production → fresh Ready proof後だけ配送。
- **Publication reconcile:** RSS read-only。note投稿日と一次Source公開日を分離。
- **Content Intelligence:** Event / Articleの正本。
- **Technology Intelligence:** durable Technology current state。
- **Decision History:** change history。
- **Paid Product:** Use-Decision Intelligence / 月額1,980円。
- **Subscriber Decision Brief:** 機能は維持し、Full Dailyではmember-facing mutationがある場合だけdispatch。変更0ならSKIPし、判定用の追加Notion scan / Gemini callは0。
- **Monthly Brief:** zero-modelでMember current stateから更新。
- **Product Review:** Daily内で専用1 pass。
- **CI:** Falsification / Integration / Notion / Workflow guardsに加え、Canonical Specification Freshness Guardで仕様書の照合日とProduction Fingerprintを機械強制。
- **Recovery:** 過去Recovery専用surfaceを復活させず、現行exact / fail-closed laneだけを使う。

この状態から次の開発を行う。過去Run文書・旧Recovery・旧Provider構成・旧Source構成を暗黙の前提として引き継がない。
