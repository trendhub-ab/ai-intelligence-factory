# AI Intelligence Factory 横断監査 — 2026-09-17

## 結果

現行mainを取得し、再現できた9件の契約不整合・不具合を修正した。品質Gate、Safety Cap、永続カウンタ、通常のProviderモデル集合、必須4 Source配分は維持した。実APIを使った記事生成、Notion書き込み、note下書き作成、公開は実行していない。したがって、この監査結果は実記事E2Eの成功証明ではない。

基準main: `c6bb452a9ea308b24564a090fb5821e973a1daad`（#379を含む）。Git tree: `160ed9250646740d8ddc046f90d198557fe786d0`。取得した1,029ファイルすべてのGit blob SHAを照合した。Python 591ファイル・6,098関数を静的調査し、Workflowと仕様書も横断した。変更は隔離した監査ブランチに限定した。

Superpowersのsystematic-debugging / test-driven-development / writing-plans / requesting-code-review / verification-before-completionを使い、呼び出し経路確認、失敗再現、根本原因修正、既存回帰試験の順で検証した。独立レビューで見つかったRescue初期化順序とXリダイレクトの指摘も再現してから反映した。

## 修正した再現可能な不具合

重大度Highは送信境界・Evidence・永続成功判定・正常なReady経路への影響、Mediumは運用失敗や検証結果の誤表示への影響として評価した。悪用やProductionでの実発生を推定したものではない。

| ID | 重大度 | 根本原因と再現 | 修正と維持した契約 |
|---|---|---|---|
| A01 | High | `production_pipeline._workflow_dispatch_mode`が未知modeを返し、不正eventを空modeへ変換する。`ful`等が検証レーンを選ばず通常Productionへ進む。 | 明示modeを既存4モードで検証。不正JSON・inputsを初期化前に拒否。有効な別Workflowのmodeなしevent、通常local / Syntheticは維持。 |
| A02 | Medium | Production入口のPending分岐が、引数を受け付けない`run_article_revalidation(..., pending_only=True)`を呼ぶ。Workflow専用入口との乖離でTypeError。 | 初期化前に既存`pending_retry_validation.main()`へ委譲。1記事・非永続・送信上限の既存レーンを共有。依存Guardにはこの制御入口だけの非Publication区分を登録。 |
| A03 | Medium | Article Revalidationが文字列・辞書のtruthinessを`accepted`と扱い、未知tuple statusを`rejected`と扱う。 | Pending Retryの既存非永続Classifierを共有し、未知結果は`unverified`に分離。品質合格、原稿返却、Ready保存を混同しない。`persist_results=False`を維持。 |
| A04 | High | 統合済みX候補は`source='X'`を保持するがPublication allowlistには存在せず、`note_ready_sync._source_state`で排除される。 | Xを任意の発見経路として共通Source・表示名・権利注記へ登録。原投稿はEvidence不可。一次情報URL、現行policy・原稿hash、eyecatch・下書き安全判定は維持。必須4 Source配分は変更しない。 |
| A05 | Medium | Content DB Source Guardが旧ProductHuntを必須とし、OfficialVendor / Xを検査しない。 | 共通Publication Source定義から必要enumを導出。現行schemaは合格し、各active Source欠落は不合格。旧余剰enumは既存互換性のため許容する。 |
| A06 | Medium | Technology / Subscriber / Member DBもSourceを引き継ぐが、Cross DB Guardは同じ旧Source集合を独立保持する。 | 共通Publication Source集合と既存`Unknown`を使用。ContentからMemberまで契約を一致させ、その他の型・Status・DB境界の検査は維持。 |
| A07 | High | Rescue fan-outのPython判定エラーを`|| exit 0`が吸収する。欠落・破損JSONが成功扱いになり、boolean `true`がReady 1とみなされる。 | Ready件数は非負の厳密な整数のみ許容。監査不正は失敗、有効な0は非起動、正数は既存GH_PATによるprivate-draft付きNote Ready Sync dispatch。実Workflow shellをfake ghで試験。 |
| A08 | High | Rescueが`pipeline.main()`の外側で先行し、後続のAudit / Style / Runtime / Funnel初期化と件数ゼロ初期化で記録・予算・Ready集計を消す。TOP_N一時減算にも後続集計が追随しない。 | 初期化後・Fresh取得前の明示hookへ移動し、Ready件数と候補順位をFresh / Backlogへ渡す。記事目標を変えず残枠で停止。Rescue 1 / Fresh 8 / Backlog 3、総12、最大1回Rescue送信を維持。 |
| A09 | High | 一次情報候補の取得先がXへredirect / adapter解決されても本文を受け取り、AuthorityがPRIMARY_SOURCE metadataを優先してEvidenceとして扱う。 | HTTP各redirectと最終URLでX / Twitter / t.coを拒否し、保存済みEvidenceのAuthorityでもDiscoveryを優先。DNS末尾`.`も正規化し回避を防止。不正IPv6 URLは従来どおり空取得として処理。通常の一次情報取得とSSRF検査を維持。 |

新規再現テスト: `tests/test_repository_audit_contracts.py`。既存テストの変更は戻り値の追加`unverified`、正式統合済みXのSource集合、Rescueの初期化後hookと共有記事目標に限定した。Gateを通すための期待値・閾値の緩和は行っていない。

## 調査した経路と境界

| 対象 | 確認内容・評価 |
|---|---|
| Production / Runtime layers | `production_pipeline`とcanonical layer順序、制御入口、Product Review子プロセス、非永続検証、Synthetic分岐。A01 / A02を修正。Runtime順序自体は変更しない。 |
| Provider Routing / Retry / Fallback | Run260 / 261 / 204 / 346 / 374、送信前チェック、永続・モデル別・総量上限、503 Circuit、送信済み失敗と送信前拒否の区分。Rescueの1回境界を維持。モデル集合や期限付き3.6復帰条件は変更しない。 |
| Screening / Source normalization | round-robin、必須4 Source、OfficialVendor、X一次情報キュー、Source ROI、既存URL排除、Stock保存成功後のDeep Dive。Xを必須配分には追加しない。 |
| Evidence / Decision | Authority / entity binding / ledger / Primary Source context / 数量・因果主張とDecision適格性。A09で原Xの取得・保存済み根拠判定の両境界を修正。 |
| Writer / Reader Repair / Quality | Run283 / 284 / 397等の数量修正・Recovery精度・Reader複数軸判定・Writer解析・repair送信上限。#379の非エンジニアaccess corroboration修正を含む基準mainで回帰検証。Gate閾値・repairの合否基準は変更しない。 |
| Ready / Publication | `publication_contract`、62 policy依存ファイル、現行policy / draft hash、品質metadata、eyecatch安全、stale queue reconciliation、Ready Sync。A04のSource通過もReady全体合格とは同一視しない。 |
| note非公開下書き | Ready→Note Ready Sync→明示dispatch→Private Draft guard / 本文render audit / eyecatch persistence。実ブラウザ操作・note writeは未実行。Workflow shellと既存Guard試験のみ。 |
| Notion保存契約 | Content / Evidence / Cross DB / Public DB / Member契約、公開API Authorityとview-first、Stock保存失敗、Article / Content Status混在。A05 / A06を修正。実schema読み書きは行っていない。 |
| Scheduled Daily / ONE-SHOT | PAUSED状態、許可mode、GH_PAT fan-out、独立Inventory経路、validationとReady保存の区分。A01 / A02 / A07修正。Daily・過去Recoveryは起動しない。 |
| Tests / Guards / CI | 全テストのbaselineと修正後差分、Hermeticity、Workflow参照、依存区分、Publication hashと品質workflow分離、旧Runテストの互換性。新規試験は外部送信境界を置換し実dispatcher / main / shell / classifierを実行。 |

## 残る監査指摘と今回の変更範囲

| 優先度 | 指摘 | 判断・次の検証条件 |
|---|---|---|
| Medium | 固定Runの手動回復・診断資産が残る。例: Run297–302、413 / 414 / 416 / 418 / 425のWorkflow。Repository cleanupの包括的な読み方と現物が一致しない。 | actor・Issue・command・確認文字列等で限定された個別経路であり、通常Production Authorityには追加しない。本監査では実行せず、旧Recoveryの再開も行わない。依存と必要性を個別確認して廃止する必要があり、推測で一括削除しない。 |
| Low | Acquisitionのtext変換、Notion rich-text helper、CIのPR本文区分、旧note診断に同等helperが複数ある。 | 完全一致だけでは契約の同一性を証明できない。例外・長さ制限・Unicode・公開本文の差異とpolicy hashへの影響を確認するまで統合しない。今回Source集合と非永続Classifierの重複は実証した範囲で解消。 |
| Low | `pipeline.main`の後段`len(deduped_repos) > MAX_SCREENING_CANDIDATES`は、前段の上限付きround-robinと非増加dedupeを前提とすると通常経路で成立しない。 | 防御的な互換分岐として残した。静的scanで同一scopeの重複defや無条件return後の文は検出しなかったが、動的にinstallされるwrapper全体の到達不能性を証明したものではない。 |
| Low | Rescue Ready件数は修正後の総Ready通知に含まれるが、Telegramの「試行」件数は従来どおりFresh Deep Diveのみ。Funnelは全試行を保持する。 | 送信数・Ready合否には影響しない表示範囲の相違。運用表示の変更には試行の定義を明示する必要があるため今回は変更しない。 |
| Unverified | 実Provider障害時の最新挙動、実Notion schema、実記事のGate合格、noteのDOM / セッション・下書き保存結果。 | Offline回帰だけでは証明できない。別途許可されたbounded live検証で確認する。API消費や外部書き込みを伴う検証は本監査に含めない。 |

Publication依存ファイルの変更によりpolicy fingerprintは変わる。過去Readyを新policyとして再認証・rebaseしない。既存のstale判定とreconciliationが正常に適用されることを回帰試験で確認する。Scheduled Daily PAUSEDは維持する。

## 検証記録

- 基準main: **2,663 tests PASS**、主要構造Guard 9件PASS。
- 最初の追加再現: **20 FAIL / 2 PASS**。追加Cross DB・Rescue初期化再現: **4 FAIL**。X本文混入とEvidence再現: **6 FAIL**。X末尾dotの追加再現: **6 FAIL**。不正URLの新規例外回帰: **1 FAIL**。失敗はいずれも外部APIなしで確認した。
- 新規回帰: **39ケース**。unknown mode、event破損、direct Pending、legacy return、X→Ready Source、Content / Member Source欠落、実mainの初期化順・件数・Artifact、X解決先とAuthority、DNS dot、不正URL、実Workflow shellのinvalid / zero / positiveを含む。
- 修正後全件・Guard・Synthetic smoke・self-testの最終結果は下記追記欄に記録する。
- 独立レビューではさらにRescue 1件 + Fresh 2件の実main経路をofflineで実行し、Ready合計3、候補順位2 / 3、記事目標3、使用数3 / 総上限12、正常な通知を確認した。
- ローカルはPython **3.12.3**とcached locked dependenciesを使用。Required CIのPython **3.11.16**はGitHub側で確認する。Pillowの既存`getdata()` deprecation warningはbaselineにも存在する。
- Gemini / Google / Groqの生成API・Apify送信0。Notion mutation0、note mutation0。ProductionのDaily / validation workflowは未起動。

### 最終結果

- 全件回帰: **2,702 PASS**（37.73秒）、既存Pillow deprecation warning 1件。
- 構造Guard: **14 / 14 PASS**。Integration、repository falsification、Notion access、Workflow reference、Run262 / 267 / 268 / 269 / 270 / 271 / 279 / 280 / 307 / 308。
- Compileall: **PASS**。`git diff --check`: **PASS**。
- 現行`production_pipeline.py`のSynthetic smoke: **30 / 30 PASS**、critical failures 0、Production write isolation true。
- Regression harness self-test: **PASS**。
- 最終独立レビュー: **102 focused tests PASS**。末尾dot・不正URL・正常一次情報の追加offline確認を含め、修正差分に新たなCritical / Important指摘なし。
- Publication policy hash: `31a380dd32b6c6dbeaca77a92cfa08cd330b23dcacbd6833ae2dc7db06071df2`。
- [PR #380](https://github.com/trendhub-ab/ai-intelligence-factory/pull/380)のコード変更commit `74febf786e913594cf9b0cb7b25e642a395a7ed0`: GitHub CI **6 / 6 SUCCESS**。実Notionを扱う2 jobはPR条件により**SKIPPED**。
- [Integration CI](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/35233406988): Python **3.11.16**、**2,702 PASS**（23.17秒）、Synthetic **30 / 30 PASS**をjob logでも確認。
- [Run269 acquisition smoke](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/35233406852): 公開一次情報の取得のみ。Vendor 11件とHackerNews候補20件を確認して**PASS**。公開changelogのネットワーク読み取りは行うが、生成Provider / Notion / noteにはアクセスしない。
- 最新headの最終CI状態はPRのChecksを正とする。この検証記録の追記は文書のみで、検証済みProductionコードは変更しない。
