# AI Intelligence Factory — 現行Production仕様

最終更新: **2026-09-13**  
Production Source of Truth: **`main`**  
Canonical Specification: **本ファイル**  
Current Repository Baseline: **2026-09-13 post-cleanup / Gemini-based Production restored / retired provider & recovery surfaces removed**  
Core Reliability Baseline: **Run209 — Gemini timeout RPD fail-closed**  
Documentation Governance Baseline: **Run267 — Current Canonical Contract Sync / Required-Check Governance**  
Article Model Routing Baseline: **Run261 — live `_call_deep_dive_pool` routing / Gemini 3.7 Primary / Gemini 3.8 Quality Rescue**  
ONE-SHOT Downstream Fan-out Baseline: **Run261 — explicit GH_PAT-authenticated workflow_dispatch**  
Integration Determinism Baseline: **Run263 — Hermetic / Locked / Zero-Provider Integration CI**  
Standalone Synthetic Baseline: **Run264 — Hermetic Synthetic Regression**  
Dependency Compatibility Baseline: **Run266 — Pillow 12.1+ Production Floor / <13 Upper Bound**  
Required PR Check Governance Baseline: **Run267 — required contexts on every PR to main**  
Eyecatch Baseline: **Run183 — Run181 Visual Balance / Run182 Conclusion Emphasis / Run183 Emphasis Scale**  
Business / Source Strategy Baseline: **Run268 — Four-Source Intelligence / OfficialVendor East-West Coverage**  
Acquisition Precision Baseline: **Run269 — Live Acquisition Precision / 11-Vendor Structured Smoke**  
Member Surface Baseline: **Run307 — Generic Use-Decision Member Surface / Run270 compatibility overlay**  
Paid Product Messaging Baseline: **Run307 — self-development + work use + optional proposal**

> 本書は「現在のProductionで何を守るか」を示す唯一のcanonical仕様書である。Run番号単位の追補、過去の検証レポート、Recovery文書、`docs/reference/`、`docs/archive/`、Git履歴は設計根拠・履歴として参照できるが、**本書と`main`の実装を上書きするAuthorityではない**。

---

## 0. Authority / 参照優先順位

現行仕様の優先順位は次の通り。

1. **`main` の実行コード・テスト・GitHub Actions**
2. **本ファイル `AI_Intelligence_Factory_最終仕様書.md`**
3. `PAID_PRODUCT_CONTRACT.md`
4. `README.md` / `NOTION_ACCESS_POLICY.md` / `GEMINI_QUOTA_SETUP.md` 等の領域別Operator契約
5. `docs/reference/` の現行領域別資料
6. `docs/archive/`、過去Run追補、検証レポート、Git履歴

重要原則:

- 過去Runの文書が現行コードと矛盾する場合、**現行`main`を正**とする。
- Recovery・診断・Shadow・移行用の過去文書をProduction仕様として復活させない。
- Productionコード、Fail-Closed Guard、Evidence契約、安全契約を文書整理の都合で弱めない。
- 新しい仕様変更をProductionへ統合した場合は、本書を同時に更新する。

---

## 1. 2026-09-13 Production Baseline

2026-09-13時点の正式方針を以下で固定する。

### 1.1 Provider / Model Routing

- **ProductionはGeminiベースの既存ロジックを正式系統とする。**
- Groqとの共存・Provider併用構成は終了した。
- Groq/Qwen Shadow、Live Shadow、共存用Providerコード、関連Workflow・fixture・testはProductionから撤去済み。
- Groq系を自動的に再導入しない。
- Gemini以外のProviderへ再移行する場合は、別途正式な設計変更・比較検証・承認を必要とする。
- **Google/Gemini APIを検証・診断目的で勝手に消費しない。明示的に許可された実行だけを行う。**

Gemini系の既存安全契約は維持する。

- timeout / RPD fail-closed
- bounded transient recovery / cooldown
- 503連続時のrun-local circuit
- Free Tier前提の利用量保護
- Provider障害を品質不合格と混同しない

### Run261 article model routing

現行のArticle Model RoutingはRun261契約を維持する。

- live entrypointは **`_call_deep_dive_pool`**。
- Primaryは **`gemini-3.7-flash`**。
- Quality Rescueは **`gemini-3.8-flash`**。
- これはGroq共存を意味しない。GeminiベースProduction内部の現行routing contractである。
- 詳細な成立経緯は `docs/reference/RUN261_LIVE_ROUTING_AND_FANOUT_REPAIR.md` を参照する。

### 1.2 X logic

- X取得・監視・候補化ロジックは、今回のRepository cleanupとは別系統として保持する。
- X系の仕様・コードを、Groq撤去やRecovery整理の理由で変更しない。
- X系をProductionへ統合・変更する場合は、その時点で別途検証する。

### 1.3 Repository cleanup

2026-09-13のRepository整理で、次のカテゴリを現行Productionから撤去した。

- Groq/Qwen coexistence / shadow provider surfaces
- current-policy Ready recovery専用surface
- Ready metadata rebase専用surface
- Run361〜365の固定Recovery・固定診断surface
- 固定ID・固定SHA・固定期間に依存する一時Recovery資産
- それら専用のWorkflow / trigger / test / fixture

一方、以下は**Recovery起源でも現在の一般安全機構として有効なため維持する**。

- Ready provenance
- Publication Contract
- Reader Gate
- Evidence safety
- rate-limit protection
- Japanese surface integrity / 日本語破損防止
- Reader Repair conflict prevention
- local repair protection
- fail-closed workflow reference protection

### 1.4 45記事Recoveryの扱い

過去の45記事Recoveryタスクは終了済みとする。

- 45件すべてを復旧する継続タスクとして扱わない。
- **33件未復旧の状態をもって終了**している。
- 旧Recovery workflow、旧固定IDツール、旧rebase処理を再実行しない。
- 未復旧33件を今後の開発・Daily・品質改善の前提条件にしない。
- 将来、個別記事を再利用する場合は「過去Recoveryの続き」ではなく、現行Publication Contractで新規に評価する。

---

## 2. Production Execution Contract

### 2.1 Scheduled Daily

- Scheduled Dailyは現在 **PAUSED** を正とする。
- 自動Dailyを勝手に再開しない。
- Dailyを実行する場合は明示的な運用判断を必要とする。

### 2.2 Manual ONE-SHOT / ChatOps

現行ChatOpsのProduction入口は、現在の`main`実装をAuthorityとする。

現行の主要モード:

- `article_validation`
- `pending_retry_validation`
- `full`

旧Recovery専用command、Run361〜365専用command、Groq専用commandを復活させない。

ONE-SHOTという名称自体はRecovery専用ではなく、現行の汎用手動実行契約として保持する。

### Run261 ONE-SHOT downstream fan-out

成功したONE-SHOTのdownstream fan-outは、受動的なONE-SHOT `workflow_run` chainingではなく、明示的なworkflow dispatchをAuthorityとする。

- auth: **`${{ secrets.GH_PAT }}`**
- target: `note-ready-sync.yml`
- target: `subscriber-decision-brief.yml`
- target: `cross-db-contract-guard.yml`
- 3 target workflowはmanual `workflow_dispatch`可能であり、ONE-SHOTをpassive subscribeして二重writeしない。
- Subscriber Decision Brief側の独立したInventory apply経路は維持する。
- 詳細は `docs/reference/RUN261_LIVE_ROUTING_AND_FANOUT_REPAIR.md`。

### 2.3 Production entrypoint

- `production_pipeline.py` を安定Production entrypointとして扱う。
- Provider / runtime / safety layerのインストール順を勝手に分岐させない。
- 過去Recovery用入口からProductionへ迂回しない。

---

## 3. Required CI / Dependency Contract

現在のDocumentation Contract Freshness正本はRun267。

Production依存関係:

- Production Pillow range: `Pillow>=12.1.0,<13.0.0`
- CI known-green pin: `Pillow==12.3.0`
- CI constraints: `requirements-ci-constraints.txt`

mainへのPRで必要なrequired context:

- `zero-api-regression`
- `falsify-all-tracked-surfaces`
- `notion-access-policy`

**required status checkに指定されたWorkflowは、対象PRで必ずcheck contextを生成できなければならない**。そのためrequired workflowの`pull_request`に **pull_requestのpath filterを置かない**。

現行Integration/Documentation契約の参照:

- `docs/reference/RUN263_INTEGRATION_HERMETICITY_AND_STABILITY.md`
- `docs/reference/RUN264_STANDALONE_SYNTHETIC_HERMETICITY.md`
- `docs/reference/RUN267_CANONICAL_SPEC_SYNC.md`

---

## 4. Publication / Ready Contract

Readyは単なるステータスではなく、**現行Publication Policyを満たしたことを証明するprovenance付き状態**である。

維持する契約:

- Publication policy fingerprint
- manuscript fingerprint
- Ready caption / Ready block provenance
- current policyとの一致確認
- Reader Gate
- Evidence / source boundary
- Japanese surface integrity
- local repair protection
- Reader Repair conflict prevention

### Policy fingerprint

`PUBLICATION_POLICY_FILES` に含まれるpolicy fileの内容が変われば、policy fingerprintも変わり得る。

したがって:

- 過去のReadyが新しいpolicy fingerprintと一致しない場合、**staleと判定されること自体は正常動作**。
- stale Readyを理由に旧Recovery機構を復活させない。
- policy変更後の再認定は、現行Publication Contractに従う。
- provenanceを偽装してReadyを維持しない。

---

## 5. Article Quality / Eyecatch Contract

記事品質は「Gateを通すこと」ではなく、読者にとって理解しやすく、面白く、判断に使えることを目的とする。

維持する原則:

- 事実・出典・Evidenceを壊さない。
- 中学生〜非エンジニアでも核心を理解できる日本語を目指す。
- 報告書調・AIテンプレート調へ寄せすぎない。
- 導入、Reader Tension、Discovery、Concrete Consequence、Explanation Bridge、Editorial Point of Viewを、固定個数のスタイルGateではなく読者価値のために使う。
- Reader Repairは事実を創作しない。
- 日本語の修復で意味・主語・因果・数値・条件を勝手に変えない。
- Evidence不足を文章力で隠さない。
- Provider障害と記事品質不良を分離する。

無料noteの品質を意図的に落として有料転換を作らない。無料記事自体が集客・信頼形成の商品入口である。

Eyecatchの現行baselineはRun183。Run181 Visual Balance → Run182 Conclusion Emphasis → Run183 Emphasis Scaleの順序を維持する。

---

## 6. Intelligence Source Contract

Business / Source Strategy BaselineはRun268、取得精度はRun269を正とする。

Productionで同格に扱うactive Source:

1. **GitHub = 実装動向**
2. **ArXiv = 技術の先行動向**
3. **HackerNews = 市場・エンジニア反応**
4. **OfficialVendor = 商用利用に直結する一次情報**

**Product HuntはRun268からProductionのactive Sourceではない**。

OfficialVendorはベンダーごとにSource枠を分裂させず、1 Sourceとして扱い、metadataでvendor / regionを識別する。

主要vendorは少なくとも OpenAI / Anthropic / Google Gemini / **Alibaba Qwen** / DeepSeek / ByteDance Doubao・Seed / Moonshot AI Kimi / Zhipu AI GLM / MiniMax / Baidu ERNIE / **Tencent Hunyuan** を含む。

地域・ブランドだけで加点減点せず、一次情報・Evidence・実務影響・Decision契約で評価する。

Run268詳細: `docs/reference/RUN268_BUSINESS_SOURCE_STRATEGY.md`

### HackerNews Precision — Run269

- AI関連取得は広すぎるraw queryではなく、**exact token / exact phrase**を用いて精度を守る。
- lookbackは現行Run269契約の**30日**。
- OfficialVendorはcurrent-state取得で `structured_current_state` を優先し、必要時に `page_fallback` を使う。
- live smokeはprovider/model call、Notion write、Production DB write、publication actionを行わない。

Run269詳細: `docs/reference/RUN269_LIVE_ACQUISITION_PRECISION.md`

---

## 7. Business / Product Contract

AI Intelligence Factoryはnote事業そのものではない。

noteは低コストの集客・SEO・信頼形成チャネルの一つであり、有料商品は**Decision Intelligence**である。

中心価値:

> **「このAI、使える！」を、根拠付きで判断できる。**

商品構造:

1. **無料note** — 知る・面白く理解する
2. **Decision Brief** — 重要変化を短時間で把握する
3. **Decision Intelligence** — 比較・Evidence・リスク・履歴を確認する
4. **Decision / Action Asset** — 試す・導入する次の一手へ落とす

標準価格は現行方針として **月額1,980円** を維持する。

初期の商業検証は、広告費を大きく使う前に「知らない実利用者が実際に支払う」ことを優先する。

現在のMember Surface正本はRun307。Run270の**Proposal-First Member Surface**は歴史的互換層として保持し、Run307がその後段で現行Use-Decision表示を提供する。

参照:

- `docs/reference/RUN270_PROPOSAL_FIRST_MEMBER_SURFACE.md`
- `docs/reference/RUN307_GENERIC_USE_DECISION_PRODUCT.md`

---

## 8. Paid Member Production Surface

既存のPaid Member契約は維持する。

主要Authority:

- Run211 — derived product sync ordering
- Run218 — member navigation / UI
- Run219 — non-engineer human-language UI
- Run220 — canonical member DB destination
- Run221 — API-host isolation / member-view separation
- Run270 — Proposal-First Member Surface compatibility layer
- Run307 — Generic Use-Decision Intelligence / paid product messaging

Run番号は各領域の成立履歴を示すものであり、**Factory全体の最新バージョン番号ではない**。

現行Member Surfaceでは次を守る。

- PC-first
- live Top3
- fixed cardをAuthorityにしない
- Decision/EvidenceをPresentation都合で書き換えない
- canonical member DBへfail-closedで同期する
- legacy DBをProduction destinationへ戻さない
- member-facing languageは非エンジニアでも理解できる日本語を使う

### Run271 — Member Body Delta Sync

Member body同期はRun271契約を維持する。

- `MEMBER_BODY_CHANGED_SINCE` を使うdelta pathを維持する。
- 基準は**前回成功**した同期runの開始時刻。
- checkpointが欠ける、再実行、または契約不一致時はfull scanへfail-safeする。
- `sentinel` が契約不一致を検出した場合は部分同期で誤魔化さない。

個別のDatabase ID / Page ID / onboarding note / purchase funnel等の運用値は、現行`main`と領域別Operator契約を正とする。

---

## 9. Safety / Cost / Operations

最優先する運用原則:

- 無料枠・低コストを優先する。
- 不必要なmodel callを増やさない。
- Google/Gemini APIを診断や確認だけのために勝手に消費しない。
- Notion write、note write、公開処理を検証の副作用として行わない。
- Dry-run / zero-provider / deterministic validationで確認できるものは先にそれで確認する。
- 公開・DB更新・Provider消費は、目的に必要な場合だけ行う。
- Fail-Closedを安易なFail-Openへ変更しない。

---

## 10. Documentation Governance

### 10.1 唯一の現行仕様入口

今後、Factory全体の現行仕様を確認するときは**本ファイルを最初に読む**。

Run単位の「仕様追補」「監査結果」「Recovery指示書」は、現行仕様の入口にしない。

### 10.2 過去Run文書の扱い

過去Run文書は削除しなくてもよいが、意味は以下に限定する。

- 設計理由
- 過去の障害記録
- 検証結果
- 回帰防止の由来
- 監査証跡

過去文書に書かれたProvider、Recovery手順、固定ID、固定SHA、旧Workflow名が、現在も有効だと推定してはならない。

### 10.3 更新ルール

次の変更を`main`へ統合した場合は、本書を同じ変更単位で更新する。

- Provider / model routing変更
- active Source変更
- Publication / Ready契約変更
- Quality Gate / Reader Gateの意味変更
- ChatOps / Daily入口変更
- Paid Member destination変更
- Production DB authority変更
- Repository全体の大規模整理
- 事業・価格・商品構造の正式変更

単なる内部リファクタリングやテスト追加は、本書の契約を変えない限りRun履歴を追加しない。

---

## 11. 2026-09-13 廃止事項 — 誤復活防止

以下を現行Production仕様として扱わない。

- Groq + Gemini coexistence
- Groq/Qwen shadow provider
- Groq technology comment shadow live
- current-policy Ready recovery workflow
- Ready metadata rebase workflow
- Run361 byte-preserving recovery
- Run362 recovery inventory / provenance auditをProduction復旧入口として使うこと
- Run363 Gemini 3.8 temporal diagnosticを常設Production機能として使うこと
- Run364 / Run365 fixed-ID historical rebase
- 45記事Recoveryの継続
- 「残り33記事をすべて復旧する」ことをProduction backlogとして扱うこと

ただし、これらの過程で得られ、現在の一般安全機構へ昇格したprovenance / publication / reader / evidence / Japanese integrity / repair protectionは維持する。

---

## 12. Current-state summary

2026-09-13時点のFactoryは、次の状態を正式な基準とする。

- **Production:** Geminiベース既存ロジック
- **Groq coexistence:** 終了
- **X logic:** 保持、今回の整理対象外
- **45-article Recovery:** 終了、33件未復旧のまま再開しない
- **Scheduled Daily:** PAUSED
- **Manual execution:** current ONE-SHOT / explicitly dispatched workflows
- **Publication safety:** provenance + current policy + Reader/Evidence/Integrity guardsを維持
- **Repository:** Recovery専用・Groq共存専用surfaceを撤去済み
- **Documentation Authority:** `main` → 本書 → 領域別契約 → reference/archive

この状態から次の開発を開始する。過去RecoveryやGroq共存フェーズを暗黙の前提として引き継がない。
