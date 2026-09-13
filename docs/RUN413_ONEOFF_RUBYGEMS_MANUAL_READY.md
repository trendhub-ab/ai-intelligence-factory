# Run413 — One-off RubyGems manual Ready exception

## Scope
Operator-approved exception for Content Intelligence page `3d9479ff-dca9-819a-814c-e4a0aeb3263f` only.

## Contract
- Article body generation/repair: zero Gemini/model calls.
- Reuse exact persisted manuscript bytes only; no semantic rewrite.
- Require exact page ID, exact article title, and `記事状態=Ready`.
- Append a byte-valid current publication-policy Ready caption using `publication_contract.current_ready_caption`.
- Do not weaken publication policy or alter normal Daily/article-validation behavior.
- Dispatch normal Note Ready sync after recaption; private draft fan-out remains subject to its existing fail-closed preflight.
- Public note release remains human-only.

## Manual repair performed before Run413
The operator-approved Notion manuscript was minimally repaired without model calls: terminal title punctuation was normalized and an explicit reservation section was added using only limitations already present in the manuscript (API-key theft success unknown; internal reasoning unobservable; no generalization to all agents).

## Eyecatch
The existing production eyecatch contract remains mandatory. Run413 itself does not fabricate or bypass an eyecatch. If the source asset is absent, normal Ready sync must refuse fan-out rather than silently publish.
