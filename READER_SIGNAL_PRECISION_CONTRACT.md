# Reader Signal Precision Contract — Run358

## Purpose

Run358 narrows two false-positive classes reproduced from a real Gemini Production manuscript without weakening Fact, Evidence, Publication, or genuine Reader/Human Appeal review.

## Production specimen

The 2026-09-12 RubyGems article reached Publication Readiness `PASS` but Human Appeal `REVIEW`.
The audit artifact showed both genuine reader-density concerns and two deterministic detector defects.

### Confirmed false positive 1 — explained slash compound

The article contained:

`CI/CD（自動ビルド環境）`

The historical acronym detector split the compound and reported `CI` as unexplained even though the full compound had an adjacent Japanese gloss. It also reported ordinary editorial `SF` as unexplained jargon.

Run358 treats a slash-delimited uppercase compound with an adjacent parenthetical gloss as explained for each sub-token and includes `SF` in the existing common editorial acronym vocabulary.

### Confirmed false positive 2 — topic fragments interpreted as repeated insight

The historical repetition detector used seven-character cross-paragraph fragments. In the real article this classified topical wording such as:

- `エージェントの`
- `エージェントが`
- `エージェント群`
- overlapping fragments of `ドキュメント生成`

as `repetitive_insight`.

Run358 requires longer, more distinctive nine-character fragments and multiple recurring fragments across at least three distinct paragraphs. A regression case proves that genuinely duplicated long wording is still detected.

## Non-goals / safety invariants

Run358 does **not**:

- lower a quality score or review-count threshold;
- convert an article to Ready;
- bypass Human Appeal or Reader Value;
- modify Fact, Evidence, Decision, or Publication gates;
- add a provider/model call;
- change Gemini routing or Groq behavior;
- suppress genuine technical density, jargon-translation weakness, information-budget weakness, or final-publication-surface issues.

If other reader issues remain after false-positive removal, the article remains in review exactly as before.

## Regression contract

Tests must prove all of the following:

1. `CI/CD（自動ビルド環境）` does not produce an unexplained `CI` sub-token.
2. `SF` is not treated as specialist unexplained jargon.
3. RubyGems-like recurring topic nouns do not trigger `repetitive_insight`.
4. genuinely repeated long wording across three paragraphs still triggers repetition detection.
5. removing the false acronym signal does not erase unrelated accessibility/density problems.
6. installation is idempotent and uses zero provider calls.
