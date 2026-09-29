# AI Intelligence Factory — 現行Production仕様

最終更新: **2026-09-29**  
Production Source of Truth: **`main`**  
Canonical Specification: **本ファイル**  
実装監査基準SHA: **`3bd95621fb4064dafe3b8f00dd5486f799e504b2`**  
（この仕様同期自体のmergeで `main` SHAは変わり得るが、Productionコード契約は上記SHAを基準に監査した。）

> 本書は、現在のAI Intelligence Factory（AIIF）がProductionで「何を実行し、何を禁止し、どこをFail-Closedにするか」を示す唯一の全体仕様入口である。  
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
- Provider / Source / Gate / Ready / Daily / ChatOps / Note / Paid Product の意味が変わる変更をmergeする場合、本書も同じ変更単位で同期する。

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

現行標準価格は **月額1,980円**。

noteは販売チャネルの一つであり、Factoryそのものではない。

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

通常のProduction発火は専用Control Issue経由の `AIIF ChatOps ONE-SHOT Bridge` を使える。

代表コマンド:

- `/aiif run full`
- `/aiif run article_validation`
- `/aiif run pending_retry_validation`
- `/aiif run ready_rescue_validation`
- `/aiif run production_e2e_validation`
- `/aiif run production_e2e_preflight`
- `/aiif run local_skills_canary_validation`
- `/aiif run local_skills_production_validation`

Control Issue、owner、run_attempt等を二重認証し、GH_PATで既存manual workflowを1回だけdispatchする。Bridge自身がProduction処理を直接実行しない。

`/aiif run full` は現行運用上 **`human_narrative`** を明示してDaily ONE-SHOTへ渡す。

### 2.4 Editorial Style

ONE-SHOTが受理するStyle:

- `classic`
- `human_narrative`
- `duo_narrative`

未知StyleはFail-Closed。

`duo_narrative` はフェルン／クレハを使う任意Styleであり、通常のFull Dailyでは自動選択しない。

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
- X投稿本文そのものをEvidenceにしない。
- 技術的Factはリンク先一次情報で確認する。
- 必須4 Sourceの配分をXで置換しない。
- Publication Source上は `X（一次情報への発見経路）` と明示する。

### 3.3 Product Hunt

**Product Huntはactive Production Sourceではない。**

旧enumやhistorical artifactに残っていても、Fresh取得・Publication Source・現行商品価値の必須Sourceへ戻さない。

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

Screeningは大量候補の低コスト選別を担当し、記事本文の最終品質を担わない。

### 4.2 Deep Dive / Article Models

現行Full ONE-SHOTの明示allowlist:

- `gemini-3.7-flash`
- `gemini-3.8-flash`
- `gemini-3.6-flash`
- `gemini-3.5-flash`
- `gemini-3-flash-preview`（既存health routingの候補）

モデル別persistent daily budgetは各18。

公開用記事の初稿・Human Narrative / Quality Retryは上記のFull Flash系のみを候補にする。Flash-Lite系はScreening、分類、Evidence整理、JSON抽出等の非公開補助処理に限る。上位Writer候補が全て503、timeout、quota等で利用不能なら記事をReadyへ進めず、既存のPending Retry等の非Ready状態で止め、note下書きへ配送しない。Quality repairの最大2モデル制限とhealth routingを維持する。

通常Deep Diveはprovider reliability layerで `thinking_level=low`、Quality Retryは `medium` を明示する。本文の `max_output_tokens` は既存の `GEMINI_DEEP_DIVE_MAX_OUTPUT_TOKENS`（既定9000）を維持する。各モデルのthinking対応値はGoogleの現行SDK/API仕様で照合済み。

Deep Dive run budgetは **12 provider-visible requests** を上限とする。

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

履歴が同条件なら、Routerのcold-start tie-breakは概ね:

**3.6 → 3.5 → 3.7 → 3.8**

ただし、実際に使えるmodel setはそのWorkflowで明示されたallowlistとquota状態を優先する。

### 4.4 503 / Retry ownership

google-genai SDK内部のtransient retryはProductionで無効化し、**Factoryを唯一のretry owner** とする。

通常Deep DiveのFull Flash modelでは、provider-verified 503を受けた場合、同一modelへ無駄な再送を重ねず次のdistinct modelへ進み、限られたrequest budgetを保護する。

Quality repairは最大 **2 distinct models**。

429 / RPD / RPM / timeout / 404は既存quota・circuit契約に従い、無制限retryしない。

### 4.5 Product Review

Product Reviewは記事Deep Dive内に混在させない。

Full Dailyでは:

- main Production中の `PRODUCT_REVIEW_MAX_PER_RUN=0`
- 旧bootstrapも0
- 後段の **Portfolio-aware Product Review** を専用passとして1回実行
- review max: 2
- request budget: 3

Product Review runtimeは記事Publication / Reader / Eyecatch layersを持たず、Provider / quota safetyだけを使う。

---

## 5. Candidate Identity / Dedupe / Entity Resolution

### 5.1 URL dedupe

`candidate_identity.py` が保守的にcanonicalizeする。

除外してよいもの:

- `utm_*`
- `fbclid`
- `gclid`
- `ref`
- `source`
- default port
- presentation-level trailing slash差

ArXivは `abs/pdf/version/.pdf` の差を同一paper IDへcanonicalizeする。

意味のあるpath/queryを勝手に消さない。

### 5.2 Content EventとEvidence identityを分離

OfficialVendorのpage-level revisionは、revision付きURLを **Content Event key** とする。

stable primary URLまで同一dedupe集合へ混ぜて、後続revisionを旧イベント扱いにしない。

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

### 6.3 Provider-free fallback

Local fallbackは何でも生成してよい逃げ道ではない。

使用条件:

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

### 6.5 Human Narrative

`human_narrative` は事実を脚色するStyleではない。

許容:

- 読者が場面を想像できる導入
- 軽い比喩
- 現実的なツッコミ
- 技術と仕事の距離を縮める表現

禁止:

- 架空の体験談
- 架空の会話をFact扱い
- Evidenceにない因果
- 誇張された断定
- 同じ会社員ネタ等のテンプレ使い回し

Human Narrativeは **Source-specific Hook** を優先する。

- 冒頭1〜2段落で一次情報固有の数字、出来事、矛盾、制約、著者の強い問題提起、比喩等へ早く接続する
- 「私たち」「多くの人」「そんな経験は少なくない」等の一般化された共感だけで導入を作らない
- オピニオン/エッセイの温度・違和感・ユーモアを全部消して無難な企業向け一般論へ均さない
- 「こうした背景から」「この現状を踏まえて」「まずは小さく」等の汎用ビジネス作文を複数連鎖させない
- Source固有のEvidenceと無関係な「ガイドラインを見直す」「評価項目に加える」だけでActionを閉じない

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

Human Appealの中核品質が `WEAK` の原稿は最大1回のQuality Retryを行う。Retry後も `WEAK` ならFact / PublicationがPASSでもNeeds Editorial Review等の非Readyへ送り、note下書き配送を禁止する。記事固有の導入が弱い `opening_hook_weak`、判断の欠落、AI調の複合的な兆候、読者価値の重大な不足はREVIEWとする。軽微な語尾・反復・表面表現だけのSOFT warningは、Human AppealがACCEPTABLEなら警告付きReadyを許可できる。Run #186の「The revolt of the reader」実稿を回帰fixtureとする。

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

現行Public manuscriptは、記事固有のNarrative Leadを保持した上で、固定のReader Summaryを使う。

主要見出し:

- **どんな内容？**
- **なぜ重要？**
- **結論は？**
- **元情報**

「何が出た？」の重複labelは使わない。

元情報には主一次情報と発見経路を表示する。

未知の技術・製品・略語は「知っていて当然」で進めず、初出で非専門読者に役割が分かる日本語へ橋渡しする。

### 7.3 Decision語彙

NOW / TRY / WATCH / WAIT / AVOIDをそのままpublic本文へ漏らさない。

歴史・研究・事件・制度・ベンチマーク等を、無理に「導入する／しない」へ翻訳しない。対象に合うAction（確認、比較、検証、追跡、基準点化等）を使う。

---

## 8. Publication / Ready Contract

Readyは単なるSelect値ではない。

現行Ready blockは少なくとも次を証明する。

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

### 8.1 Visual-only repair

Article policyがstaleでも、過去本文が

- Ready caption family
- 正しいmanuscript SHA
- exact title一致

を満たす場合、**visual-only repair** のためだけにbyte-authenticated本文を利用できる。

この経路は:

- article bodyをrestampしない
- titleを変えない
- article regenerationしない
- public releaseしない
- 現行Eyecatch Contractだけを更新する

---

## 9. Eyecatch Publication Contract

Eyecatchは単なるPNGではない。Public titleと現行rendering policyにbindされたasset。

### 9.1 Geometry / Format

必須:

- PNG
- RGB
- **1280 × 670**
- Noto Sans JP production font
- 日本語fontがない場合はFail-Closed

### 9.2 Headline integrity

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

を要求する。

省略記号で「収まったことにする」運用は禁止。

### 9.3 Japanese line-break integrity

Headlineは原則1〜3行。

禁止例:

- `新し｜い`
- `管｜理者`
- `エー｜ジェント`
- `Chat｜GPT`

保護する単位:

- 漢字複合語 + 送り仮名
- カタカナ語
- 英数字product / model token
- 明示的空白境界

収まらない場合:

1. 自然な意味境界へ改行
2. 3行化
3. 許容範囲内でfont縮小

を優先し、語中改行で無理に収めない。

Eyecatch semantic layoutのProvider利用は補助処理としてboundedに扱う。

- `gemini-3.6-flash` → `gemini-3.5-flash` の順で各1回だけ試行
- 各Provider sendは **30秒 watchdog** 内で実行
- watchdogが利用できない場合はProviderを呼ばずFail-Closed
- 503 / timeout / invalid layoutは次のProviderまたは既存deterministic layoutへfallback
- Eyecatch layout待機がDaily全体のjob timeoutを占有することを禁止

### 9.4 Asset version binding

Eyecatch file名tokenは:

- Public title SHA
- Eyecatch policy SHA

へbindされる。

image + sidecar manifestを対で扱い、古いPNG URLが残っているだけではcurrent assetと認めない。

### 9.5 Existing note cover-only apply

既存private draftへcoverだけを差し替える場合:

- exact sync_id
- exact current asset
- exact existing private draft
- same edit route
- title unchanged
- body unchanged
- new draft作成禁止
- public release禁止
- 差し替え前coverをbackup
- failure時restore
- reload後に新coverのpersistを再確認

を必須とする。

---

## 10. Content Intelligence → Note Delivery Contract

### 10.1 Content Intelligence DB

Content Intelligenceは **Content Event / Article単位** のSource of Truth。

保持するもの:

- 発見元
- 元情報URL / 一次情報URL
- Screening / Deep Dive結果
- Decision / Score
- article status
- article manuscript
- Ready provenance
- eyecatch
- publication candidate state

### 10.2 Note Ready DB

`note_ready_sync.py` はzero-model。

通常同期で必要:

- Source rowが記事状態Ready
- active public source
- current-policy Ready manuscript
- manuscript SHA一致
- current Eyecatch asset

Human workflow fieldsは自動同期で上書きしない。

保護対象:

- 投稿状態
- note公開URL
- 投稿予定日
- 投稿日

### 10.3 Current-run delivery causality

Full ONE-SHOT終了後、`run624_delivery_causality.py` が **今回runで実際にReady保存された候補だけ** を監査する。

契約:

- funnel ready_countとcandidate Ready数が一致
- article_saved=true
- valid source URL
- candidate rank有効
- 全current-run Ready targetをexact setで保持

Current-run Readyが0件なら、古いReadyを勝手に次のdraft候補へ回さない。

Current-run Readyが複数なら、**全件を個別にexact targetで `note-ready-sync.yml` へdispatch** する。

ここで **記事品質としてのReady** と **新規note draft配送対象** は分離する。

- note Ready DBに行が無い / `投稿状態=投稿待ち` → 新規draft配送対象
- `投稿状態=投稿準備中` / `投稿済み` → **already_delivered**。再生成・再draft作成を禁止し、exact配送は成功no-op
- `投稿状態=保留` / `取下げ` → 人間判断を優先してFail-Closed
- 自動同期はHuman workflow fieldの`投稿状態`を`投稿待ち`へ巻き戻さない

また、write-enabledのautomatic stale Ready Recoveryは、note配送状態が
`not_queued` または `投稿待ち` と確認できる記事だけを対象にする。
`投稿準備中` / `投稿済み` / `保留` / `取下げ` はProvider呼び出し前に除外する。
note配送状態を確認できない場合もFail-Closedで自動Recoveryしない。

したがって「Readyになった記事はすべてexact配送判定へ送る」が契約であり、
**既に配送済みの記事を重複して下書き生成する、という意味ではない。**

### 10.4 Downstream fan-out

成功した通常ONE-SHOTはGH_PATで明示dispatchする。

- `note-ready-sync.yml`
- `subscriber-decision-brief.yml`
- `cross-db-contract-guard.yml`

passive `workflow_run` subscribeによる二重writeを正規経路にしない。

---

## 11. Note Draft / Publication Contract

### 11.1 Private Draft

note automationの自動到達点は **private draft**。

Public releaseは人間のみ。

公開本文へ内部生成制御ラベルを出さない。

- Provider promptは記事タイトル直後から本文を開始し、公開用ではない本文開始ラベルを要求しない
- parser / note normalizationは旧出力互換として既知の内部制御ラベルをdeterministicに除去する
- Final Publication Surfaceで内部マーカーが1件でも残ればFail-Closed
- 内部マーカー除去を理由にFact / Evidence / Decision本文を削除しない

### 11.2 Existing draft repair

汎用exact repair lanes:

- Ready eyecatch finalize
- Ready note body resync
- Ready note cover apply

いずれもexact sync_idと既存stateをFail-Closed確認する。

既存draft修復を理由に別記事・新規draftへ逃げない。

### 11.3 Human publication reconciliation

Full Dailyは、過去に人間が公開したnoteを `note_publication_reconcile.py` でread-only RSS確認できる。

この処理は:

- model call 0
- note editor write 0
- public release 0
- exact title 1件一致
- exact queue row 1件一致
- source page identity一致

の場合だけNote Ready DBへ:

- 投稿状態=投稿済み
- note公開URL
- 投稿日

を記録する。

### 11.4 Publication date provenance

**Content Intelligenceの「公開日」** と **noteの「投稿日」** は別物。

- Content Intelligence 公開日 = 一次Source側のpublication / update provenance
- note 投稿日 = 人間がnoteで公開した日

note RSS reconciliationでSource側公開日を上書きしない。

Hacker News timestampはHN投稿 / discovery時刻であり、外部一次記事の公開日へ昇格させない。

---

## 12. Technology Intelligence / Decision History / Member Product

### 12.1 Technology Intelligence DB

Technology IntelligenceはArticle一覧ではない。

**durable Technology / Project entityのcurrent state** を持つ。

主な情報:

- canonical entity ID
- aliases
- official URL
- sources
- adoption score
- adoption status
- evidence confidence
- production readiness
- main risk
- best / avoid use
- tracking status
- assessment state
- last evidence update
- next review
- current article / source state

同じTechnologyの再評価は新しいArticle rowを増やすだけではなく、current stateを更新する。

### 12.2 Decision History DB

Decision Historyはcurrent stateの上書きDBではなく、変化を追うappend-oriented history。

記録:

- score delta
- status change
- previous score/status
- risk / evidence change
- snapshot type
- entity ID
- event ID

### 12.3 Content Intelligenceとの違い

**Content Intelligence DB**
- 「何が起きたか」
- Content Event / 記事候補
- 記事生成・Ready・note連携の正本

**Technology Intelligence DB**
- 「その技術を今どう評価するか」
- Technology / Project entity
- 複数Source・複数Eventを統合したcurrent state

両者を同一DBの重複行として扱わない。

### 12.4 Member / Subscriber derived surfaces

Member PresentationはTechnology / Decision stateから生成するderived surface。

- canonical member DBをAuthorityとする
- presentation都合でDecision/Evidenceを書き換えない
- legacy DBへ戻さない
- 不要なGemini callを追加しない

### 12.5 Monthly Decision Brief

Paid-product freshnessを保つため、Member sync後にexact monthly briefをzero-modelで更新する。

内容:

- 今月のTop判断
- ADOPT / TEST中心の実務判断
- 重要なscore / decision change
- 主リスク
- 次の一手
- DB / 公式情報へのリンク

更新方式はcontent-first replacement。新bodyのNotion受理前に旧bodyを消さない。

「変化がない」場合も判断情報として明示する。

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
- note publicationを自動化
- secret/tokenをartifactやrepositoryへ保存
- Notionの人間管理fieldを品質同期で上書き
- Gateを通すためのEvidence捏造
- stale Readyをmanual property変更だけでcurrent扱い

X / ApifyもFull時だけ明示的に有効化し、charge / record上限を持つ。

---

## 15. CI / Repository Governance

### 15.1 Core PR Guards

現行mainの主要保護:

- Integration Reconciliation CI
- Repository-wide Falsification Guard
- Notion Access Policy Guard
- Workflow Reference Guard

Required / protective checksは過去文書の文言一致ではなく、**実行可能なSafety invariant** を監査する。

### 15.2 Deterministic regression

可能な限り:

- zero-provider
- deterministic
- hermetic
- synthetic smoke

を先に実行する。

実Provider / Notion / note書き込みが必要な検証は、明示的なONE-SHOT / maintenance workflowへ分離する。

### 15.3 Dependency

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
- 日本語語中改行を文字幅都合で許容
- EvidenceとContent Event identityの混同
- fuzzy titleだけのTechnology entity merge
- Product Reviewを記事Deep Dive中へ重複混在

---

## 17. Documentation Governance

### 17.1 唯一の全体入口

Factory全体を理解するときは、まず本書を読む。

ただし最終Authorityは `main`。

### 17.2 更新必須の変更

次の変更をmergeしたら本書も同期する。

- Provider / model routing
- Screening / Deep Dive pool
- Source architecture
- Candidate dedupe / Entity Resolution
- Publication / Ready contract
- Article / Reader Gateの意味
- A+ / Local Skills Production経路
- Editorial Style
- Eyecatch rendering / integrity
- Note Ready / Draft / Publication reconciliation
- Daily / ChatOps entrypoint
- Current-run delivery causality
- Paid Product / Member surface
- Technology / History DB authority
- Repository全体の大規模整理

内部リファクタだけで意味が変わらない場合は、Run番号や履歴を本書へ増やさない。

### 17.3 過去資料

`docs/reference/` / `docs/audits/` / `docs/archive/` は:

- 設計理由
- 障害記録
- 検証結果
- 回帰由来
- 監査証跡

としてのみ使う。

---

## 18. Current-state Summary — 2026-09-29

現在のFactoryは次を正式基準とする。

- **Execution:** Scheduled DailyはPAUSED。Manual ONE-SHOTのみ。
- **Full Daily:** ChatOps経由では `human_narrative`。
- **Entry point:** `production_pipeline.py`。
- **Runtime:** `runtime_layers.py` が正本。
- **Screening:** Gemini 3.5 Flash-Lite / 3.1 Flash-Lite。
- **Article Deep Dive:** Gemini 3.6 / 3.5 / 3.7 / 3.8 / 3 Flash Previewをhealth-aware routingで運用。Flash-Liteは公開Writerから除外。
- **503:** Factory single retry owner + bounded fallback。
- **A+:** Local Skills skeleton + Gemini prose + deterministic Gates + safe local fallback。
- **Local Skills:** canary / bounded Production validationを持つ。
- **Active acquisition:** GitHub / HackerNews / ArXiv / OfficialVendor。
- **X:** Discovery専用。X本文はEvidenceにしない。
- **Product Hunt:** retired。
- **Dedupe:** URL canonicalization + OfficialVendor revision event identity。
- **Entity Resolution:** conservative、bound Evidenceのみalias可、fuzzy title merge禁止。
- **Reader format:** Narrative Lead + どんな内容？ / なぜ重要？ / 結論は？ / 元情報。
- **Ready:** policy SHA + manuscript SHA + style provenance。
- **Eyecatch:** 1280×670、PNG pixel proof、ellipsis禁止、語中改行禁止。
- **Note:** current-run Ready全件をexact targetでprivate draftへ送る。公開は人間のみ。
- **Publication reconcile:** RSS read-only。note投稿日と一次Source公開日を分離。
- **Content Intelligence:** Event / Articleの正本。
- **Technology Intelligence:** durable Technology current state。
- **Decision History:** change history。
- **Paid Product:** Use-Decision Intelligence / 月額1,980円。
- **Monthly Brief:** zero-modelでMember current stateから更新。
- **Product Review:** Daily内で専用1 pass。
- **CI:** Falsification / Integration / Notion / Workflow guardsを維持。
- **Recovery:** 過去Recovery専用surfaceを復活させない。

この状態から次の開発を行う。過去Run文書・旧Recovery・旧Provider構成・旧Source構成を暗黙の前提として引き継がない。
