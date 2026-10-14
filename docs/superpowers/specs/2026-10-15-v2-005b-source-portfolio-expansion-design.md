# V2-005B Source Portfolio Expansion Design

## Status

Planned next bounded slice after V2-005A. This document fixes scope only; implementation starts after V2-005A is verified.

## Goal

Expand V2 live-shadow acquisition from Hacker News + arXiv to the four-source portfolio required for representative V2 selection/evidence proof:

1. OfficialVendor
2. GitHub
3. Hacker News
4. ArXiv

## Boundaries

- V1 remains Production authority.
- No Notion, note, Ready, delivery, subscriber, economic, publication, or Production mutation.
- X remains discovery-only and does not become Evidence authority.
- Product Hunt remains retired.
- Existing HN/arXiv behavior stays bounded and deterministic.
- OfficialVendor and GitHub are added as read-only acquisition adapters only.
- Selection Value from V2-005A is reused unchanged unless 4-source tests expose a specific calibration defect.
- Provider Evidence remains rank #1 only, max one request, retry 0, model fallback 0, rank fallback 0.

## Verification target

After V2-005B is implemented and verified, run 3–5 independent four-source Live Proofs before deciding whether V2-006 Evidence Contract + Article Brief may proceed.
