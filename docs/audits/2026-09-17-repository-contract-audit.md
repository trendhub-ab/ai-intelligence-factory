# AI Intelligence Factory 横断監査 — 2026-09-17

## 結果

**統合後の最新確認:** PR #380は`merged=true`、承認対象headは`a00bcab4a394a29664929c8a510ab51f4ee4b2bd`。確認したmainは`9296c90a2f4c7953b884800ff3edda177f5cb57a`、treeは`a1056e509930fdef9a2cba102ae673f0da6ffd37`。承認headとmainのtreeは同一、追加ファイル差分0。mainの1,023 blobをローカルと照合した。以下の旧2,702件記録は初回監査時点の履歴であり、最新結果は末尾の「統合後検証」を正とする。

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
| Medium | 固定Runの手動回復・診断Python・test・仕様資産が残る。Run297–302の8 WorkflowとRubyGemsの5 WorkflowはPR #380で退役済み。 | 退役理由・trigger・副作用・履歴は`2026-09-18-retired-one-shot-workflows.md`を参照。統合後の全文検索・import graph棚卸しは`2026-09-17-retired-assets-inventory.md`。14専用Pythonすべてにtestまたは別helperから参照があり、削除条件未成立。12専用test・6仕様文書も回帰・履歴資産として保持。追加削除0。 |
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

## 統合後検証（継続監査）

### GitHub mainとCI

- [PR #380](https://github.com/trendhub-ab/ai-intelligence-factory/pull/380): `merged=true`、`draft=false`、2026-09-17 16:22:17 UTC統合済み。再統合操作は不要だった。
- 統合main: `9296c90a2f4c7953b884800ff3edda177f5cb57a`。親は基準main `c6bb452…` と承認head `a00bcab…`。承認headとの比較はファイル差分0、tree同一。
- mainのpush CIは最初5成功 / 1失敗。PRでskipされたlive-schema検査により、Technology DBの`情報源 missing=OfficialVendor,X`を初めて実証した。Content DB検査は成功していた。PRのGreenをlive schema適合の証明としない。
- [Cross DB CI run 35246162966](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/35246162966)のattempt 2は成功。job `105292776611`ログでContent DB enum/type、Technology / Decision History DB enum、Evidence Ledger type/Source healthの合格を確認した。Subscriber/Monthlyは運用設定でdisabled、Member jobはこのeventではskip。disabled/skipをlive E2E成功として扱わない。
- [main regression run 35246162952](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/35246162952): Python 3.11.16、**2,705 PASS**（23.23秒）、既存warning 1。Workflow Reference `35246162976`、Repository Falsification `35246162923`、Notion Access `35246162861`、Note Ready Sync `35246162881`も成功。修復後にmainの6実行すべて成功を確認した。

### A10 — schema移行とMember provisioningの不一致

既存Technology / Subscriber / Memberの3 data sourceを事前取得し、旧Source選択肢だけが存在することを確認した。`OfficialVendor` / `X`を各schemaへ追加した。既存`ProductHunt` / `Unknown`を除去せず、事後取得で全既存option ID・色が維持され、Source以外の全schema定義が同一であることを比較した。記事行、本文、Posting Stateは変更していない。

`provision_member_presentation_db._properties_schema()`も旧Source集合を生成していたため、新規DB作成を許可する明示bootstrap経路で同じGuard不合格を再発させる根本原因が残っていた。`tests/test_member_presentation_resolution_guard.py`へ実schema生成→Notion応答型の付与→既存Cross DB enum検査を通す試験を追加し、修正前に`OfficialVendor,X`欠落で**1 FAIL**を確認した。修正後は`ACTIVE_PUBLIC_SOURCES`から不足Sourceだけを補い、旧option順序・色とUnknownを保持して合格する。通常Productionのcanonical DB固定・自動作成禁止、schema GuardやGateは変更しない。

このbootstrap修正はPublication fingerprint対象外。policy hashは引き続き`31a380dd32b6c6dbeaca77a92cfa08cd330b23dcacbd6833ae2dc7db06071df2`で、既存Readyを再認証しない。

### 残存資産・重複・表示

- 退役済み13 Workflowはmainに存在しない。8 GenRec / 5 RubyGemsの退役GuardとGenRec ingress GuardをFull Regressionで実行した。棚卸し詳細は[残存資産参照調査](2026-09-17-retired-assets-inventory.md)。14専用Python、12専用test、6仕様文書を保持し、追加削除0。Run298 helperはRun418/425からも参照され、Run413は共通Reader Summary testが使用する。参照ゼロを作る目的でtestや仕様を削除しない。
- Acquisition `_response_text`3種はHTTP例外を伝播し、明示text優先、bytesはUTF-8 replacement decode、文字数制限なし。Unicode/不正bytes/空text等の代表fixtureで同じ結果を確認した。ただし各呼出先のドメイン・材料選別・日付/モデル状態判定は異なり、3 moduleがpolicy hash対象である。実証された不具合がなく、統合によるfingerprint移行コストを避け保持した。
- context/noteの`_rt`はstrip後2,000 Python文字で切る。Member `_rt`は`_norm`が`<br>`を改行へ、連続space/tabを1 spaceへ、3連以上の改行を2連へ変換してから切る。代表fixtureで差異を確認した。Notion JSON型は同じでも公開表示契約を同一視せず保持する。text読取helperもtitle/rich_text/formulaの優先順は共通だが、schema別の呼出境界を保持する。
- CI PR本文partitionは同じ正規表現・tuple返却を持ち、代表LF fixtureは一致した。任意YAML/CRLFまで同一契約の改善が必要な根拠はなく、Guardごとの診断を維持する。旧note `_visible_count`はcount例外で0/0、最大40、visibility timeout 250ms、要素例外はskipする。同じ本体でもProductionの永続画像判定と履歴DOM診断の外側判定は異なるため統合しない。
- Screening capは基底round-robinが上限までしか返さず、Run268/367も最終的に同じlimitへ委譲する。legal filterとdedupeは増加しないため、現在の通常経路では後段capは成立しない。将来wrapperや入力契約変更に備える防御コードとして保持し、静的推測だけで削除しない。
- 表示定義: Telegramの`Ready`はRescue/Fresh/Backlogの保存済み合計、同文中の`試行`はFresh候補loopへ入った件数。Funnelの`deep_dive_candidates_attempted`はrecordされた全候補処理で、Evidenceで送信を回避した候補を含む。どちらもProvider request回数とは異なる。表示変更は品質不具合修正と混ぜず、定義を記録して保持した。

### 最新offline結果と外部操作

- 継続修正後: **2,706 PASS**（44.79秒）、既存Pillow warning 1。ローカルPython 3.12.3、cached test dependencies、pytestの外部network遮断を使用。統合済みmain snapshotの事前試験は**2,705 PASS**。
- Member/Cross DB/監査関連focused: **51 PASS**。Repository Falsification、Workflow Reference、Notion Accessを含む構造Guard **14 / 14 PASS**。compileall / diff check成功。
- 現行`production_pipeline.py`のSynthetic smoke: **30 / 30 PASS**、critical failures **0**、`production_write_isolation=true`。
- 継続修正の[PR #381](https://github.com/trendhub-ab/ai-intelligence-factory/pull/381)、コードhead `8898680d310b5d19600acb779e19047ed753e9bb`: CI **4 / 4 SUCCESS**。Workflow Reference単独Workflowはpath条件で起動しないが、Repository Falsification CI内のReference Guardと全件回帰で合格した。[Integration run 35248551079](https://github.com/trendhub-ab/ai-intelligence-factory/actions/runs/35248551079)のjob `105294840248`ログでPython **3.11.16**、**2,706 PASS**（17.22秒）、Production Synthetic **30 / 30 PASS**、critical 0、write isolation trueを確認した。独立レビューもfocused **51 PASS**、Critical/Important指摘なし。文書追記後の最新状態はPR Checksを正とする。
- 生成Provider / Gemini / Google / Groq / Apify送信 **0**。Notion connector取得 **7回**（接続identity 1 + schema事前3 + 事後3）、schema mutation **3回**（不足option追加のみ）。必要なlive確認はGitHubの失敗schema job再実行**1回**に限定した。CI自身のpublic API schema readはこのconnector7回に含めない。
- note mutation / 公開 / Daily起動 **0**。Dailyはscheduleなし・job hard-disabledのPAUSEDを維持。過去Run用Pythonは実行しない。
- 未検証: 実生成Provider障害・実記事Gate・note DOM/セッション/下書き保存、Member全行品質、任意の動的import。3 DBのSource enum事後比較は行ったが、disabled Subscriberとevent-skip Memberのlive全行E2E成功を意味しない。
- 次の最優先: 修復済みSource schemaを前提に、Member/Subscriberのview-first/read-only契約確認をboundedに行い、その後に試行表示をFresh候補・全候補・Provider送信へ明示分離する。旧資産削除を目的として回帰証拠を失わせない。

継続修正はreview PRで検証してmainへ反映する。上記full SHAは調査対象の統合mainを特定するものとし、文書自身のcommit SHAは自己参照せずGitHubの現行main refと最終統合ログを正とする。
