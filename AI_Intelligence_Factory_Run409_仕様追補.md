# AI Intelligence Factory Run409 仕様追補

## 目的
2026-09-13の承認済みRubyGems実記事 Run399 #11 で、Run408によりGemini 3.5 Flashまで正しくフォールバックし、Quality RetryはHTTP 200で成功した。再Gate後、Fact由来の失敗は解消しPublication ReadinessもPASSしたが、残存失敗はReader-onlyだった。

残った理由は以下。
- `dense_report_cluster`
- `multi_axis_reader_weakness`
- `non_engineer_access_failure`
- `final_surface_summary_jargon_cluster`

しかしretry policyは `run360_base_quality_retry_already_spent` を返して停止した。原因はRun208/360の所有権判定順序で、基礎Quality Retryを1回使った後、Reader-only状態でもbase retry exhaustionが先に返り、Run360が元来用意している専用Reader Repairの判定へ到達できない場合があるためである。

## Run409の変更
通常ProductionのRun208/360は変更しない。`candidate_origin=approved_article_apply` に限り、wrapped policyが `run360_base_quality_retry_already_spent` を返した場合、以下をすべて満たすときだけRun360の既存専用Reader Repair所有権をclaimする。

- Evidence stateが`SUFFICIENT`。
- `decision_scope_safe == true`。
- 全blocking rowがReader Value系。
- HARDを含まない。
- 全blocking rowがcanonical `_FRESH_REPAIRABLE` 対象。
- canonical Reader Repairが未使用。

許可理由は `run409_approved_canonical_reader_repair` とする。

## 重要な意味
Run409は新しいretry枠を追加しない。Run360が元から持つ「ordinary quality retry 1回 + dedicated Reader Repair 1回」のうち、実Run #11で所有権判定順序により隠れていた後者を正しく使えるようにするだけである。

## 不変条件
- `ARTICLE_REVALIDATION_REQUEST_BUDGET=5` を変更しない。
- `GEMINI_DEEP_DIVE_PER_RUN_REQUEST_BUDGET=5` を変更しない。
- 各GeminiモデルのDaily Safety Budgetを変更しない。
- Fact / Evidence / Publication / Human Appeal / Reader Gateを緩和しない。
- non-reader blockerやHARD blockerでは発動しない。
- 通常Daily / article_validation / pending_retry / new candidateのretry policyは変更しない。
- Run406/407のoptional second Reader Repair条件は変更しない。
- Run408 provider fallback contractは変更しない。
- Xロジックは変更しない。
- note.com公開契約は変更しない。今回の到達点はprivate draftまでで、公開は手動。

## 反証テスト
- 実Run #11のReader-only 4理由 + safe evidence + approved lane + base retry spent → canonical Reader Repairを1回だけ許可。
- 同条件2回目 → `run360_reader_repair_already_spent`。
- new / article_revalidation / pending_retry → base retry exhaustionをそのまま維持。
- non-reader / HARD / Evidence insufficient / decision_scope_safe=false →発動禁止。
- 別のbase reasonは上書きしない。
- installは冪等、canonical retry policy欠落時はFail-Closed。
