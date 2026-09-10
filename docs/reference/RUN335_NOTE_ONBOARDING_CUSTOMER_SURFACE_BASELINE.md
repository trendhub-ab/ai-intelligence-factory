# Run335 — note Onboarding Customer Surface Baseline

Status: **Production verified / current**  
Date: **2026-09-10**  
Scope: paid-member note onboarding article + membership-plan customer-facing copy  
Provider cost: **0 Gemini/model calls / 0 Notion writes for verification**

## 1. Current customer-facing state

### Onboarding article

- note ID: `n284e428c80f4`
- public title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- finalized body SHA256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- membership: `AI Decision Intelligence`
- logged-out entitlement proof remains Run326b: members-only gate present and protected deep-body markers absent.

### Membership plan

- plan: `AI Decision Intelligence`
- fee: `¥1,980/月`
- exact owner edit route: `https://note.com/membership/settings/plans/358b94bcb3c6/edit`
- current description length: **114 characters**
- durable final guidance: `参加後は、メンバー限定の「最初にお読みください」記事をご確認ください。`
- legacy article-name reference `はじめに｜AI Decision Intelligenceの利用方法`: **absent**
- existing benefits preserved:
  - `AI Decision Intelligence｜会員向け意思決定DB`
  - `AI Decision Intelligence｜会員向けDigest`

## 2. Convergence proof

### Run334 — exact save

Workflow: `34433539671`

Run334 repaired only the Playwright Locator-to-DOM snapshot transport that had stopped Run333 before mutation. It then reached the exact membership plan, preserved the audited plan/fee/benefit invariants, filled only the authorized description, and executed one exact `プランを変更する` click.

The bounded immediate public verification still returned the legacy copy and the workflow failed closed. Because the final click had already occurred, the updater was **not rerun**.

### Run335 — zero-mutation state audit

Workflow: `34433925788`  
Artifact: `10135503385`  
Artifact SHA256: `8b398e98853b2629ba07d43f47c5d23b316908827e2cb6f73c991a391008872c`

Observed state:

- `public_state=current`
- `edit_state=current`
- `public_edit_consistent=true`
- `plan_name_verified=true`
- `fee_marker_verified=true`
- `benefits_verified=true`
- `description_chars=114`
- clicks `0`
- fills `0`
- saves `0`
- Gemini/model calls `0`
- Notion writes `0`

Conclusion: **Run334 saved successfully.** Its post-save failure was a short public-propagation/cache false negative, not a failed save.

## 3. Production operator contract

1. Do not resave the membership plan merely because an immediate public read briefly shows the prior copy after a confirmed exact save.
2. First compare the server-saved edit form and public customer surface with a read-only audit.
3. If both are current, stop: no additional click, fill, or save is authorized.
4. Any future membership-copy mutation must remain hard-bound to the exact plan, expected prior/current copy, plan-name/fee/benefit invariants, and an explicit manual command.
5. Do not change `すべてのプラン（全員に公開）`, trial-read behavior, plan price, or existing benefits as part of onboarding-copy maintenance.

## 4. Relationship to prior baseline

`docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md` remains the historical/current contract for Run325 article finalization and Run326b logged-out members-only verification. This Run335 reference adds the now-verified membership-plan customer surface and supersedes Run326b **only as the top-level note onboarding customer-surface baseline**; it does not replace the underlying Run325/326b article contracts.

Public purchase-funnel rendering and logged-out join-page verification are governed separately by `docs/reference/RUN339B_NOTE_PUBLIC_PURCHASE_FUNNEL_BASELINE.md`. Run339b does not replace Run335 saved-state authority and does not authorize a membership resave.
