# AIIF Gemini Single Shared Quota Ledger — runtime-state normalization (2026-10-24)

**Status:** corrective implementation candidate; no Production merge without MERGE GO. No Gemini calls required for proof.

## Root cause and evidence

On 2026-10-24, P5 run #40103331690 (triggered by owner-only Issue #71 ChatOps) passed provider-free tests and Telegram private-recipient preflight, then stopped at `PersistentGeminiDailyCounter.reserve` BEFORE the first Gemini call. GitHub Contents PUT to `main:.runtime/gemini_daily_usage.json` returned HTTP 409 because the active `Protect main production` ruleset #22101771 requires PRs and three checks. Disabling the safety counter or relaxing main protection is forbidden.

Existing `runtime-state` branch is writable and already the authoritative target of `article-revalidation-apply.yml`. It contained the canonical SHA-hashed repository counter scope, last quota date 2026-10-20. `main` contained an older quota_date 2026-09-02. Do not create a second quota database or replace newer runtime history with the stale main copy.

On 2026-10-24, performed a ZERO-Gemini, compare-and-swap write/round-trip proof on the real `runtime-state:.runtime/gemini_daily_usage.json` (commit `a3c5ff91f910887c3138369dc406332cd4e9adda`). All model counts, quota_date and scope were preserved. The private branch is not covered by the default-branch PR protection rule.

## Correction

- Repoint ALL known workflows with `GEMINI_PERSISTENT_DAILY_COUNTER=true`, including Daily, P5 A–E, inventory, article revalidation, Recovery, Issue 668/683/698, Ready draft, eyecatch, regression, to **one branch** `runtime-state` and **one path** `.runtime/gemini_daily_usage.json`.
- Preserve `GEMINI_QUOTA_FALLBACK_ID=github.repository` on Daily and P5; native `PersistentGeminiDailyCounter` hashes a stable repository scope and enforces per-model and per-run budgets.
- Preserve GitHub Contents API blob SHA compare-and-swap, 409 retry/re-read, fail closed on HTTP or missing credentials, and `ai-intelligence-gemini-budget` concurrency. Do not replace CAS with direct push, disabled counter, branch-specific divergent quota, or public model prompts.
- Retire Issue 668's historical automatic `push: [main]` trigger in favor of manual `workflow_dispatch`: otherwise updating that workflow as part of this fix would fire paid provider calls without an explicit owner request.
- Add static workflow-contract tests and provider-free mocked native CAS tests. They ensure all Gemini-persistent workflows select `runtime-state`, all share concurrency, and concurrent 409 does NOT discard existing counts.
- The counter is **repository-local**, not an exact provider-wide quota ledger. Gemini API requests made via other repositories, AI Studio, or disconnected experiments remain outside its visibility. At day rollover (`America/Los_Angeles`) the existing normalizer creates the new quota_date state automatically. Do not claim today's aggregate provider consumption without provider dashboard evidence.

## Rollout and verification

1. Keep `main` and the one-shot ChatOps trigger unchanged until approved MERGE GO for this corrective PR.
2. After merge, perform an offline Actions preflight (zero Gemini requests) and verify all workflow envs and branch selection on main.
3. Perform **one** bounded P5 owner ChatOps dispatch only after checking no active model workflows, 17:00 JST restriction, encryption/Telegram private-chat preflight, and native Gemini quotas.
4. Keep P5 raw drafts out of public GitHub/Notion/note; only encrypted review artifact, with decryption key sent separately to verified private Telegram.
5. A completed P5 live run is not an automatic article quality gate or publication authorization; blind human review + Evidence/Fact/Publication gates remain mandatory.

## Regression boundary

This change alters selected workflow quota **storage address** and disables an unapproved historical push trigger. It does NOT change `pipeline.py` budget mechanics, V1/V2/Classic, note/Notion writes, Writer prompts, Gemini models or sampling parameters, or main-branch protection.
