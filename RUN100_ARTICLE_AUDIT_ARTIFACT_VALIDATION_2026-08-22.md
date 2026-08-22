# Run 100 Article Audit Artifact Validation — 2026-08-22

## Purpose
`private-gate-review`にJSONしかなく記事本文を人間監査できない問題を解消する。Gateを弱める修正ではなく、既存生成稿を0 APIで監査用Markdownとして保存する。

## Implemented
- Ready: final publishable manuscript only.
- Quality Failed: generated_original / after_quality_retry / final_after_rescue (available stages only).
- Pending Retry: latest available current manuscript.
- Needs Editorial Review: current manuscript in unified Article Audit tree (legacy review_candidates Markdownも維持).
- Notion persistence failure after Quality PASS: Pending Retry audit manuscriptを保存。
- `RUN_SUMMARY.md` index and Ready eyecatch copy.
- `.github/workflows/daily.yml`の`private-gate-review-${{ github.run_number }}`へ`article_audit/`を追加。
- Additional Gemini/API calls: 0.

## Falsification / counter-checks
1. Quality Failedの`final_after_rescue.md`がRescue前稿を誤保存しないことを確認。Rescue後draftを独立snapshotとして保持。
2. Readyは中間稿を過剰保存せず最終稿だけ残す。
3. Pending Retryは本文がある場合の最新稿を残す。
4. Audit writerにGemini呼び出し依存がない。
5. Article Audit保存はprivate artifact経路のみで、Repository commit経路へ追加しない。
6. 既存Gate/Decision Intelligence/Eyecatchロジックを変更しない。

## Validation
- Dedicated Article Audit tests: 5/5 PASS.
- All unittest: 403/403 PASS.
- pytest: 403 passed + 10 subtests passed.
- Synthetic Regression Full: 500/500 PASS.
- Synthetic critical failures: 0.
- Production write isolation: true.
- Python compile: PASS.
- Workflow YAML parse: PASS.
- Font binaries bundled: 0.

## Expected artifact tree
```text
private-gate-review-<run>/
├─ article_audit/
│  ├─ RUN_SUMMARY.md
│  ├─ articles/
│  │  ├─ ready/.../final.md
│  │  ├─ quality_failed/.../generated_original.md
│  │  ├─ quality_failed/.../after_quality_retry.md
│  │  ├─ quality_failed/.../final_after_rescue.md
│  │  ├─ pending_retry/.../current.md
│  │  └─ needs_editorial_review/.../current.md
│  └─ eyecatch/*.png
├─ review_candidates/
├─ quality_failures/
├─ gate_history/
└─ regression_cases_pending/
```
