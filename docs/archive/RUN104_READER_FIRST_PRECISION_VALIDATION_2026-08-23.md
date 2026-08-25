# Run104 Reader-First Precision Validation — 2026-08-23

## Baseline
- Production baseline: Run102 PublishYieldPrecision.
- Reader-first branch: Run103 ReaderFirstArticleFormat.
- This Run104 is a narrow hardening of the Reader-first branch after human inspection of the real Ready artifact `The New MCP Roadmap`.
- No ProfitMeasurementHardening changes are merged.

## Business objective
Improve first-30-second comprehension and audit trust without adding Gemini requests, weakening Quality Gates, or changing Notion/product economics.

## Changes
1. Reader summary readability
   - `何が出た？` selects the least jargon-heavy existing sentence among gated `Source Summary`, a factual intro sentence, and `What`.
   - No new AI call and no synthetic factual rewrite.
   - Reader summary default maximum shortened from 135 to 110 characters.
2. Duplicate opening removal
   - When the Reader-first header exists, boilerplate provenance sentences such as `本記事は…一次情報に基づいています` are removed from the body.
   - The early conclusion section (`先に判断を書くと。` and aliases) is removed because `結論は？` already serves that function.
   - The final conclusion/Action remains intact.
3. Temporal specificity precision
   - Unsupported vague durations such as `半年` are checked.
   - `coming months` can support `数ヶ月`, but cannot be silently expanded to `半年`.
   - Explicit `six months` / `half a year` can support `半年`.
4. Article Audit isolation
   - Production `main()` resets `article_audit/` before the run starts.
   - `article_audit/` is gitignored.
   - Tests that can persist Ready/Pending/Failed artifacts now use temporary audit directories.
   - Full unittest execution leaves no repository-local `article_audit/` residue.

## Unchanged
- Fact Gate / Editorial Gate / Publication Readiness Gate / Human Appeal Gate ordering and core thresholds.
- Evidence sufficiency and Primary Source Authority rules.
- Notion persistence and Ready definition.
- Screening / calibration / Deep Dive model budgets.
- Subscription attribution logic and landing URL configuration requirement.
- Source ROI and profit-priority ranking.

## Validation
- Targeted Reader/Audit/Adversarial tests: PASS.
- `unittest discover`: 442 / 442 PASS.
- `pytest`: 442 passed + 10 subtests PASS.
- Synthetic Full: 500 / 500 PASS, critical failures 0, production write isolation true.
- Python compileall: PASS.
- GitHub Actions YAML parse: 5 / 5 PASS.
- Manual MCP regression:
  - jargon-heavy `What` resolves to the least-complex existing gated candidate;
  - duplicate source sentence and early conclusion section are removed;
  - `coming months` + unsupported `半年` is rejected as `unsupported vague quantified claim: 半年`.
- Test artifact isolation: no repository-local `article_audit/*.md` remains after full unittest.

## Acceptance recommendation
Recommended as the next Reader-first production candidate after Run102. Keep Run102 as Source of Truth until the user deploys this Run104 package.
