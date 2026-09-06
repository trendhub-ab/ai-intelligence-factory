# Run267 — Canonical Specification Sync

Date: 2026-09-07

## Purpose

`AI_Intelligence_Factory_最終仕様書.md` を現行 `main` のProduction実装・CI・依存契約へ完全同期し、Run263以降の重要な運用契約がcanonical仕様から再び抜け落ちないようFail-Closedで保護する。

## Audit result before correction

中核Production契約は概ね一致していた。

- Paid Member canonical destination / legacy isolation
- Daily hard-PAUSED / ONE-SHOT authority
- Run261 Gemini 3.7 primary / 3.8 quality repair
- GH_PAT explicit downstream fan-out
- Public note human-only publication
- active runtime manifest
- Fact / Evidence / Decision boundaries

一方、次のcurrent contractがcanonical仕様へ十分に昇格していなかった。

1. Run263 Integration hermeticity / locked deterministic CI
2. Run264 standalone Synthetic hermeticity
3. Run266 Pillow production compatibility floor `>=12.1,<13`
4. current Eyecatch stackがRun183までactiveであること
5. main ruleset required contextsと、それらのWorkflowが全PRでstatus contextを生成できる必要性

## Required-check governance correction

Direct GitHub ruleset audit on 2026-09-07 confirmed `Protect main production` requires these contexts on the default branch:

- `zero-api-regression`
- `falsify-all-tracked-surfaces`
- `notion-access-policy`

Run266 had already removed the `pull_request.paths` filter from Notion Access Policy Guard after a requirements-only PR became unmergeable with an `expected` required check.

Run267 found the same latent mismatch in `Integration Reconciliation CI`: `zero-api-regression` was required by branch protection but its pull-request trigger still had path filters. A documentation-only or otherwise unmatched PR could therefore be blocked without producing the required context.

Correction:

- `Integration Reconciliation CI` keeps `branches: [main]` but removes all `pull_request` path filters.
- `integration_stability_guard.py` now fails closed if the required Integration check regains `paths` / `paths-ignore` filtering or stops covering main.
- `run267_documentation_contract_guard.py` verifies that all three currently required contexts have a pull-request trigger without path filters and retain their exact job context names.

GitHub ruleset configuration is external state and cannot be proven by a zero-network repository guard. If the ruleset itself changes, direct GitHub ruleset audit remains required and the canonical context snapshot must be updated in the same reviewed change.

## Dependency compatibility correction

Run265 replaced deprecated Pillow `Image.getdata()` usage with `get_flattened_data()`.

Run266 aligned the declared Production lower bound with that API:

- Production range: `Pillow>=12.1.0,<13.0.0`
- CI known-green pin: `Pillow==12.3.0`

The upper bound remains `<13.0.0`; Run267 does **not** claim Pillow 13/14 Production support. A separate compatibility audit is required before broadening that range.

## Eyecatch baseline correction

The old canonical header said `Run181 current`, while current runtime order is:

1. Run181 visual balance / geometry
2. Run182 conclusion emphasis selection
3. Run183 emphasis scale

Run183 remains active with:

- `HIGHLIGHT_FONT_SCALE = 1.20`
- `HIGHLIGHT_MAX_FONT = 96`

The canonical Eyecatch baseline is therefore Run183, with Run181/182 retained as active prerequisite layers.

## Documentation governance

Run262 remains the focused fail-closed guard for the Run261 live routing and GH_PAT fan-out contract.

Run267 adds a second current-contract guard covering:

- post-Run262 CI hermeticity baselines
- Pillow compatibility contract
- required-check workflow trigger governance
- current Eyecatch baseline
- required canonical reference markers

`Repository-wide Falsification Guard` runs both Run262 and Run267 documentation guards.

## Non-goals

Run267 does not change:

- article generation logic
- Fact / Evidence / Decision gates
- Gemini request budgets or model routing
- Notion schemas or Production write destinations
- note publication behavior
- Paid Product semantics
- Daily PAUSED state

All changes are zero-provider and zero-Production-write governance changes.
