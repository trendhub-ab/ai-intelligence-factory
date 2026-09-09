# Run327 — note Member Onboarding Production Baseline

Date: 2026-09-10 JST  
Status: **Current Production contract**  
Canonical target: `n284e428c80f4`

## 1. Purpose

This document records the verified Production contract for the paid-member onboarding note after Run324–Run326b. It separates three concerns that had previously been mixed together: saving the newest draft on note, finalizing that draft as the existing published article, and proving the customer-facing members-only surface from a logged-out browser.

No model inference is part of this contract. The maintenance and audit paths use zero Gemini/model calls and zero Notion writes.

## 2. Canonical note state

- Note ID: `n284e428c80f4`
- Public URL: `https://note.com/trendhub_biz/n/n284e428c80f4`
- Current title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- Legacy title: `【最初にお読みください】AI Decision Intelligenceの利用方法`
- Exact finalized body SHA256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- Membership plan retained: `AI Decision Intelligence`
- All-plans exposure: **not added**
- Trial-read line: **not selected**
- Resulting access contract: the full article remains members-only.

## 3. Run324 — note UI contract discovery

Run323 proved that the existing article reached the correct publish-settings URL but did not expose a normal final `更新する` control. Run324 then followed the exact existing-article/latest-draft route and opened only `試し読みエリアを設定`.

Observed Production UI contract:

1. Existing article → `編集`
2. Select the latest unpublished draft
3. `公開に進む`
4. Normal publish settings contains no final `更新する`
5. Open `試し読みエリアを設定`
6. `更新する` appears exactly once

Run324 observed 389 candidate trial-read positions and selected none. The note UI stated that when no trial-read line is selected, the article remains available only to subscribers/members.

Run324 made no public, membership, or settings mutation.

## 4. Run325 — exact latest-draft finalization

Run325 repaired the live onboarding-maintenance workflow to use the UI route actually proven by Run324.

Hard-bound route:

`existing article → edit → latest draft → 公開に進む → 試し読みエリアを設定 → select no line → 更新する once`

Safety conditions:

- exact target note ID only;
- exact server-saved title and body SHA must match before progression;
- current article-list card must match the known existing-published state or the run fails closed;
- no trial-read line may be selected;
- exactly one final `更新する` click is permitted;
- membership selection itself is not changed;
- a rerun is idempotent: if the article is already converged, no public update is clicked again.

Live evidence:

- Workflow run: `34388876334`
- Result: `latest_draft_published_and_membership_verified`
- `final_update_clicked = true`
- `trial_read_line_clicked = false`
- `public_mutation = true`
- `membership_mutation = false`
- `settings_mutation = false`
- post-update article-list card shows the new title and `公開中`;
- `追加編集された未公開の下書きがあります` is absent;
- legacy published title is absent;
- membership dialog verifies `AI Decision Intelligence 追加済`;
- `すべてのプラン（全員に公開）` remains not added;
- zero Gemini/model calls;
- zero Notion writes.

Run325 evidence artifact: `run325-onboarding-update`.

## 5. Run326b — logged-out customer-facing verification

Run326 added a completely read-only external audit of the public URL. Run326b corrected one audit-only false positive: note.com creates `_note_session_v5` for a fresh anonymous visitor after first navigation, so that server-created anonymous session cookie must not be confused with seeded authentication.

The stronger logged-out invariant remains:

- browser context starts with zero cookies;
- no cookies/storage state are injected;
- no editor URL is opened;
- zero clicks;
- zero forms/submissions;
- no content, settings, membership, or public mutation;
- explicit auth/token/login/user-id cookies still fail closed.

Verified live result:

- Workflow run: `34416681984`
- HTTP status: `200`
- Public page title: `【最初にお読みください】「このAI、使える！」を判断するための使い方｜AI Intelligence Factory`
- Open Graph title matches the new title
- `new_title_verified = true`
- `legacy_title_absent = true`
- `not_for_sale_absent = true`
- `members_only_gate_verified = true`
- gate markers observed: `メンバーシップ`, `メンバー限定`, `メンバー`
- public text states `ここから先は 1,424字`
- protected deep-body markers exposed to logged-out visitors: `[]`
- cookies before navigation: `[]`
- note-created anonymous session observed: `_note_session_v5`
- explicit auth-like cookies after navigation: `[]`
- `clicks_performed = 0`
- all mutation flags: `false`
- zero Gemini/model calls
- zero Notion writes

Run326 evidence artifact:

- name: `run326-onboarding-public-audit`
- artifact ID: `10129395551`
- files: result JSON + full-page logged-out screenshot

## 6. Current operator commands

### Exact maintenance

`/aiif note onboarding update`

This is a hard-bound maintenance exception for the exact onboarding note/current SHA contract. It is not a generic note publisher.

### Logged-out public audit

`/aiif note onboarding public-audit`

This command is read-only. It verifies the customer-facing public surface with zero clicks and no seeded authentication state.

## 7. Retired live route

The old Run315 DOM-range live workflow is no longer the dispatched Production update path. Its code/tests may remain as historical regression coverage, but `.github/workflows/note-member-onboarding-update.yml` uses the Run325 finalizer contract.

Do not restore the old live path merely because its historical test or adapter still exists.

## 8. Production invariant

For this onboarding article, “saved in the editor” is not equivalent to “current public article,” and “public article” is not equivalent to “correct customer entitlement.” A successful maintenance operation is complete only when all three are true:

1. the exact newest manuscript is server-saved;
2. the existing published article is finalized through the Run325 route without adding a trial-read line;
3. Run326b-style logged-out verification proves the new title and members-only gate while protected body content remains hidden.

This three-layer proof is the current paid-member note onboarding baseline.