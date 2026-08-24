# Run122 Real Article Regression Hardening — Validation

Date: 2026-08-24
Baseline: Run121 Article Quality Logic

## Trigger

GitHub Actions `Real Article Regression Test` produced 3/3 rejected artifacts after Run121 main integration. The observed rejection reasons were:

- Kobo / Cobalt: `source-boundary unsupported named fact: Cobalt SDK` + `missing observation or reservation`
- The New MCP Roadmap: legacy required-heading failures + `ARTICLE_STRUCTURE_INCOMPLETE` + `missing observation or reservation`
- ESP32 / Docker Sandboxes: `INTERNAL_DRAFT_DELIMITER_LEAKED` + `source-boundary unsupported named fact: Espressif IoT, Development Framework` + `missing observation or reservation`

The patch treats these as falsification fixtures, not as reasons to weaken Fact safety globally.

## Root-cause findings

1. Run108 removed fixed public heading names, but Fact Gate still retained a legacy semantic-heading hard-fail path.
2. Humanization reservation detection recognized too small a vocabulary and could miss explicit constraints/risks.
3. Source Boundary lacked the canonical ESP-IDF full-name alias and could interpret `target entity + SDK` as a distinct unsupported product.
4. An exact generation transport control line could survive parsing long enough to be treated as a factual publication defect, despite being deterministically removable.

## Implemented logic

- Removed public heading-name requirements from Fact Gate.
- Added `article_structure_needs_edit` to Publication Readiness for long-form articles with fewer than 2 Markdown section headings.
- Expanded reservation semantics: constraints, limitations, risks, issues, unverified/unsupported states, trade-offs and no-warranty language.
- Added explicit `ESP-IDF` / `Espressif IoT Development Framework` alias group.
- Added target-bound `Entity + SDK/API/CLI` exception requiring target identity + descriptor evidence; unrelated entities remain blocked.
- Stripped exact standalone NOTE_DRAFT transport lines immediately after response parsing; inline marker-like prose is not silently removed.

## Falsification tests

Dedicated Run122 tests: **10/10 PASS**.

Negative controls: **3/3 KILLED**.

1. Broadly allow every `Entity + SDK/API/CLI` without target binding -> killed by unrelated `OpenAI SDK` case.
2. Remove ESP-IDF canonical alias -> killed by full-name source-boundary case.
3. Disable parser control-line stripping -> killed by NOTE_DRAFT_END leak case.

## Full regression

- unittest: **604/604 PASS**
- pytest: **604 passed + 19 subtests PASS**
- Synthetic Regression self-test: **PASS**
- Synthetic Full: **500/500 PASS**
- Critical failures: **0**
- Major failures: **0**
- Critical invariants: **PASS**
- Production write isolation: **true**
- compileall: **PASS**
- Workflow YAML parse: **8/8 PASS**
- Production `_generate_via_chat(` call sites: **7**
- Production `genai.Client(` call sites: **1**

## Production-E2E boundary

This environment cannot truthfully re-run the GitHub Actions Real Article Regression with the user's live Gemini quota. Therefore this package is locally/adversarially validated, but the same 3 real articles must be re-run through `Real Article Regression Test` after main integration. Do not claim Production E2E completion until that action has run and its artifacts have been inspected.
