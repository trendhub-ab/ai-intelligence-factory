# AI Intelligence Factory — Run281 仕様追補

最終更新: 2026-09-08  
対象Baseline: **Run281 — Publication Causality / Source Contract / Recursive Provenance Closure**  
Production Source of Truth: **`main`（本変更merge後）**

本追補は、現行Production仕様書のうち「Publication Contract」「Note Ready → note private draft」「Intelligence Source Contract」の下流整合性をRun281へ更新する。既存のFact / Evidence / Publication / Reader Gate、public release human-only、Gemini Free Tier制約は変更しない。

---

## 1. Publication Contract — 再帰依存closure

Readyは履歴状態であり、現在の公開ポリシー準拠を意味しない。公開可能なReady manuscriptは、本文SHAとcurrent publication policy SHAの両方が一致しなければならない。

Run281では `PUBLICATION_POLICY_FILES` を単なる手動リストとして信頼しない。`run280_publication_dependency_guard.py` が、fingerprint対象となる**全モジュールのローカルimportを再帰的に監査**する。

### current contract

- `reader_quality_precision.py`
- `evidence_sufficiency.py`
- `source_normalization.py`
- `reader_experience_signals.py`
- `evidence_context.py`
- `editorial_naturalness.py`
- `note_manuscript.py`
- `candidate_identity.py`
- `publication_source_contract.py`
- `content_generation_protocol.py`
- `fact_validation_signals.py`
- `source_boundary_validation.py`
- `runtime_layers.py`
- Run260 model routing
- Run268 / Run269 source acquisition stack
- public eyecatch stackおよび `eyecatch_badge_taxonomy.py`
- Publication / Reader / Evidence / CTA / Notion manuscript persistenceに影響する既存runtime layers

上記を含むcurrent publication-material closureはfingerprint対象とする。

新しいローカル依存がfingerprint対象モジュールからimportされた場合、次のどちらかを満たさない限りrequired CIをFail-Closedにする。

1. `PUBLICATION_POLICY_FILES`へ追加する。
2. 公開本文・公開可否・公開アイキャッチ・公開Source attributionへ影響しないことを、狭い理由付きoperational exemptionとして明示する。

Telemetry、quota/retry transport、member-only maintenance、candidate scheduling等を無条件にfingerprintへ入れない。公開物を変えない運用変更で全Readyを不要に失効させ、Gemini再生成コストを増やさないためである。

`note-ready-sync.yml` のpush pathは `PUBLICATION_POLICY_FILES` と同期し、policy file変更時はmain上でReady queue reconciliationを行う。

---

## 2. Note Ready → private draft fan-out因果契約

Run33で観測された `source_ready=0 / created=0 / updated=0` にもかかわらず `Create note Draft` workflowがdispatchされる状態を禁止する。

### Run281 current flow

1. `note_ready_sync.py` がcurrent-policy Readyを同期する。
2. explicit `workflow_dispatch` かつ `create_private_draft=true` の場合だけ、親workflowが `run199_note_vm_preflight.preflight()` を実行する。
3. `status == eligible_ready` かつ `should_start_vm == true` の場合だけfan-out eligibleとする。
4. 親workflowで選定した `selected_sync_id` を固定する。
5. eligibleの場合だけ `note-create-draft.yml` をdispatchし、固定した `sync_id` を子へ渡す。
6. 子workflowは同じpublish-safe preflightを再実行する。これはdefense in depthであり、親の誤dispatchを正常系として許容するための装置ではない。
7. `no_eligible_ready`、current-policy Readyなし、eyecatch不足、投稿対象外状態等では**子workflow自体をdispatchしない**。

pushによるpolicy reconciliationではprivate draft fan-outを起動しない。public releaseは引き続きhuman-onlyである。

この契約により「Draft workflowが起動した」というイベント自体を、実際にeligible Readyが存在した場合のみに限定する。

---

## 3. Canonical Public Source Contract

Run268以降のactive SourceとNote公開下流を一致させるため、`publication_source_contract.py` をcanonical authorityとする。

active public sourcesは**厳密に次の4系統**とする。

1. `GitHub`
2. `HackerNews`
3. `ArXiv`
4. `OfficialVendor`

`ProductHunt` はretired sourceであり、次のcurrent contractには含めない。

- Note Ready allowlist
- reader-facing source label authority
- non-GitHub rights note authority
- Production active source set

`note_ready_sync.py` は `ACTIVE_PUBLIC_SOURCES` を直接参照する。unsupported / retired sourceはfail closedでNote Readyへ流さない。

`note_manuscript.py` も同じcanonical source contractからreader labelとrights noteを参照する。

### OfficialVendor public attribution

Reader-facing label: **公式ベンダー**

権利注記は、各ベンダーが公式公開した一次情報を基に独自分析・要約したこと、および製品名・商標・公開資料等の権利が各権利者へ帰属することを明示する。

### Hacker News

Hacker Newsは一次情報そのものとして扱わず、技術的事実・数値は上部の公式リンクおよび参考情報で確認できる範囲へ限定する。権利注記内で「発見経路」を重複表示しない。

---

## 4. Required CI / Falsification Contract

PR to mainでは少なくとも次を必須検証する。

- Run279 canonical runtime-layer order
- Run280/281 recursive Publication Dependency Completeness
- Run281 source contract / fan-out causality adversarial tests
- Repository-wide provenance / secret falsification
- Workflow Reference Integrity
- Documentation current-contract guards
- Run268 / Run269 source strategy and acquisition precision
- Notion access policy
- full deterministic regression
- current Production synthetic smoke

Publication dependency closureで未分類moduleが検出された場合、テストを緩めて通さない。公開物へ影響するならfingerprintへ昇格し、純運用なら理由を明記して除外する。

---

## 5. Cost / Business Contract

Run281はGemini/API request budgetを増やさない。

- dependency guard: zero-provider
- source contract: zero-provider
- fan-out parent preflight: Notion readのみ、zero-VM
- eligible Readyなし: child Draft workflow dispatchなし、VM起動なし
- public release: human-only

目的は安全性だけではなく、誤fan-out・不要VM・不要再生成を減らし、無料枠運用と利益率を守ることである。

---

## 6. Run281完了条件

以下を全て満たしたときRun281完了とする。

- current publication-material local dependency closureがrequired CIでPASS
- OfficialVendorがNote Readyとpublic manuscript attributionの両方でcurrent contractとして扱われる
- ProductHuntがcurrent public source contractから除外される
- no eligible Ready時にparentからCreate note Draftをdispatchしない
- full deterministic regression PASS
- Synthetic smoke PASS
- validate PASS
- Notion access policy PASS
- merge後mainでもrequired checksとpolicy reconciliationがPASS
