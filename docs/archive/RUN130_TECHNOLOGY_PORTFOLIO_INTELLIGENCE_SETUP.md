# Run130 — Technology Portfolio Intelligence

## Business decision

AI Intelligence Factory does **not** become a generic popular-AI catalog.
Its differentiation is overseas AI/IT technology intelligence translated into
reader-friendly note articles and decision-ready paid intelligence.

The defect found before launch was not “too much technology”. It was that the
subscriber inventory could become a proxy for discovery source composition,
especially GitHub OSS.

## Product layers

The paid portfolio intentionally contains three soft layers. These are portfolio
planning concepts, not Adoption statuses and not forced quotas.

1. **APPLIED_AI** — directly usable AI products/services only when the underlying
   technical change has decision value. Fame alone is not a reason to include it.
2. **PRACTICAL_TECH** — agents, MCP, RAG/retrieval, AI security, data, inference,
   observability, infrastructure, multimodal, models and meaningful developer tooling.
3. **DEEP_TECH** — emerging research, mechanisms and architectures that can change
   future decisions.

note and AI Decision Intelligence cover the same technology world at different
resolutions: note makes it understandable and enjoyable; the paid DB makes it actionable.

## Run130 implementation

- `technology_portfolio_policy.py`
  - removes the large automatic GitHub source advantage from bootstrap planning;
  - keeps Screening/relevance as the dominant planning signal;
  - adds a soft three-layer portfolio classifier;
  - penalizes repeated source/category/layer concentration;
  - penalizes generic GitHub DEVTOOLS/OTHER repositories when they have no strategic
    technology/decision signal;
  - does **not** modify Adoption Score, Adoption Status, Evidence, Product Review or
    Notion write contracts.
- `portfolio_inventory_bootstrap.py`
  - installs the policy as a reversible planning overlay and delegates to the mature
    `inventory_bootstrap.py` implementation.
- `.github/workflows/inventory-bootstrap.yml`
  - uses the portfolio-aware entry point;
  - lowers the default one-source planning cap from 0.60 to 0.45;
  - passes the cap in both plan and apply modes.

## Falsification constraints

Run130 must be rejected if any of the following occurs:

- GitHub/ArXiv candidates are excluded merely because of source;
- a lower-quality candidate is force-promoted to satisfy a quota;
- Adoption or Evidence semantics change;
- plan mode consumes Gemini;
- apply can invoke article screening/deep-dive Gemini paths;
- existing `inventory_bootstrap.py` safety contract is bypassed;
- popular AI products receive an automatic inclusion bonus merely for brand awareness.

## Expected effect

The queue should stop behaving like “best GitHub repositories first” and instead
behave like “strongest decision-relevant technology portfolio first”, while preserving
Deep Tech as a differentiated part of the product.
