# AI Intelligence Factory — 現行Production仕様

最終更新: 2026-09-06  
Production Source of Truth: **`main`**  
Paid Product Baseline: **Run255 — Work-First / Natural Neutral-Subject Decision Intelligence**  
Paid Product Contract: **`PAID_PRODUCT_CONTRACT.md`**  
Article Production Baseline: **Run249 + current article-quality stack**  
Eyecatch Baseline: **Run181 current**  
Pipeline Modularization Baseline: **Run245**  
Repository Organization Baseline: **Run246**

> この文書は「現在のProductionで何を守るか」だけを短く示す。旧Runの詳細は `docs/reference/` とGit履歴で監査し、現在挙動を旧文書から推測しない。

## 0. 参照優先順位

1. `main` の実行コード・テスト・GitHub Actions
2. 本ファイル
3. `PAID_PRODUCT_CONTRACT.md`
4. `README.md` / `NOTION_ACCESS_POLICY.md` / `GEMINI_QUOTA_SETUP.md` 等の領域別Operator契約
5. `docs/reference/` の現行領域別仕様
6. `docs/archive/` とGit履歴

領域別の詳細が本書より新しい場合でも、Productionコード・テストを最終Authorityとする。

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

正規会員入口:
- Home Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`

正規Member Presentation DB:
- Database ID: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Data Source ID: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`

2026年9月 Decision Brief:
- Page ID: `3d0479ff-dca9-81de-b614-fef528d2f32c`

AI活用判断シート:
- Page ID: `3d3479ff-dca9-8119-b0d8-c014b068fe82`

物理APIホストと会員ナビゲーションを同一視しない。旧Member DB / 旧Data Sourceは監査用に隔離し、会員入口へ戻さない。詳細なアクセス境界は `NOTION_ACCESS_POLICY.md` を正本とする。

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

ただし `自分だけ / 少人数 / チーム` のように主体差が意味を持つ場合は残す。

中立化より**自然で意味が保たれる日本語**を優先する。`自社`を機械的に一律置換しない。

Run255で禁止した例:
- NG: `自社AI` → `利用環境AI`
- OK: `自社AI` → `利用中のAI`
- OK: `自社案件` → `対象業務`
- OK: `自社要件` → `利用条件`
- OK: `自社コード` → `独自コード`
- OK: `自社環境` → `利用環境`

安全な意味保持置換ができない場合、canonical表現を無理に崩さない。

---

## 3. Decision Brief / Decision Update 契約

Decision Briefは静的な「今月のおすすめ一覧」だけにしない。

- 今月の主要候補を3〜7件へ絞る。
- `使う / 試す / 待つ / 避ける` の判断を出す。
- 仕事への意味、確認事項、次の一手を短く示す。
- **仕事上の判断を変えるmaterial changeが存在する場合、少なくとも1件は具体例をBrief本文へ出す。** 一覧リンクだけで代替しない。
- material changeがない月は、無理に変化を作らず **「重要な判断変更なし」** を価値として示す。
- 生の `82 → 91` を継続課金価値の中心にしない。何が変わり、判断を変える必要があるかへ翻訳する。

2026年9月の具体例:
- `FlowiseAI/Flowise` — 公式GitHubがArchived。新規AIワークフロー基盤としてはAVOID、既存構成の保守・移行判断に限定。

Decision Updateは「Changed / New / Unchanged-important」を扱えるが、個別Watchlistや通知パーソナライズはPMF前に実装しない。

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

---

## 5. Gemini / Provider契約

- 基本はGemini Free Tier運用。
- RPD/RPM/TPM、Retry Budget、安全弁を超えて無理に実行しない。
- API枯渇・quota不明時は推測で実行しない。
- Geminiは記事生成等の限定された生成担当であり、主要な設計判断・コード判断のAuthorityにしない。
- Geminiの生成結果はEvidence / tests / 別ロジックで検証する。
- ZERO-provider-callで可能な表示・監査・移行はZERO-provider-callを優先する。

詳細は `GEMINI_QUOTA_SETUP.md` とcurrent runtime codeを正本とする。

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

Run250–255で確立したproduct presentation:
- Run250: initial paid-product presentation overlay
- Run251: legacy fixed shortlist retirement
- Run252: `__main__` production script-entrypoint authority
- Run253: Work-First correction
- Run254: unnecessary first-person removal
- Run255: context-safe / natural neutralization

---

## 8. 運用契約

- **Daily workflowはPAUSED。**
- Production実行は明示的なONE-SHOT / workflow_dispatchを基本とする。
- Public note公開はhuman-only。
- 外部サービス状態を推測で補完しない。
- 成功していない処理を成功扱いしない。
- CI greenは必要条件であり、Production実物監査の代替ではない。
- 本番変更は小さく、回帰可能にし、Source/Evidence/Decisionを保護する。

---

## 9. 回帰・反証契約

最低限、変更領域に応じ以下を通す。

- Repository-wide Falsification Guard
- Integration Reconciliation CI
- Synthetic Regression
- Notion Access Policy Guard
- Cross DB Contract Guard（該当時）
- 関連unit tests / full pytest
- Production Notion direct audit（Member UI変更時）
- Public surface direct audit（note/article変更時）

特に表示ロジックでは、テストが緑でも次を反証する。
- 実行中moduleとimport moduleのAuthorityずれ
- stale bodyをcurrentと誤認
- 文字列置換による不自然な日本語
- old fixed shortlistの復活
- Source score / Evidence / Deep Techの意図しない変異

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

このファイルは、商品・Production契約が変わったRunで更新する。

- 現行仕様は短く保つ。
- 詳細な変更理由・反証記録は `docs/reference/RUNxxx_*.md` へ置く。
- 過去仕様を本ファイルへ積み増して肥大化させない。
- 古い説明と矛盾した場合は、current code/tests + 本書 + `PAID_PRODUCT_CONTRACT.md` の順で解消する。

**現在のPaid Product正本はRun255。Decision Briefの具体化ルールはRun256 documentation reconciliationで追加。**
