# Run228 — Reader Rhythm Planning

## Purpose

The first FULL Production run after Run226 confirmed that article-specific angles and curiosity improved, but several manuscripts still triggered `reader_value_review:dense_report_cluster`. The recurring failure mode was not missing Evidence; it was **Evidence arriving faster than the article converted it into understanding, consequence, and decision**.

Run228 improves that layer without adding Gemini calls, lowering Evidence density, or introducing a new writing template.

## Production behavior

`run228_reader_rhythm_planning.py` appends an idempotent planning contract to the existing article-generation prompt after Run226.

The same generation request is instructed to:

- avoid stacking technical facts, benchmarks, and implementation details as a report-only cluster;
- move from necessary mechanism/detail into reader meaning or decision consequence before accumulating unrelated detail;
- keep one main explanatory spine and omit secondary implementation inventory that changes neither core understanding nor Decision;
- preserve important numbers, conditions, counter-evidence, and constraints;
- bridge specialist terms at the point of use instead of adding dictionary-like definition blocks;
- use tables/lists when they are genuinely clearer, rather than forcing everything into conversational prose;
- treat clarity, discovery, and decision usefulness as Reader Delight for serious topics where forced lightness would be inappropriate.

## Non-template contract

Run228 does **not** require fixed counts for:

- sentence length
- paragraph length
- rhetorical questions
- metaphors
- bullets
- headings
- conversational markers

It does not force a shared article order such as `problem → metaphor → three bullets → "私なら"`.

## Evidence boundary

Reader Rhythm never outranks Fact/Evidence safety.

Run228 must not:

- invent a number, person, dialogue, adoption result, causal claim, competitor fact, or usage scene;
- remove a source condition or caveat merely to make prose lighter;
- drop important Evidence to evade Information Budget diagnostics;
- add filler phrases such as `つまり`, `実は`, `ここで重要なのは`, `ですよね` mechanically.

## API / runtime invariants

- new Gemini/model call sites: **0**
- article-generation request count: unchanged
- Fact / Evidence / Decision / Publication gates: unchanged
- Reader Value diagnostics: unchanged and still fail/review independently
- Daily: PAUSED
- public note release: human-only

## Publication policy

Run228 can materially change public article text and is therefore included in `PUBLICATION_POLICY_FILES`. Old Ready manuscript fingerprints are not current-policy Ready after Run228 changes until they are reconciled/re-generated under the current policy.

## Regression evidence

`tests/test_run228_reader_rhythm_planning.py` verifies:

- Evidence-preserving dense-report guidance;
- absence of fixed style-count quotas;
- idempotent prompt augmentation;
- no additional call site introduced by installation.
