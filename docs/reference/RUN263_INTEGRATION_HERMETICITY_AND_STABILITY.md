# Run263 — Integration Hermeticity and Stability

Date: 2026-09-06

## Purpose

`Integration Reconciliation CI` がProduction不具合ではない stale test contract / dependency drift / accidental external I/O で繰り返し赤く見える構造を解消し、赤なら「実際に現在契約のどこかが壊れた」と判断しやすいCIへ戻す。

## Root causes confirmed

1. **Umbrella duplication** — Integrationは多数の個別unittest群を実行した後、同じtestsをfull pytestでも再実行していた。1件のstale assertionでも巨大job全体が赤くなり、故障箇所の意味が曖昧だった。
2. **Duplicated runtime manifest** — `tests/test_run231_pipeline_slim.py` が `runtime_layers.RUNTIME_LAYER_ORDER` 全体を別tupleとして手書きコピーしていた。正当なruntime layer追加でもcopy更新漏れだけでIntegrationが失敗した。
3. **Accidental real GitHub REST I/O** — `test_run130_fresh_article_regression_reconciliation.py` がfake `GH_PAT`を設定した結果、module-global persistent Gemini counterが有効化され、zero-api-regression中にGitHub Contents APIへ実通信してHTTP 401を発生させていた。例外がsummary文字列へ変換されるためテストはGreenになり、外部I/Oだけが隠れていた。
4. **Dependency drift** — `requirements.txt` とpytestがrange指定で、コード無変更でも新しいminor/transitive dependencyを取得できる状態だった。
5. **Manually maintained compile inventory / artifact step** — Integration内にPython対象の長い手書き一覧と、回帰判定に不要なsource artifact uploadがあり、CI自身の変更表面を増やしていた。

## Fixes

- CI専用 `requirements-ci-constraints.txt` を追加し、2026-09-06にGreenだった依存グラフへ固定。
- runnerを `ubuntu-24.04`、Pythonを `3.11.16`、pipを `26.2.1`へ固定。
- `tests/conftest.py` のautouse fixtureでpytest中の外部socket接続をFail-Closed。loopbackだけ許可し、GitHub/Notion/provider通信はmock必須。
- Integration job全体でも `GEMINI_PERSISTENT_DAILY_COUNTER=false`。
- Run130 testはpipeline import前にpersistent counterを明示OFFにし、disabled状態を回帰確認。
- runtime layer testはcanonical `runtime_layers.RUNTIME_LAYER_ORDER` を唯一のmanifest Source of Truthとして使い、重要な順序関係だけsemantic invariantとして検査。
- Integrationを `stability guard → repository falsification → full pytest once → Synthetic smoke` へ単純化。coverageはfull pytestで維持し、重複実行だけを削除。
- `python -m compileall -q *.py tests` へ変更し、compile対象の手書き一覧を廃止。
- 回帰判定に不要なpipeline source artifact uploadをIntegrationから削除。
- `integration_stability_guard.py` とunit testを追加し、上記契約をrequired `falsify-all-tracked-surfaces` 内でもFail-Closed保護。

## Non-changes / safety

- Article Fact / Evidence / Decision Gate: unchanged.
- Reader / Publication / Eyecatch gates: unchanged.
- Gemini routing (Run261): unchanged.
- Deep Dive per-run 12 / model safety budgets: unchanged.
- Notion schema/write destinations: unchanged.
- Scheduled Daily: **PAUSED**.
- Public note release: **human-only**.
- Gemini/provider requests used by this implementation: **0**.

## Acceptance

Run263 is acceptable only when the PR head and merged main both show:

- `zero-api-regression` SUCCESS under the locked environment.
- pytest full suite SUCCESS while external sockets are blocked.
- Synthetic smoke SUCCESS with production write isolation.
- `falsify-all-tracked-surfaces` SUCCESS including Integration Stability Guard.
- `notion-access-policy` and Workflow Reference Guard remain SUCCESS.

A real ONE-SHOT is not required for Run263 because this change is CI-only and must not consume Gemini quota or write Production data.
