# Live Notion Falsification Snapshot — 2026-08-23

## Observed inventory state
- Technology Intelligence total: 342
- LEGACY_PENDING: 324
- SCREENED: 16
- ASSESSED: 1
- Subscriber-qualified at observation: 1

## Observed queue examples
High Screening Score legacy queue contained both durable Technology candidates and event/news/opinion records. Examples included durable candidates such as W&B, Hugging Face speech-to-speech, Mojo, DVC, Vespa, and ZenML, while the same high-score region also contained incidents, price news, security events, and opinion-style links.

## Decision
Screening Score alone is unsuitable as a paid-product promotion rule. It may be one planning signal, but formal Adoption assessment must still pass existing Product Review + Evidence + History + Subscriber sync.

## Live control added
A read-only `Bootstrap Queue` view was added to the internal Technology Intelligence DB. It filters to LEGACY_PENDING + RESOLVED + non-ARCHIVED + Primary URL present, ordered by Screening Score for human audit. It does not mutate Assessment State and does not call Gemini.
