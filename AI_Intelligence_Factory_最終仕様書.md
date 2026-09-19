# AI Intelligence Factory — 現行Production仕様

最終更新: **2026-09-20**
Production Source of Truth: **`main`**  
Canonical Specification: **本ファイル**

> 本書は「現在のProductionで何を守るか」を示すcanonical仕様書である。過去のRun番号、検証レポート、Recovery文書、`docs/reference/`、`docs/archive/`、Git履歴は設計理由・監査証跡として参照できるが、現在の実装・安全契約を上書きするAuthorityではない。

---

## 0. Authority / 参照優先順位

現行仕様の優先順位は次の通り。

1. **`main` の実行コード・テスト・GitHub Actions**
2. **本ファイル `AI_Intelligence_Factory_最終仕様書.md`**
3. `PAID_PRODUCT_CONTRACT.md`
4. `README.md` / `NOTION_ACCESS_POLICY.md` / `GEMINI_QUOTA_SETUP.md` 等の領域別Operator契約
5. `docs/reference/` の領域別資料
6. `docs/archive/`、過去Run追補、検証レポート、Git履歴

重要原則:

- 過去資料が現行コードと矛盾する場合、**現行`main`を正**とする。
- Recovery・診断・Shadow・移行用の過去文書をProduction仕様として復活させない。
- Productionコード、Fail-Closed Guard、Evidence契約、安全契約を文書整理の都合で弱めない。
- 正式な仕様変更をProductionへ統合した場合は、本書を同じ変更単位で更新する。
- Run番号は履歴識別子であり、現行仕様のAuthorityやバージョン番号として使わない。

---

## 1. 2026-09-13 Production Baseline

### 1.1 Provider / Model Routing

- **ProductionはGeminiベースの既存ロジックを正式系統とする。**
- Groqとの共存・Provider併用構成は終了した。
- Groq/Qwen Shadow、Live Shadow、共存用Providerコード、関連Workflow・fixture・testはProductionから撤去済み。
- Groq系を自動的に再導入しない。
- Gemini以外のProviderへ再移行する場合は、正式な設計変更・比較検証・承認を必要とする。
- **Google/Gemini APIを検証・診断目的で勝手に消費しない。明示的に許可された実行だけを行う。**

現行Article Model Routing:

- live Deep Dive entrypoint: **`_call_deep_dive_pool`**
- cold-start順序: **3.6 → 3.5 → 3.7 → 3.8**。実運用はProvider Healthの成功履歴とrun-local circuitで並び替える。
- Quality Retryは利用可能なモデルを絞った後、最大2モデルとする。
- fallback: 現行`main`のrouting layerをAuthorityとする

期限付きProvider保護:

- ONE-SHOTのjob環境変数`AIIF_GEMINI36_BLOCK_UNTIL=2026-09-16T17:00:00+09:00`により、期限前はGemini 3.6とそのaliasを除外する。Product Review子プロセスにも同じ環境を引き継ぐ。
- 候補初期化・Provider Health再注入・Quality Retry・共通fallback・独立Product Review poolで除外し、最終SDK送信前にもquota予約より先に拒否する。
- 期限到達後の実行では除外は無効となり、Gemini 3.6は通常のArticle model setへ自動復帰する。恒久pool・モデル別RPD上限は変更しない。タイムゾーンなし・不正な期限は送信前に停止する。

Gemini系の安全契約:

- timeout / RPD fail-closed
- bounded transient recovery / cooldown
- 503連続時のrun-local circuit
- Free Tier前提の利用量保護
- Provider障害を品質不合格と混同しない
- Primary / Qualityの役割を意図せず同一化しない

### 1.2 X logic

- X取得・監視・候補化ロジック（`x_discovery`）およびインテリジェンス層（`x_intelligence`）はProductionリポジトリへ統合済み。
- 独立したモジュール設計および安全契約（`is_evidence=false`、ゼロプロバイダー/ドライラン安全、無許可の外部API消費防止）を維持する。
- 自動実行ワークフローは手動（`workflow_dispatch`）または独立した安全実行を前提とする。
- Xは任意の発見経路としてPublication Source契約に含める。投稿・`t.co`の本文はEvidenceに使わず、一次情報取得のリダイレクト先がXである場合も取得境界で遮断する。保存済み根拠のAuthority判定でもXのURLはDiscoveryとして扱う。

### 1.3 Repository cleanup

2026-09-13のRepository整理で、以下を現行Productionから撤去した。

- Groq/Qwen coexistence / shadow provider surfaces
- current-policy Ready recovery専用surface
- Ready metadata rebase専用surface
- 固定Recovery・固定診断surface
- 固定ID・固定SHA・固定期間に依存する一時Recovery資産
- それら専用のWorkflow / trigger / test / fixture
- historical documentation / prose locks that do not protect executable safety

一方、Recovery起源でも一般安全機構として有効なものは維持する。

- Ready provenance
- Publication Contract
- Reader Gate
- Evidence safety
- rate-limit protection
- Japanese surface integrity / 日本語破損防止
- Reader Repair conflict prevention
- local repair protection
- fail-closed workflow reference protection
- zero-provider / deterministic regression protections

### 1.4 45記事Recoveryの扱い

過去の45記事Recoveryタスクは終了済みとする。

- 45件すべてを復旧する継続タスクとして扱わない。
- **33件未復旧の状態をもって終了**している。
- 旧Recovery workflow、旧固定IDツール、旧rebase処理を再実行しない。
- 未復旧33件を今後の開発・Daily・品質改善の前提条件にしない。
- 将来、個別記事を再利用する場合は「過去Recoveryの続き」ではなく、現行Publication Contractで新規評価する。

---

## 2. Production Execution Contract

### 2.1 Scheduled Daily

- Scheduled Dailyは現在 **PAUSED** を正とする。
- 自動Dailyを勝手に再開しない。
- Dailyを実行する場合は明示的な運用判断を必要とする。

### 2.2 Manual ONE-SHOT / ChatOps

現行の主要モード:

- `article_validation`
- `pending_retry_validation`
- `ready_rescue_validation`
- `full`

旧Recovery専用command、固定Recovery command、Groq専用commandを復活させない。

ONE-SHOTはRecovery専用語ではなく、現行の汎用手動実行契約として保持する。

成功したONE-SHOTのdownstream fan-outは、受動的な二重起動ではなく**明示的なworkflow dispatch**をAuthorityとする。

- authentication: **`${{ secrets.GH_PAT }}`**
- downstream: `note-ready-sync.yml`
- downstream: `subscriber-decision-brief.yml`
- downstream: `cross-db-contract-guard.yml`
- downstream workflowはmanual `workflow_dispatch`可能であり、ONE-SHOTをpassive subscribeして二重writeしない
- Subscriber Decision Brief側の独立したInventory apply経路は維持する

### 2.3 Production entrypoint

- `production_pipeline.py` を安定Production entrypointとして扱う。
- Provider / runtime / safety layerのインストール順を勝手に分岐させない。
- 過去Recovery用入口からProductionへ迂回しない。
- 明示されたONE-SHOT modeが未知、またはevent JSON / inputsが不正なら、Production初期化より前に停止する。有効な別Workflowのmodeなしeventと通常ローカル実行は既存契約を維持する。
- `pending_retry_validation`はこの入口からも専用の`pending_retry_validation.main()`へ委譲し、Workflowと同じ非永続・上限付き検証を行う。

### 2.4 Pending Retry validation contract

`pending_retry_validation`はProduction品質スタックを使う**非永続の1記事検証レーン**であり、Ready化や記事復旧の一括処理ではない。

- 1回のvalidationで暗黙に2記事目へ進まない。候補順位が変わっても、1記事目の不合格やProvider障害を理由に別記事へ自動代替しない。
- `persist_results=False`の戻り値は、`accepted` / `rejected` / 未生成 / 未検証を区別する。原稿が返ったというtruthinessだけで品質成功にしない。
- validationの`quality_passed` / 互換キー` succeeded`は、明示的な`accepted`だけを数える。`rejected`は品質不合格、`None`は未生成、未知の戻り値は未検証として分離する。
- `accepted`でもNotionへ保存していないため**Ready保存成功ではない**。Ready件数・永続成功へ加算しない。
- validation専用上限はProvider-visibleな記事送信を最大4回とし、503等のProvider-visible失敗は数える。Persistent/Local Budget等による送信前拒否はProvider送信数と同一視しない。ただし既存の永続・モデル別・Deep Dive・全体Safety Capを緩めない。
- OperatorがGemini 3.6を除外しているvalidationでは、routing初期値・pool再注入・`models/`表記・3.6派生aliasを含め、最終送信直前でも3.6へ送らない。
- 記事品質の検証に不要なmodel-assisted eyecatch layoutはこのレーンでは送信しない。不合格原稿の診断・Artifact保存はアイキャッチ送信なしで継続できること。
- Workflow/jobのsuccessは、記事の品質合格・Ready・永続保存成功と同義ではない。最終報告ではこれらを別状態として扱う。
- `article_validation`も同じ非永続戻り値Classifierを使用する。未知の戻り値は`unverified`として記録し、原稿のtruthinessだけで`accepted`に加算しない。

---

### 2.5 Ready Rescue / 最小実記事E2E

- Deep Dive総予算12の配分はFresh 8 / Backlog 3 / Ready Rescue 1。使用済みカウンタをリセットせず、追加枠も作らない。
- 通常ProductionのRescueは監査Artifact・スタイル・Runtime・Funnelの初期化後、Fresh取得前に実行する。RescueのReady件数・候補順位・Artifactを後続処理に引き継ぎ、全体の記事目標を変更せず、FreshとBacklogには残りの枠だけを渡す。
- Rescue対象は既存Needs Editorial Reviewのみ。Content StatusがQuality FailedまたはPending Retryなら、Article Statusとの混在行も対象外。
- unsupported vague quantified claimは、Fact Gateが診断した該当修飾だけを0-APIで減算修正する。Fact / Evidence / Publication / Reader Gateは維持する。
- Rescue全体は最大1回のProvider送信。503の同一モデル再試行・連鎖fallbackは行わず、非Deep Dive扱いの追加repairも送信境界で止める。
- ONE-SHOT `ready_rescue_validation`は通常Production品質スタックと同じRescue関数を使用する。Fresh取得・Screening・Backlog・独立Product Reviewは回さず、既存記事1件を現在のGateで検証し、合格時だけ通常経路で保存する。
- 実検証は通常Article model set（3.5 / 3.6 / 3.7 / 3.8）を使用する。ただし`AIIF_GEMINI36_BLOCK_UNTIL`の期限前だけ3.6を時限除外し、**2026-09-16 17:00 JST以降は3.6を自動復帰**させる。Provider Healthによる並び替えは通常Production契約に従う。結果は`article_audit/ready_rescue_validation.json`と既存監査ログへ保存する。
- Ready成功が1件以上の場合のみ、既存Note Ready Syncと非公開下書きフローを起動する。同期・下書き成功は別々の実ログで確認し、ONE-SHOT成功だけを達成証拠にしない。
- Rescue fan-outの監査JSONが欠落・破損し、またはReady件数が非負整数でない場合はWorkflowを失敗させる。有効な0件だけを正常な非起動として扱い、booleanを件数として受け入れない。
- Scheduled DailyはPAUSEDを維持する。

## 3. Required CI / Dependency Contract

Production依存関係:

- Production Pillow range: `Pillow>=12.1.0,<13.0.0`
- CI known-green pin: `Pillow==12.3.0`
- CI constraints: `requirements-ci-constraints.txt`

mainへのPRで重要なrequired context:

- `zero-api-regression`
- `falsify-all-tracked-surfaces`
- `notion-access-policy`

Required status checkに指定されたWorkflowは、対象PRで必ずcheck contextを生成できなければならない。

- required workflowの`pull_request`をpath filterで欠落させない
- full deterministic regressionはzero-providerで実行可能であること
- synthetic smokeは外部Providerを消費せずcurrent Production stackを検証すること
- Guardは過去文書の完全一致ではなく、現行の実行可能なSafety invariantを検証すること

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

`PUBLICATION_POLICY_FILES` に含まれるpolicy fileの内容が変われば、policy fingerprintも変わり得る。

したがって:

- 過去のReadyが新しいpolicy fingerprintと一致しない場合、**stale判定は正常動作**である。
- stale Readyを理由に旧Recovery機構を復活させない。
- policy変更後の再認定は現行Publication Contractに従う。
- provenanceを偽装してReadyを維持しない。

---

## 5. Article Quality / Eyecatch Contract

記事品質の目的はGate通過ではなく、読者にとって**理解しやすく、面白く、判断に使えること**である。

維持する原則:

- タイトル直後は本文固有のNarrative Leadを先に置き、その後にReader Summary（「何が出た？」「なぜ重要？」「結論は？」）を置く。元情報は上部で重複させず、既存のSources / Evidence footerで保持する。
- 要確認原稿も通常のReady原稿と同じ `build_reader_first_summary` を渡して保存する。要約を省略した原稿を、そのままcaptionだけでReady化しない。
- 要約は既存の事実・重要性・判断から構成し、追加モデル呼び出しや根拠のない埋め草を使わない。
- WriterのMANAGEMENT DATAのうち `Source Summary / What / Why Important / Decision Reason / Action` は機械用構造値であると同時に、公開Reader Summaryの入力候補または旧互換fallbackである。各値はEvidenceを保ち、必要な正式名称を除いて略語・技術名を圧縮して詰め込まない。
- 公開「結論は？」は #430 の契約を正とし、有効な `Decision` がある場合はcanonical Decisionの行動距離を表す決定論的な読者向け文を優先する。実装手順や技術名の羅列をActionから逆流させない。Decisionがない旧互換データだけ、従来のfinal / Action / Decision Reasonを使用する。
- RubyGemsの依頼済み要約復元では、旧policyと本文hashを確認した対象1件だけに要約を追加する。policy更新で投稿管理がReady取消となった場合は、修正版の現行契約を読み戻してから通常同期と同じsystem propertiesを同一行へ反映する。投稿準備中・公開URLなし・投稿日なしを前提とし、他記事の再認証はしない。
- 事実・出典・Evidenceを壊さない。
- 中学生〜非エンジニアでも核心を理解できる日本語を目指す。
- 報告書調・AIテンプレート調へ寄せすぎない。
- Reader Tension、Discovery、Concrete Consequence、Explanation Bridge、Editorial Point of View等は固定個数の文体Gateではなく読者価値のために使う。
- Reader Repairは事実を創作しない。
- 日本語修復で意味・主語・因果・数値・条件を勝手に変えない。
- Evidence不足を文章力で隠さない。
- Provider障害と記事品質不良を分離する。
- 無料noteの品質を意図的に落として有料転換を作らない。無料記事自体が集客・信頼形成の商品入口である。

Production Writerの編集思想は **AIIF Editor Persona** として、既存 `call_gemini_grounded_deep_dive` の `system_instruction` に渡す。初回・既存Quality Retryとも同じ入口を使う。Personaは専属編集者としての人格・事実への姿勢・発見と読者判断を重視する思想のみを持ち、出力形式や細かいノルマを持たない。Screening / Product Review等へは適用しない。

Writer指示の責務は次の5つに分ける。

| 責務 | 正本 |
|---|---|
| Persona | `canonical_article_contract.aiif_editor_persona` → WriterのSystem Instruction |
| Evidence / Fact制約 | `content_generation_protocol` のSOURCE BOUNDARY / source別Fact Discipline / Structured Evidence、およびcanonicalの意味境界 |
| Editorial Story設計 | `canonical_article_contract.canonical_writer_contract` 内のEditorial Story Brief |
| Output Contract | `content_generation_protocol.build_decision_prompt` の既存MANAGEMENT DATA＋ARTICLE形式 |
| Final Reader Check | `canonical_article_contract.canonical_final_reader_check` 内の一度の内部Self-Edit |

Human Editorial Styleは文体・Reader Experience / Delight / Proximityの補助に限定し、上記責務を繰り返さない。専門語数・呼びかけ回数・一定段落ごとの文体切替・固定文字数を完成条件にしない。

従来の**Editorial Blueprint**は別計画を増設せず、同一Writer call内の **Editorial Story Brief** に統合する。`SURPRISE / Discovery`、`TENSION / Capability Boundary`、`HUMAN STAKE / Why Now`、`QUESTION / Reader Question`、`PAYOFF / Central Conclusion / Reader Decision` を内部形成し、Target Reader・Evidence Anchor・必要な専門語の選択を引き継ぐ。Evidenceに意外性・矛盾がなければ「なし」とし、架空の緊張・動機・人間的影響を作らない。

QUESTIONは一本の **Narrative Question** として段落間の疑問・意味・判断をつなぐ。疑問文として公開する義務はなく、答えや重要制約を最後まで隠す演出もしない。冒頭は違和感・意外性・問題・疑問、または平易な事実と意味から自然に選び、固定の発表要約型やクリックベイトにしない。

出力直前の **Self-Edit** は同じ生成内で一度行い、弱いタイトル・導入、次を読む理由の欠落、発表の羅列、一般論、AI的説明、重複、不要な専門語、中心疑問からの逸脱、PAYOFF不足を削除・統合・順序変更・言い換えで直す。技術説明だけの段落が連続する場合は、各説明がNarrative Question / Reader Decisionを進めるかを確認し、進めない説明を削る。必要な説明は「だから読者にとって何が変わるか」を既存Evidenceの範囲で普通の日本語へ戻してから次へ進む。一度役割を説明した正式名称・略語は正確な区別に必要な場合だけ繰り返す。新しいFact・数字・経験・因果は追加しない。既存局所修正の範囲と重要な意味を守り、完成稿だけを返す。内部ブリーフ・初稿・編集過程は公開出力へ含めない。

Persona / Story Brief / Self-Edit / Human Appeal専用callは増設しない。Evidence / Source Fidelity / Fact / Publication Readiness / Grounding / Source Integrity / Numeric Evidence / Safety / Notion persistence、および既存Retry・Provider予算は変更しない。

オフライン比較は `tools/editorial_ab.py`。同一Evidence・記事条件で凍結旧promptと現行promptを比較でき、手書きfixtureの11軸診断と新旧入替・旧稿勝利・同文引き分け・根拠欠落の対照を持つ。これは新旧モデルの実出力比較ではなく、評価経路と契約の検証である。語彙ベースの点数やfixture保持率を実際の読了率・意味的Fact保証・Production品質改善の実証として扱わない。Gemini / Google APIの実消費、Daily、note公開、Notion実更新は別途明示許可が必要。

Quality Retry / Reader Repair / Reader Rhythm / 出力直前チェックも同じBlueprintに従う。中核メカニズム1つ、列挙3点以内、1段落2概念未満、冒頭600文字、固定段落数での説明切替などの機械的な編集上限は使用しない。文章量・専門語・構成は核心・重要制約・読者判断の理解に必要かで決め、必要な複数の仕組み・比較条件・正式名称を個数合わせで削らない。技術説明と判断の関係が伝わらない箇所だけ接続を直し、各段落への定型的な説明文追加はしない。

Reader専用Repairでは、Run172の局所文面保持契約も適用しない。Run208と同じReader-only理由分類を使用し、Fact/HARD/混在/未知の理由では従来の局所修正保護を維持する。保護対象はEvidence・Decision・重要制約・比較・反証の意味であり、前稿の段落順・見出し・列挙全項目ではない。判断に不要なベンチマーク名と値は本文から省略できるが、残す数値の単位・測定条件・対象や、推奨強度に影響する条件は保持する。分類の共有はRetry許可・消費回数・Gateを変更しない。

この統一はpromptの編集指示に限定する。通常Quality Retryと専用Reader Repairの所有権・回数制限、Evidenceの実行条件、Publication / Fact / Evidence / Reader Gateの判定は変更せず、修正後も全Gateを再判定する。固定ノルマの撤去だけでHuman Appealの改善や実記事の合格を証明したとは扱わない。

Capability Boundaryでは「できる / できない / まだ分からない」を分離する。「できない」はSOURCE BOUNDARYに禁止・非対応・制約が明示される場合だけとし、Evidenceがないだけの事項は「未確認 / まだ分からない」と扱う。

数値Factの表記同値は、**Evidenceに同じ値が明示され、かつ数値近傍の条件・対象が互換な場合だけ**認める。`$0.75`と`0.75ドル`、または同じ記述内の日本語`万`表記と桁区切り付きUSDのような表記差は機械的に照合してよいが、丸め・推定・別条件の同額・別文脈の数字から値を補完してはならない。条件不一致、根拠のない数値、曖昧量は従来どおりFact停止を維持する。

Primary-sourceの数値Evidenceでは、次の一般契約を追加で守る。

- `$1.50`、`1.50ドル`、`1.5 USD`のように**通貨が明示された表記**は、Decimalとして完全に同じ数値であり、近傍の対象・時点・単位等の条件が互換な場合に限って同値として扱う。末尾ゼロの有無は表記差であり、丸め・許容誤差・近似一致を導入しない。
- `1.50`のような**通貨表記のない裸の数値**を通貨Claimの根拠へ昇格させない。
- semantic `<article>` 内の `<footer>` にある脚注、価格改定、期限、但し書き、引用等は、その記事自身のPrimary Evidenceとして保持できる。
- `<article>` 外のサイト共通footerはナビゲーション・広告・別文脈の数字が混入し得るためEvidenceから除外し、記事Claimの根拠に使わない。
- Artifact再検証では、保存Artifactに存在するusage audit・accepted manuscript等から証明できる事実と、保存されていないpre-rescue原稿・元HTML等を分離する。欠けた履歴を推測で復元して「完全再生」と報告しない。
- 過去Artifactに元HTMLや削除前Claimが残っていない場合、そのArtifact自体の監査と、同じ失敗条件を再現する決定論fixtureによる回帰検証を組み合わせる。後者はProvider/APIを使わず、現行Productionロジックが同じ誤判定を再発させないことを証明するためのものとする。

**Editorial Quality Memory v1** は、成功/失敗した編集パターンをリポジトリ内の決定論的ルールとして保持する。Production原稿、個人情報、Provider応答を可変DBへ保存せず、追加APIを要求しない。Quality MemoryはHard Gateや事実源ではなく、Fact / Evidence / Decision / Publication Contractを常に優先する。Quality Memory自体はPublication Policy fingerprintの対象に含める。

Eyecatchは現行runtime ordering・emphasis scale・Pillow互換性を実コードとsemantic guardで保護する。過去の描画方式やRun番号を仕様成立条件にしない。

---

## 6. Intelligence Source Contract

Productionで同格に扱うactive Source:

1. **GitHub = 実装動向**
2. **ArXiv = 技術の先行動向**
3. **HackerNews = 市場・エンジニア反応**
4. **OfficialVendor = 商用利用に直結する一次情報**

**Product HuntはProductionのactive Sourceではない。**

上記4 SourceはFresh取得の必須配分であり、任意の発見経路`X`を追加の必須配分にはしない。Content DBとTechnology / Subscriber / Member DBのSource契約は共通のPublication Source定義を参照する。後者は既存の`Unknown`も許容する。旧ProductHunt等の余剰enumは互換性のため許容するが、存在を必須にしない。

OfficialVendorはベンダーごとにSource枠を分裂させず、1 Sourceとして扱い、metadataでvendor / regionを識別する。

現行vendor registryは少なくとも次を含む。

- OpenAI
- Anthropic
- Google Gemini
- Alibaba Qwen
- DeepSeek
- ByteDance Doubao / Seed
- Moonshot AI Kimi
- Zhipu AI GLM
- MiniMax
- Baidu ERNIE
- Tencent Hunyuan

地域・ブランドだけで加点減点せず、一次情報・Evidence・実務影響・Decision契約で評価する。

HackerNews acquisition precision:

- AI関連取得は広すぎるraw queryではなく、exact token / exact phraseを使う。
- lookbackは現行契約の**30日**。
- OfficialVendorはcurrent-state取得で`structured_current_state`を優先し、必要時に`page_fallback`を使う。
- live smokeはprovider/model call、Notion write、Production DB write、publication actionを行わない。

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

現行Member Surfaceは**Generic Use-Decision**を正とする。

- 自己学習・自己開発に使える
- 社内・実務利用に使える
- 顧客提案にも使えるが、それだけを主用途にしない
- source scores / decision status / evidenceをPresentation都合で書き換えない
- paid product messagingと無料noteのCTAを矛盾させない

過去のProposal-First構成は互換履歴であり、現行商品価値のAuthorityではない。

---

## 8. Paid Member Production Surface

現行Member Surfaceでは次を守る。

- PC-first
- live Top3
- fixed cardをAuthorityにしない
- Decision/EvidenceをPresentation都合で書き換えない
- canonical member DBへfail-closedで同期する
- legacy DBをProduction destinationへ戻さない
- automatic DB creationを有効化しない
- member writerの排他を維持する
- member-facing derived syncは不要なGemini/model callを行わない
- member-facing languageは非エンジニアでも理解できる日本語を使う

Member body delta sync:

- `MEMBER_BODY_CHANGED_SINCE` を使うdelta pathを維持する。
- 基準は**前回成功**した同期runの開始時刻。
- checkpointが欠ける、再実行、または契約不一致時はfull scanへfail-safeする。
- `sentinel` が契約不一致を検出した場合は部分同期で誤魔化さない。
- `MEMBER_BODY_FORCE_FULL` による明示的full pathを維持する。

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
- Pending Retryはbounded request budgetと503 cooldownを維持し、Provider障害時に無制限再試行しない。
- secret、token、認証情報をrepository・log・artifactへ漏らさない。

---

## 10. Documentation Governance

### 10.1 唯一の現行仕様入口

Factory全体の現行仕様を確認するときは**本ファイルを最初に読む**。

Run単位の「仕様追補」「監査結果」「Recovery指示書」は、現行仕様の入口にしない。

### 10.2 過去資料の扱い

過去Run文書・reference・archiveは削除しなくてもよいが、意味は以下に限定する。

- 設計理由
- 過去の障害記録
- 検証結果
- 回帰防止の由来
- 監査証跡

過去資料に書かれたProvider、Recovery手順、固定ID、固定SHA、旧Workflow名が現在も有効だと推定してはならない。

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

単なる内部リファクタリングやテスト追加は、本書の契約を変えない限り履歴番号や過去経緯を追記しない。

---

## 11. 廃止事項 — 誤復活防止

以下を現行Production仕様として扱わない。

- Groq + Gemini coexistence
- Groq/Qwen shadow provider
- Groq technology comment shadow live
- Product Huntをactive Production sourceへ戻すこと
- current-policy Ready recovery workflow
- Ready metadata rebase workflow
- fixed-ID / fixed-SHA / fixed-period recovery tooling
- historical diagnosticを常設Production機能として使うこと
- 45記事Recoveryの継続
- 「残り33記事をすべて復旧する」ことをProduction backlogとして扱うこと
- historical documentation wordingをCI合格条件へ戻すこと

ただし、これらの過程で得られ、現在の一般安全機構へ昇格したprovenance / publication / reader / evidence / Japanese integrity / repair protectionは維持する。

---

## 12. Current-state summary

2026-09-16時点のFactoryは、次の状態を正式な基準とする。

- **Production:** Geminiベース既存ロジック
- **Primary / Quality:** Gemini 3.8 / Gemini 3.7の役割分離を維持
- **Article generation:** Writer前にEditorial Blueprint + deterministic Editorial Quality Memory v1を適用
- **Groq coexistence:** 終了
- **X logic:** Productionリポジトリへ統合済み（`x_discovery` / `x_intelligence`、`is_evidence=false`・ゼロプロバイダー安全契約を維持）
- **Active sources:** GitHub / ArXiv / HackerNews / OfficialVendor
- **Product Hunt:** active Production sourceではない
- **45-article Recovery:** 終了、33件未復旧のまま再開しない
- **Scheduled Daily:** PAUSED
- **Manual execution:** current ONE-SHOT / explicitly dispatched workflows
- **Ready Rescue validation:** 1記事・最大1 Provider送信。3.6の期限付き除外は2026-09-16 17:00 JSTで自動失効し、その後は通常Article model setへ復帰
- **Pending Retry validation:** 1記事・非永続。`accepted`だけを品質PASSとして数え、Ready保存と分離。Provider-visible記事送信は最大4回、model-assisted eyecatchは送信しない
- **Publication safety:** provenance + current policy + Reader/Evidence/Integrity guardsを維持
- **Paid product:** Generic Use-Decision Intelligence
- **Repository:** Recovery専用・Groq共存専用surfaceを撤去済み
- **Documentation Authority:** `main` → 本書 → 領域別契約 → reference/archive

この状態から次の開発を開始する。過去Recovery、Groq共存、過去Run番号、旧文書ロックを暗黙の前提として引き継がない。
