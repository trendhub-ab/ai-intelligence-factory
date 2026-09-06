# AI Intelligence Factory — 現行Production仕様

最終更新: 2026-09-06  
現行Functional Baseline: **Run209 — Gemini timeout RPD fail-closed**  
Documentation Governance Baseline: **Run210 — Documentation Freshness Guard**  
Production Source of Truth: **`main`**  
Paid Member Sync Baseline: **Run211 — Subscriber Decision Brief Sync / Member Presentation Sync**  
Paid Member UX Baseline: **Run215**  
Paid Member Commerce/Onboarding Baseline: **Run217**  
Paid Member Navigation/UI Baseline: **Run218**  
Paid Member Presentation Baseline: **Run219**  
Paid Member Database Destination Baseline: **Run220**  
Paid Member Database Hosting Baseline: **Run221**  
Paid Product Baseline: **Run256 — Work-First / Natural Neutral-Subject / Concrete Decision Update**  
Paid Product Contract: **`PAID_PRODUCT_CONTRACT.md`**  
Article Production Baseline: **Run249 + current article-quality stack**  
Eyecatch Baseline: **Run181 current**  
Pipeline Modularization Baseline: **Run245**  
Repository Organization Baseline: **Run246**  
Workflow Reference Integrity Baseline: **Run257 — Workflow Reference Guard**

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

**Web制作・マーケティング・業務改善・クリエイティブなどでAIを仕事に活用する1〜3名規模の事業者で、ツールを選び、試し、導入判断をする人。**

- AI専業である必要はない。
- 「顧客からAI相談を受けること」は必須条件ではない。
- 顧客への提案・説明は副次価値であり、商品目的へ昇格させない。
- 「AIに興味がある個人全般」「非エンジニア全般」「法人全般」は初期ICPにしない。
- 法人は将来の高単価市場として保持するが、PMF前に請求書・複数席・SSO・管理者機能を作り込まない。

### 中心価値

> **AIを全部追わなくても、仕事に使えるものがわかる。**

有料価値は「情報量」ではなく、**知る → 理解する → 仕事に使えるか判断する → 必要なら小さく試す**を短時間で進められること。

### 商品4層

1. **無料note** — 知る・面白く理解する。無料品質を意図的に落とさない。
2. **Decision Brief** — 今月、仕事で知っておく価値がある3〜7件を先に読む。
3. **Decision Intelligence** — 必要時に全体DBで比較・根拠・リスク・履歴を確認する。
4. **Work Action Asset** — 利用条件、判断シート、小規模検証条件、比較観点等へ落とす。大量テンプレート市場へピボットしない。

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
AI活用判断シート Page ID: `3d3479ff-dca9-8119-b0d8-c014b068fe82`

### 2.4 Member同期・Commerce互換契約

**Run211** の派生同期は、`Subscriber Decision Brief Sync` → `Member Presentation Sync` の順序を守る。`Inventory plan` はwrite fan-outを起こさず、Inventory Bootstrapのapplyだけを派生write対象にする。

Scheduled Dailyは現在 **`Daily Intelligence & Content Pipeline [PAUSED]`** としてhard-PAUSEDである。この間、`Subscriber Decision Brief Sync` の実在するworkflow_run上流は **`Daily Intelligence & Content Pipeline [ONE-SHOT]` + `Subscriber Inventory Bootstrap`** のみとし、Inventoryは`[apply]`だけをwrite fan-out対象にする。`Note Ready Article Sync` はONE-SHOTのみを上流にする。PAUSED stubや存在しない将来aliasをlive triggerとして残さない。Scheduled Dailyを明示的に再開する場合、その時点の実在するworkflow名を同一のreviewed changeで戻す。

**Run217** はCommerce/Onboarding履歴として保持し、Run218/220/221の後続Authorityを明示する。Digestを販売価値として案内する以上、**Digest自動生成が停止中でも**、人間運用を含めて会員へ約束したDigestを無言で消さない。自動生成停止を「Digest提供停止」と読み替えない。

---

## 3. Decision Brief / Decision Update 契約 — Run256

Decision Briefは静的な「今月のおすすめ一覧」だけにしない。

- 今月の主要候補を3〜7件へ絞る。
- `使う / 試す / 待つ / 避ける` の判断を出す。
- 仕事への意味、確認事項、次の一手を短く示す。
- **仕事上の判断を変えるmaterial changeが存在する場合、少なくとも1件は具体例をBrief本文へ出す。** 一覧リンクだけで代替しない。
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
- **1回目のHTTP 503** を観測した場合は既存cooldown契約に従う。
- `Reader Value repair` の追加消費を既存budget外へ拡張しない。

詳細は `GEMINI_QUOTA_SETUP.md`、current runtime code、Google AI Studio Rate Limitsを正本とする。

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
- Public releaseは**human-only**。自動化はprivate draftまで。

### Eyecatch

Run181 currentを基準とする。

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
- CI greenだけで本番反映完了としない。実Notionの見出し、順位、copy、source preservationを直接監査する。
- Physical API hostとlinked viewsの役割を分離し、Run221のhosting boundaryを維持する。

Run250–256で確立したproduct presentation:

- Run250: initial paid-product presentation overlay
- Run251: legacy fixed shortlist retirement
- Run252: `__main__` production script-entrypoint authority
- Run253: Work-First correction
- Run254: unnecessary first-person removal
- Run255: context-safe / natural neutralization
- Run256: concrete Decision Update + documentation reconciliation

### Member表示順

会員向け詳細は既存canonical値を使い、原則として次を表示する。

- `これは何？`
- `いま、どうする？`
- `仕事で使える場面`
- `仕事への意味（Business Impact）`
- `なぜ今見る？`
- `使う前に確認すること`
- `試すときの次の一手`
- material changeがある場合 `Decision Update｜判断を変える必要がある？`
- 公式・一次情報

Source score / Decision / Evidence / Deep Tech分類を顧客適合のために改変しない。ICP relevanceはNavigation-only。

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
- Public note公開はhuman-only。
- 外部サービス状態を推測で補完しない。
- 成功していない処理を成功扱いしない。
- CI greenは必要条件であり、Production実物監査の代替ではない。
- 本番変更は小さく、回帰可能にし、Source/Evidence/Decisionを保護する。

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
- 関連unit tests / full pytest
- Production Notion direct audit（Member UI変更時）
- Public surface direct audit（note/article変更時）

特に表示ロジックでは、テストが緑でも次を反証する。

- 実行中moduleとimport moduleのAuthorityずれ
- stale bodyをcurrentと誤認
- 文字列置換による不自然な日本語
- old fixed shortlistの復活
- Source score / Evidence / Deep Techの意図しない変異

Workflow変更では、さらに次を反証する。

- `run:` / `- run:` が削除済みrepository-local scriptを指していないか
- `python -m unittest tests.*` が実在するmoduleか
- `uses: ./...` / `- uses: ./...` のlocal actionが実在するか
- `workflow_run.workflows` が実在するtop-level workflow nameか
- static `gh workflow run` targetが実在するか
- duplicate workflow nameによる曖昧性がないか

---

## 10. 現在の商業優先順位

利益に近い順に判断する。

**顧客需要 → 売れるか → 継続するか → 粗利 → 自動化 → 技術的完成度**

現在の優先順位:

1. Paid Product / LP / Offerの整合
2. 実有料顧客10人の獲得
3. 初月利用・継続理由の観測
4. Decision Update / Work Actionの価値検証
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

- 現行仕様は読みやすく保つが、active runtime / Fail-Closed / customer destination / quota safetyの保護契約を「古いから」という理由で削らない。
- 詳細な変更理由・反証記録は `docs/reference/RUNxxx_*.md` へ置く。
- 純粋な履歴説明は `docs/archive/` とGit履歴へ置く。
- current code/tests + 本書 + `PAID_PRODUCT_CONTRACT.md` の整合を保つ。
- Documentation Freshness Guardが要求するmarkerは、テストを通すための文字列ではなく、現在Productionが依存するoperational contractとして扱う。
- Run257のWorkflow参照修整・反証記録は `docs/reference/RUN257_WORKFLOW_REFERENCE_INTEGRITY.md` を正本とする。

**現在のPaid Product正本はRun256。**  
**現在のWorkflow Reference Integrity正本はRun257。**
