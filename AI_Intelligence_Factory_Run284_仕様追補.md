# AI Intelligence Factory Run284 仕様追補

## 1. 目的

Run282のCurrent-policy Ready Recoveryを実Productionで2件実行した結果、次の2つを分離して確認した。

1. **公開文字列を破壊する0-API日本語補正バグ**
2. **Evidence十分・Fact/Editorial/Publication PASSなのにReader-onlyで落ちた候補へ、Recovery専用4-request枠の残りを一度も使わない非効率**

Run284はこの2点だけを局所修正する。

Ready率を上げるためにReader Value / Human Appeal Gateを弱めない。通常Daily、新規記事、Pending Retry、Deferred、Article Validationのretry policyも変更しない。

Scheduled Dailyは引き続きPAUSED。公開noteはhuman-only。

---

## 2. Production Finding A — `をな`自動削除による正常日本語の破壊

Recovery #2 の `wandb/wandb` で、生成タイトルの正常な語句がFinal Japanese Polishにより破壊された。

本来の意味:

`AI開発の迷子をなくす…`

補正後:

`AI開発の迷子をくす…`

原因は `pipeline.py::_JAPANESE_SAFE_FIXES` の次の広すぎる規則。

`をな(?=[日本語/英字]) -> を`

この規則は誤字だけでなく、正常な動詞も破壊する。

- `をなくす`
- `をなぞる`
- `をなす`
- `をなめる`

### Run284対応

`run284_reader_recovery_precision.disable_overbroad_japanese_polish()` がProduction起動時に**この1規則だけ**runtime tupleから除外する。

以下の既存補正は維持する。

- `がを... -> を...`
- `にを... -> を...`
- `というという -> という`
- その他Run284が触れていない既存補正

この修正は0 API。

---

## 3. Production Finding B — Reader-only Recoveryが1回目で終了

Recovery #2 の `wandb/wandb` は次をすべて満たした。

- Evidence: SUFFICIENT
- Decision scope: safe
- Fact Gate: PASS
- Editorial Gate: PASS
- Publication Readiness: PASS
- Human Appeal / Reader Value: REVIEW

主なReader failure:

- `dense_report_cluster`
- `multi_axis_reader_weakness`
- `non_engineer_access_failure`
- final surface equivalents

実原稿監査でも、冒頭は比較的よい一方、後半が機能説明・構成列挙・報告書調へ戻っており、Gateは妥当だった。

したがってGateを緩めない。

一方、Run282 Recovery workflowには1候補あたり最大4 model requestsのHard Limitがあるにもかかわらず、この候補は3.7初稿の1 requestで終了した。既存のReader bridgeがReader-only failureを `reader_value_review_no_retry` として止めるためである。

---

## 4. Run284 Reader-only Repair契約

Run284は既存 `should_attempt_dynamic_retry()` をcurrent precision overlayとしてwrapする。

追加model repairを許可する条件は**全条件AND**。

1. `candidate_origin == current_policy_ready_recovery`
2. 既存policyの判断理由が `reader_value_review_no_retry`
3. `evidence_result.state == EVIDENCE_SUFFICIENT`
4. `decision_scope_safe is True`
5. HARD reasonが0
6. 全blocking reasonが `reader_value_review:` family
7. reasonがProductionで確認したrepairable familyのみ
8. 同一processでRun284 repair未使用

repairable family:

- `dense_report_cluster`
- `repetitive_insight`
- `multi_axis_reader_weakness`
- `non_engineer_access_failure`
- `final_surface_multi_axis_reader_weakness`
- `final_surface_non_engineer_access_failure`

許可時のreason:

`run284_current_policy_reader_repair`

### 最大回数

Run284自身が許可するReader-only repairは**1 processにつき1回だけ**。

さらにRun282 workflowの既存Hard Limit:

- candidate: 最大1
- deep-dive/model requests: 最大4

が上位Authorityとして残る。

したがってRun284から無制限retry loopは作れない。

---

## 5. 修正方法

Run284は新しい長大なReader promptを追加しない。

理由:

Run226 / Run228 / Reader Value Review Bridgeには、すでに次の適切な局所修正指示が存在する。

- Evidence・数値・制約を維持
- 重複説明を削除
- Decisionに不要な実装列挙を削除または平易な1文へ置換
- 非専門読者が核心へ到達できない箇所だけ平易化
- 新Fact・架空体験・新しい数値・新しい因果を作らない
- 記事全体を全面再構成しない

Run284はその**既存quality retry pathを1回だけ利用可能にする**。

---

## 6. 変更しないもの

次は一切変更しない。

- Reader Value Gate閾値
- Human Appeal Gate閾値
- Fact Gate
- Evidence Sufficiency
- Publication Readiness
- Decision Score
- Source Boundary
- 通常new candidate retry policy
- Pending Retry policy
- Deferred policy
- Article Validation policy
- fresh acquisition
- Screening
- Product Review
- Note Draft fan-out
- VM/browser
- public note publication
- Scheduled Daily

Reader repair後もGateに再度失敗すればReadyにはしない。

---

## 7. Publication Contract

`run284_reader_recovery_precision.py` は公開文字列と公開可否に影響するため `PUBLICATION_POLICY_FILES` に含める。

`production_pipeline.py` も既存どおりfingerprint対象。

`.github/workflows/note-ready-sync.yml` のpush pathにもRun284を追加する。

したがってRun284変更後、過去Readyを現行policyとして自動継承しない。

---

## 8. Recovery実行前Fail-closed

`.github/workflows/current-policy-ready-recovery.yml` はGemini実行前に次を0 APIで必須実行する。

- `tests.test_run282_current_policy_ready_recovery`
- `tests.test_run284_reader_recovery_precision`
- `run280_publication_dependency_guard.py`

Run284 contract testが失敗した場合、Gemini requestは開始しない。

---

## 9. Run284反証テスト

`tests/test_run284_reader_recovery_precision.py` は少なくとも次を確認する。

### Japanese polish

- `迷子をなくす` が破壊されない
- `線をなぞる` が破壊されない
- `役割をなす` が破壊されない
- `表面をなめる` が破壊されない
- 他の既存安全補正は維持

### Reader repair

- W&B実測reason familyはRecovery限定で1回だけrepair可
- 2回目は拒否
- new candidateは変更なし
- pending_retryは変更なし
- deferredは変更なし
- article_validationは変更なし
- Evidence不足は拒否
- unsafe decision scopeは拒否
- HARD reason混在は拒否
- reader_delight_overclaimは拒否
- warm_hook_cold_bodyは拒否
- 既存policyがretry=trueならその判断を上書きしない

### Repository contract

- Production installを確認
- Publication fingerprintを確認
- Note Ready reconciliation pathを確認
- Recovery workflowでRun284 testが`production_pipeline.py`より前に実行されることを確認
- Recovery workflowに`note-create-draft.yml`が存在しないことを確認

---

## 10. コスト判断

Run283後のRecovery #2では3.7を1 requestだけ消費し、Fact系の不要retryは消えた。

Run284では、Evidence十分で記事資産価値が高く、しかもReader-onlyの局所修正で回収可能性がある場合だけ**最大1 request追加**する。

これは新しい候補をもう1本フル生成するより、すでにFact/Evidence/Publicationを通過した原稿を局所修正する方が期待回収率が高い、という事業判断である。

ただし実ProductionでのReader repair成功率はまだ未検証。CI/main反映後の次回Production Recovery 1件で検証する。

**Run284実装・mergeのために3件目のRecoveryは実行しない。** 次回の明示的検証までGemini消費を止める。
