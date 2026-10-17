# Stage 3 — Blind Holdout 10 Result

## Primary result

**0 / 10 all-Gate pass (0%).**

This is the pre-registered blind result. Local Writer v3 was frozen before selection and was not modified after measurement started.

- Blind workflow run: 36178520779
- Frozen writer blob: `dbb7d03fa4afc7ea8e7d1e24b70e0ddcb884f0e2`
- Full regression aside from the deliberate holdout assertion: **2,927 passed / 1 warning**
- Repository-wide Falsification Guard: SUCCESS
- Notion Access Policy Guard: SUCCESS
- Production synthetic smoke: skipped because the pre-registered holdout assertion failed first

## Failure decomposition

- Fact Gate PASS: **1/10**
- Human Appeal ACCEPTABLE: **4/10**
- Editorial Gate: **10/10 non-blocking**
- Publication Readiness: **10/10 PASS**
- Title punctuation contract failure: **9/10**
- Unsupported hype/exclusivity: **3/10**
- Unsupported ROI/financial outcome: **3/10**
- Human Appeal WEAK: **6/10**
- Cross-article fingerprint high: **1/10**

## Interpretation

Stage 2's 5/5 result does not generalize to this untouched holdout. The dominant newly exposed issue is an input-contract mismatch: the Local Writer copies `note記事タイトル`, while the Fact Gate requires a title ending in `。` or `？`; 9 of the 10 eligible real records did not satisfy that contract.

Other failures show that structurally complete records can still contain editorial or interpretive material that is not publication-safe: hype/exclusivity language, unmeasured ROI claims, and unexplained specialist terms. `Source Native` therefore does not imply that every stored Decision/Title/Why field is safe to render verbatim.

Three records (Memmy Agent, Working with AI Feels More Like Leadership Than Coding, and the cardiology world-model paper) were blocked only by title punctuation while already passing Human Appeal, Editorial, and Publication. That is a diagnostic observation, not a revised holdout score.

## Per-record result

| Source | Record | Fact | Publication | Human | All Gates |
|---|---|---|---|---|---|
| GitHub | Memmy Agent | FAIL: title must end with 。 or ？ | PASS | ACCEPTABLE | FAIL |
| GitHub | mlflow/mlflow | FAIL: title must end with 。 or ？ / unsupported exclusivity/hype: 必須インフラ | PASS | WEAK: reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity) / reader_value_review:multi_axis_reader_weakness (accessibility/reader_enjoyment/jargon_translation/non_engineer_core_clarity) | FAIL |
| HackerNews | Working with AI Feels More Like Leadership Than Coding | FAIL: title must end with 。 or ？ | PASS | ACCEPTABLE | FAIL |
| HackerNews | Maximizing the value of your Claude Code sessions | FAIL: title must end with 。 or ？ / unsupported hype: 劇的 / unsupported outcome extrapolation: ROI/financial outcome not measured by evidence | PASS | WEAK: cross_article_fingerprint_high | FAIL |
| ArXiv | Intervention-Aware Clinical World Model for Post-Op Outcome Forecasting in Cardiology | FAIL: title must end with 。 or ？ | PASS | ACCEPTABLE | FAIL |
| ArXiv | TabSOM: A tabular-to-image encoding method based on self-organizing maps | FAIL: title must end with 。 or ？ / unsupported outcome extrapolation: ROI/financial outcome not measured by evidence | PASS | WEAK: reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity) / reader_value_review:multi_axis_reader_weakness (accessibility/reader_enjoyment/jargon_translation/non_engineer_core_clarity) | FAIL |
| OfficialVendor | Wispr Flow Notetaker | FAIL: title must end with 。 or ？ / unsupported hype: 劇的 | PASS | WEAK: reader_value_review:non_engineer_access_failure (Accessibility/Information Budget/Jargon Translation/Non-Engineer Core Clarity) / reader_value_review:multi_axis_reader_weakness (accessibility/reader_enjoyment/jargon_translation/non_engineer_core_clarity/information_budget) / reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity) | FAIL |
| OfficialVendor | Dograh | FAIL: title must end with 。 or ？ / unsupported outcome extrapolation: ROI/financial outcome not measured by evidence | PASS | ACCEPTABLE | FAIL |
| HackerNews | RISC-V: They Should Have Known Better | PASS | PASS | WEAK: reader_value_review:non_engineer_access_failure (Accessibility/Information Budget/Jargon Translation/Non-Engineer Core Clarity) / reader_value_review:multi_axis_reader_weakness (accessibility/reader_enjoyment/jargon_translation/non_engineer_core_clarity/information_budget) / reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity) / reader_value_review:final_surface_summary_jargon_cluster (何が出た？/なぜ重要？) | FAIL |
| HackerNews | RustDesk now supports true unattended remote access on Wayland | FAIL: title must end with 。 or ？ | PASS | WEAK: reader_value_review:non_engineer_access_failure (Accessibility/Opening/Information Budget/Jargon Translation/Non-Engineer Core Clarity) / reader_value_review:multi_axis_reader_weakness (accessibility/curiosity_pull/reader_enjoyment/jargon_translation/non_engineer_core_clarity/information_budget) / reader_value_review:non_engineer_access_failure (Accessibility/Jargon Translation/Non-Engineer Core Clarity) | FAIL |

## Stage 3 conclusion

**Do not promote Local Writer v3 directly to Production.** The holdout falsifies the hypothesis that the v3 writer alone is sufficient for arbitrary structured records.

The next architecture to test should separate two responsibilities:

1. a deterministic Structured Input / Publication Canonicalizer that enforces the existing Production contracts without inventing facts, and
2. the Local Writer, which composes prose only from the canonicalized structured input.

Any such change must be developed on a separate development set and validated on a new holdout; this Stage 3 holdout must not be reused for tuning.
