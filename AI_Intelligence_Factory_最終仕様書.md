# AI Intelligence Factory — 現行Production仕様

最終更新: 2026-09-02  
現行Functional Baseline: **Run199 — publish-safe note VM preflight**  
Repository Organization Baseline: **Run200 — behavior-preserving consolidation**  
Production Source of Truth: **`main`**

## 0. この仕様書の位置づけ

このファイルは「現在のProductionで何を守るか」を短く明示する現行契約である。

参照優先順位は次の通り。

1. `main` の実行コード、テスト、GitHub Actions workflow
2. 本ファイルの現行Production契約
3. `README.md` の運用・リポジトリ構造
4. `docs/archive/` の過去Run仕様・検証記録

旧 `AI_Intelligence_Factory_最終仕様書.md` はRun122を基準にRun129まで追記された歴史仕様であり、内容を変更せず `docs/archive/specifications/AI_Intelligence_Factory_仕様書_through_Run129_2026-08-25.md` に保存する。Run130以降の挙動を旧仕様書から推測してはならない。

## 1. 事業・商品契約

AI Intelligence Factoryの事業構造は次で固定する。

**無料note記事 → 会員募集LP → noteメンバーシップ → 会員限定Notion Decision Intelligence + Digest**

- 無料note記事はAcquisitionチャネル。
- 有料価値は高密度な意思決定DBと会員向けDigest。
- 記事単体を有料note商品へ戻すことを前提にしない。
- subscriber PIIをGitHubの集計・attribution artifactへ持ち込まない。
- Public releaseは人間の最終操作とし、note自動化はprivate draftまで。

## 2. 運用契約

- **Daily workflowはPAUSED。**
- Production実行は明示的なONE-SHOT / workflow_dispatchを基本とする。
- API・外部サービス障害時はFail-Closedまたは局所的Fail-Safeとし、成功していない処理を成功扱いしない。
- Gemini、Notion、note、GCP等の外部状態を推測で補完しない。
- Productionの品質条件を「処理を通すため」に緩和しない。

## 3. Core Intelligence Pipeline

現行`pipeline.py` / `production_pipeline.py`の主要契約:

- 必須観測Source: GitHub / Hacker News / arXiv / Product Hunt
- Screening全体上限: 200候補
- Screening batch: 25件
- Raw Decision Score 55以上をGlobal Calibration対象とする現行設計
- Final Decision Score 60以上をStock保存対象とする現行設計
- Deep Diveは上位最大3件を基本とし、失敗時は次点Backfillを許容する
- Decision品質とCommercial Valueを混同しない
- Profit/Portfolio最適化は品質閾値・Evidence・Fact条件を迂回しない
- Observed履歴、Source ROI、deferred state等のProduction continuity dataを保持する

具体的な環境変数・重み・model候補・quota値は、将来変更され得るため実行コードとworkflowの値を優先する。

## 4. 品質・Evidence契約

現行Productionでは、記事を売るため・投稿本数を増やすためにFact/Evidence/Decision品質を下げない。

維持すべき不変条件:

- Fact / Evidence / Decisionの整合性
- Primary Sourceを優先するEvidence authority
- Publication readinessのFail-Closed
- Human Appeal / reader-first編集品質
- 非エンジニアでも核心が理解できる平易さ
- Evidenceを削って「読みやすさ」を作らない
- 比喩・会話調は理解を助ける場合に使い、Evidenceそのものとして扱わない
- Reader Experience系の診断を理由に、重大なFact/Evidence gateを緩めない

## 5. Production runtime layer

`production_pipeline.py`は現行Production entrypointであり、以下を明示順でinstallする。

- `run172_production_reliability.py`
- `run173_operational_yield.py`
- `run174_monthly_digest_integrity.py`
- `run175_semantic_fact_precision.py`
- `run176_scope_fidelity.py`
- `run177_paid_funnel_alignment.py`
- `run178_eyecatch_editorial_layout_optimizer.py`
- `run179_eyecatch_font_refinement.py`
- `run180_eyecatch_semantic_layout.py`
- `run181_eyecatch_visual_balance.py`
- `run182_eyecatch_conclusion_emphasis.py`
- `run183_eyecatch_emphasis_scale.py`
- `reader_value_review_bridge.py`
- `run194_publication_contract.py`

これらはRun番号が古く見えても現役Production codeである。整理目的だけで削除・rename・統合してはならない。

## 6. Publication Contract / note Ready契約

note投稿対象は、単にContent Intelligence側が`Ready`であるだけでは不十分。

自動投稿候補になるためには少なくとも次を満たす。

- note Ready queueで投稿可能状態である
- 現行automatic publication policy fingerprintに一致するpersisted manuscriptを持つ
- manuscript captionのSHAと本文bytesが一致する
- 必須eyecatch assetが存在する
- historical paid-area control marker等の危険なlegacy条件を含まない

古い契約、hash不一致、asset不足の行を無理に復活させない。安全条件を満たさない既存destination rowは、現行sync policyに従いReady取消/取下げとなり得る。

## 7. note private-draft automation

現行note stack:

- `note_draft_automation.py`
- `run185_note_ready_legacy_skip.py`
- `run186_note_header_image_resilience.py`
- `run187_note_editor_readiness.py`
- `run188_note_header_upload_fallback.py`
- `run189_note_editor_route_gate.py`
- `run190_note_persistent_cloud.py`
- `run191_note_crop_dialog_resilience.py`
- `run193_note_official_header_upload.py`
- `run194_note_current_contract.py`
- `run194_note_persistent_cloud.py`
- `run199_note_vm_preflight.py`

`.github/workflows/note-create-draft.yml`の現行契約:

1. GitHub-hosted Ubuntuでzero-browser / zero-Gemini preflightを行う。
2. publish-safe candidateが0件なら`no_eligible_ready`として正常終了し、GCP Chrome VMを起動しない。
3. candidateがある場合のみVM起動を許可する。
4. preflightで選択した`sync_id`を固定してVM jobへ渡し、queue順変更による別記事選択を防ぐ。
5. VM側でも現行Publication Contractを再検証する。
6. 作成するのはprivate note draftのみ。
7. 公開は人間がnote上で確認後に行う。

明示`sync_id`の不一致、Notion/API障害、Publication Contract違反、asset不足等の真の異常はFail-Closedを維持する。

note draft pathはGemini/model requestを行わない。

## 8. GCP / browser cost contract

- publish-safe candidateが0件ならGCP note Chrome VMを起動しない。
- 実draft時のみpersistent Chrome VMをon-demandで使用する。
- VMはworkflow後に停止確認を行い、guest側failsafeも維持する。
- `note-cloud-preflight.yml`は記事候補preflightではなく、GCP VM / self-hosted runner / Chrome環境診断用の別workflowとして保持する。

## 9. 保護対象データ

次は生成ゴミではなくProduction continuity / 公開参照資産であるため、通常のrepository cleanupで削除・移動しない。

- `.runtime/`
- `observed_history/`
- `source_roi_history/`
- `deferred_deep_dive/`
- `eyecatch_images/`
- `assets/`

特に`eyecatch_images/`はNotion等からURL参照されている可能性がある公開資産であり、単純dedupeやrenameを禁止する。

## 10. テスト・変更管理

- `tests/`のRun番号付きtestは、古い名前だけを理由に削除しない。現在のinvariantを検証している可能性がある。
- similarly named workflowも役割を確認してから扱う。
- Production codeのsemantic refactorはrepository cleanupとは分離する。
- main反映前にRepository-wide Falsification Guardと関連CIを通す。
- Cleanup PRでproduction Pythonの削除・renameを行う場合は、別途明示的なequivalence proofが必要。

## 11. Repository organization

rootは現在のoperator/canonical documentsと実行entrypointを優先し、過去Runの説明資料は`docs/archive/`へ置く。

Run200の整理内容と「意図的に整理しなかったもの」は次を参照する。

`docs/archive/repository-cleanup-2026-09-02/REPOSITORY_CLEANUP_MANIFEST_2026-09-02.md`
