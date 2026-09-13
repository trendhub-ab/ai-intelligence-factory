# Run397 implementation note

Run397 is intentionally implemented as a late precision overlay in `reader_quality_precision.py`, which is installed after the historical runtime stack. This allows the new policy to refine the signals consumed dynamically by Run248 without rewriting historical Run248/Run249 code or weakening their Fact/Evidence/Publication responsibilities.

The change does not convert all technical articles to PASS. It only removes density-derived accessibility penalties for MEDIUM/LOW plainness topics when all Decision Accessibility dimensions and required-term explanation are proven by deterministic signals.
