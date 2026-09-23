# AIIF Gate・Retry・Rescue・Ready到達性 横断監査

監査基準: `635edb911ded28748868885d53add9920f243fe5`（main、PR #516統合後）。
日付: 2026-09-23。

## 結論と証明範囲

Readyへの経路全体が常に到達不能、という仮説は反証された。実際のProduction dispatcherが組み立てるGate群を用い、正常な固定原稿が全停止条件を満たし、保存成功を与えた場合だけReadyになる実行例を確認した。

一方、修正前の実装では4種類の相互作用上の欠陥を再現した。独立レビューで、要約検証追加後にも残る例外処理との相互作用をさらに1件再現した。安全な修正稿を阻止する欠陥だけでなく、本来阻止すべき稿をRescueや要約挿入が通してしまう欠陥も含む。検出済みの判定を無視する修正ではなく、現在の原稿・公開要約・実行中の候補に判定を一致させた。

これは有限の反例・到達例による検証であり、あらゆる自然言語原稿が正しく判定されるという数学的証明ではない。Gemini API呼び出し、実Notion更新、note下書き作成・公開は行っていない。実モデルによる良質な原稿の生成率や、実サービスでの保存成功率は未検証である。

動的な到達例は適格候補を共通生成関数へ投入する段階からのもの。収集・Screeningの実モデル応答・Notion実保存までを含むlive E2Eではない。これらの入口条件と共通生成への接続はコードと既存回帰で確認した。

## 監査手法

- GitHubの最新main、tree、CI状態を読み取り、全1,066ファイルのGit blob SHAを照合して監査用コピーを固定した。過去会話のSHAは基準にしなかった。
- 既存テスト2,875件の初期PASSを記録したが、正しさの証明には採用しなかった。
- `production_pipeline.main()`を通して実際のruntime layersとcurrent overlaysを導入した。合否判定関数をPASSのスタブに置き換えず、モデル応答と外部入出力だけを固定した。
- 修正前に失敗する反例を先に追加し、修正後の通過を確認した。同じ入力で安全側・危険側を対にした。
- 外部ネットワークはpytestの既存autouse fixtureで遮断した。Google SDKの初期化とGemini API実送信を区別し、実送信は行っていない。
- 製品コードの変更は `pipeline.py`、`run249_final_publication_surface_gate.py`、`run283_numeric_evidence_equivalence.py`、`article_revalidation.py` に限定した。

## 横断した実行経路

| 境界 | 主な実装 | 後段との関係・監査内容 |
|---|---|---|
| 実行入口・layer順序 | `production_pipeline.py`, `runtime_layers.py` | 通常・full・検証入口が使う共通生成関数とoverlay順序を追跡。63 publication-policyファイルの依存分類をguardでも確認 |
| 候補受付 | `pipeline.main`, `legal_safety_gate`, `candidate_identity.py` | ライセンス、既存URL、候補内URL重複、Stock/Deferred/Pendingの入口を確認 |
| Source Integrity / Freshness | `prepare_source_context`, `_verify_arxiv_source_integrity`, `resolve_followup_freshness` | 一次資料、出典ID・タイトル、補足取得、時点とsource depthからEvidenceへ渡す状態を追跡 |
| Evidence | `evidence_sufficiency.py`, `run172_production_reliability.py` | requested tier、許可tier、downgrade理由、sufficient互換フィールドの更新先を追跡 |
| Fact | `validate_fact_gate` とRun175/223/227/176/248/283 | 数値・固有名詞・意味・条件・出典・日本語・行動制限を追跡。Rescueからの再入も確認 |
| Editorial / Publication / Human / Reader | `pipeline.py`, `reader_value_review_bridge.py`, `reader_quality_precision.py`, Run248/249 | 本文判定、最終要約・タイトル、HARD/REVIEW/SOFTへの写像を確認。本文Readerの重複検査を新設していない |
| 理由集約 | `gate_reasoning.py` | PASS/PASS_WITH_WARNINGSのみ許可。REVIEW/HARDからのRetry・保留・拒否への分岐を追跡 |
| Quality Retry / Reader Repair | `run208_reader_value_repair.py`, `run284_reader_recovery_precision.py` | 通常品質修正とReader修正の所有権、原稿ごとのreset、Fact再評価、既存budgetの上限を確認 |
| 明示承認記事の修正 | Run399/400/406/408/409/411 | exact targetと専用origin、追加Reader枠、同じ生成・Gate・保存経路への合流を確認。今回の実運用実行はしていない |
| Provider Retry | `run260_gemini_model_routing.py`, `gemini_provider_resilience.py`, budget関連 | 有限model pool、同一model retry、distinct-model上限、503 fallbackとsemantic retryの分離を確認 |
| Deterministic Rescue | `_apply_deterministic_publication_rescue`, `_publication_rescue_can_be_ready`, Run224/374 | 削除後の再評価が元の行動制限を失う反例を再現・修正 |
| Ready Rescue / Backlog | `run374_ready_rescue.py`, `run346_backlog_budget_reserve.py`, `article_revalidation.py` | preflight→fresh→backlog→既存稿救済のwrapper順で、同一pageの再選択を再現・修正 |
| Ready保存 | `generate_intelligence_report`, `notion_payloads.py`, `run194_publication_contract.py` | Gate通過と保存成功のAND。本文hash・policy hashとexact-body idempotencyを確認 |
| Ready後の同期 | `note_ready_sync.py`, `publication_contract.py`, `publication_source_contract.py` | current-policy本文証明、source、画像条件の追加チェックを確認。Content DB Readyとnote配送可能状態は別条件 |

## 再現した欠陥

### GRA-1: 安全に修正したRetry稿が古い行動禁止判定で落ちる

経路: 初稿MEDIUM → EvidenceがLOWへ制限 → Quality Retryが実際のActionをLOWへ変更 → 比較先もLOWなので再評価を省略 → 初稿の`action_risk_downgraded_from=MEDIUM`が残る → Quality Failed。

再現用の一次資料は配送手法のみを説明し、運用制約を裏付けない。初稿は「限定ユーザーへ導入する。」、修正稿は「公式資料を確認する。」。修正前は安全な後者も拒否された。

修正: 前稿の「許可tier」ではなく「要求tier」と比較してEvidence状態を更新。禁止理由は現在稿に対するFact評価で導出する。Evidence閾値・必要情報は変更していない。

テスト: `test_retry_to_low_risk_clears_previous_action_restriction`。

### GRA-2: 数値Rescueが独立した行動禁止まで解除する

経路: 根拠のない「42ms」と未許可MEDIUM Action → 初回Factで両方停止 → 数値の一文だけ削除 → Rescue helperがFact等を再実行 → 行動制限は生成loop内にしかないため消える → accepted。

修正前の公開原稿には「私なら限定ユーザーへ導入する。」が残った。Rescue helper単体でも同じEvidenceから誤ってReady可を返した。

修正: 行動制限を共通Fact Gateに置き、Rescueでも現在のActionを一次資料に照合する。数値削除によって別の停止条件が解除されない。

テスト: `test_numeric_rescue_cannot_erase_independent_action_failure`、`test_rescue_helper_enforces_evidence_action_scope`。

### GRA-3: Fact通過後に未検証の公開要約を挿入する

経路: 数値を含まない安全な本文 → Fact PASS → `source_summary_text`から要約を作成 → 本文に存在しなかった「応答時間は42msです。」を挿入 → accepted。

Run249の最終面検査は日本語・括弧・要約断片等を確認していたが、要約の数値・意味はFactの対象外だった。

修正: 実際の要約builderの返す公開要約とタイトルを、本文とともに既存の全Fact wrapperへ渡す。元本文は変更しない。短い要約に長文向けReader密度判定を重ねる修正ではない。

テスト: `test_summary_assembly_cannot_introduce_ungrounded_number_after_fact_pass`。

### GRA-4: 同じ失敗記事を一実行内で再び救済する

経路: Ready Rescue preflightが既存Editorial Reviewのpage Aを試す → Readyにならず同じ状態で残る → full recoveryを内包するbacklog wrapperへ → page Aを再選択 → もう一度生成。

単独のRun374 wrapperの「slot消費済み」だけでは、その内側のRun277既存稿救済を止められなかった。無限loopではないが、同じ失敗候補への重複消費を実証した。

修正: 実行単位の既存稿attempt済みpage IDを選定前に除外する。次の別page Bは選択可能。次回runの開始時に集合をresetする。予算総額やGateは変えない。

テスト: `test_full_recovery_does_not_repeat_consumed_preflight_candidate`（次候補あり／なし）。

### GRA-5: 後段の例外処理が別の公開面で発生したFact違反を消す

独立レビューで、GRA-3の要約検証を加えただけでは不十分なことを再現した。本文が「投資対効果を評価する。」、要約が未根拠の「この手法は投資対効果を改善する。」の場合、内側のFactは要約の断定を検出する。しかし外側のRun283/350は元本文だけを見て「評価意図の誤検出」と判断し、違反を消してacceptedへ戻していた。

修正: 内側のFactと外側の例外処理が、同じ公開要約・タイトル・本文のprojectionを使用する。評価意図だけの正常稿は通し、成果を断定する混在稿は止める。

テスト: `test_outer_precision_filter_uses_same_summary_surface`（未根拠の成果断定／評価意図のみ）。修正前は危険側1件失敗・正常対照1件成功を確認した。

## 到達性と循環について

- 正常稿のjoint witnessは、全Gateを実際に通した後、new / deferred / pending_retry / existing_editorial_recovery / existing_stale_ready_recoveryの5 originで確認した。
- 各originについて保存成功・保存失敗の双方を与え、成功時のみReady、失敗時はPersistence Failedかつ戻り値なしであることを確認した。Notion通信自体の成功を主張するものではない。
- 修正前のGRA-1は「安全稿への修正が成功しても過去の状態で再び失敗する」到達阻害。GRA-4は有限だが重複する再入経路。
- Quality Retryのloop上限、専用ownerの使用済みフラグ、有限provider pool、request budgetを追跡した。調べた経路で無制限のAPI再帰loopは確認していない。
- Content DB Readyの後も、note Ready同期には現行policy hash、本文hash、許可source、画像等の条件がある。今回の成功例は実note配送完了を意味しない。

## 既存テストを反証対象にした結果

- `tests/test_run102_publish_yield_precision.py`の経路テストはFact/Evidence/Publication/Human等を固定値に置き換える。分岐確認には有効だが、同時充足可能性の証拠にはならない。
- `tests/test_run147_rescue_loss_precision.py`は実装の損失式をテスト側で再記述し、source文字列を確認する。損失ルールの記録にはなるが、現在のwrapperを通したRescueと全Gateの相互作用は証明しない。
- Run374のstub orchestrationだけではRun277＋Run346＋Run374の合成時の重複実行を検出できなかった。新テストは実際の合成順を実行する。
- 合成回帰500件は`validate_synthetic_invariants`の固定入力検証であり、生成loop・全wrapper・実Notionを含むE2Eではない。全件PASSをReady到達性の代用にしなかった。
- 新テストの導入時、共有renderer moduleへのpatchが後続テストへ残る2件の干渉も発見した。namespaceを復元するfixtureへ修正し、該当37件を再実行して通過を確認した。途中の変更とpolicy hash計算が重なった検証結果も最終結果には採用せず、変更を固定して再実行する。

## 実行済み検証

- 修正前既存pytest: 2,875 passed。
- 初期反例: 4 failed / 1 passed（GRA-1/2/3と正常対照）。
- 追加の重複救済反例: 1 failed / 15 passed。
- 修正後の重点検証: 45 passed（追加前の16件＋Run277/374）。
- テスト隔離修正後の関連検証: 37 passed。
- GRA-5修正後の重点検証: 31 passed。
- Synthetic harness self-test: PASS。
- Synthetic full: 500/500、failed=0、critical failures=0。
- compileall、integration stability、runtime layer order、publication dependency completeness、repository falsification、workflow reference guard: すべてexit 0。

独立レビューはGRA-5を指摘し、修正後に同じprojectionを使用することと正常な評価意図の例外が維持されることを確認した。再レビューでは追加の具体的不具合指摘はなかった。

最終検証: `python -m pytest -q tests test_run360_gemini_retry_owner.py` → **2,897 passed, 1 warning（179.07秒）**。追加した19件を含む。warningは既存画像テストのPillow `getdata()`非推奨通知。実行環境はPython 3.12.14 / pytest 8.4.2 / Pillow 12.3.0。GitHub CIのPython 3.11環境での結果はPR上で別途確認する。

## 維持した条件

Evidence/Fact/Publicationの閾値・意味判定を緩和していない。SOFT/HARD/REVIEWの分類、provider pool、予算上限、モデル数、公開権限は変更していない。添付キャラクター画像は監査対象コードと無関係のため使用していない。
