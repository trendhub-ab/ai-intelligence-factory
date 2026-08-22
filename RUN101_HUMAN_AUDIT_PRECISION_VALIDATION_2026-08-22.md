# Run 101 Human Audit Precision Validation — 2026-08-22

## Purpose
Run 100 Article Auditの実記事監査で確認したGate偽陽性を、品質基準を緩めず修正する。

## Changes
1. Evidence Alias / Acronym recognition
   - MCP ↔ Model Context Protocol
   - RAG ↔ Retrieval Augmented Generation
   - TTS ↔ Text to Speech
   - short acronym token-boundary protection
2. Editorial severity split
   - `mechanical ordinal structure` is audit-only soft warning
   - material list-like / repetitive / structural defects remain blocking
   - soft-only warning does not spend Quality Retry
3. Run-local heading profile balancing
   - same article keeps its profile during retry
   - new articles rotate through least-used profiles to avoid same-run template collision

## Run 100 Regression Fixtures Added
- MCP full-name accepted when primary evidence contains MCP.
- Alias expansion cannot legitimize unrelated named facts.
- `storage` cannot accidentally trigger the `RAG` alias.
- Ordinal structure alone remains visible but non-blocking.
- Material list-heavy prose remains blocking.
- ESP32 and Kobo receive different run-local display profiles while retry remains stable.

## Validation Results
- Dedicated Run 100 human-audit regression: 6/6 PASS.
- Full unittest: 409/409 PASS.
- pytest: 409 passed + 10 subtests passed.
- Synthetic Regression Full: 500/500 PASS.
- Synthetic critical failures: 0.
- Synthetic production write isolation: true.
- No Gemini/API request was used by the validation suite.

## Safety Position
This release does not relax Fact Gate evidence requirements. It improves evidence equivalence recognition and separates a cosmetic editorial signal from material publication defects. Explicit unsupported actor/product relationships and unrelated named facts remain hard failures.
