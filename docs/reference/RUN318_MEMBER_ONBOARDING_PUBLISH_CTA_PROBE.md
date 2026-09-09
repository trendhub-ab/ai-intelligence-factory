# Run318 — Clean Member-Onboarding Publish-CTA Probe

## Purpose

Run317 proved that the rewritten onboarding article `n284e428c80f4` is persisted on note's server. The public page is still the legacy revision because Run317 intentionally did not publish.

note's current official browser help describes the published-article update path as `公開に進む` followed by `更新する`. A prior Run316 live probe did not observe an exact visible `更新する` control, but that probe ran before server persistence was correctly established and also reused the persistent Chrome profile.

Run318 therefore re-observes the publish-settings UI from the exact Run317 server-saved state in a clean cookie-only browser before any public mutation.

## Exact source contract

Run318 accepts only:

- note ID: `n284e428c80f4`
- title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- full Run315 marker/link verification PASS

Any other state fails closed before entering publish settings.

## Probe sequence

1. Start the persistent Chrome profile only long enough to collect current authenticated `note.com` cookies.
2. Close the persistent profile completely.
3. Launch a clean non-persistent browser/context and add cookies only.
4. Open the exact editor URL and verify the exact Run317 server-saved revision.
5. Click the exact `公開に進む` control to enter the exact publish-settings URL.
6. Require the expected free-article surface and exact membership name.
7. Inventory all actionable DOM controls, including text, aria-label, title, visibility, disabled state, viewport state, IDs, hrefs, and nearby context.
8. Record candidate final controls for current official/known labels such as `更新する`, `更新`, `公開する`, `投稿する`, and `保存する`.
9. Scroll to the bottom and repeat the inventory.
10. Record raw text occurrence counts for final-CTA markers.
11. Close the clean browser without changing membership or clicking any final commit control.

## Safety contract

Run318 performs no content rewrite and no settings mutation. It does not:

- click membership `追加`;
- change article type, tags, magazine, detail settings, translation, comments, or any other setting;
- click `更新する`, `公開する`, `投稿する`, `保存する`, or equivalent final commit action;
- mutate the public article;
- write to Notion;
- call Gemini or another model.

## Success contract

A successful probe returns:

- `status=probe_complete_no_mutation`
- exact source title/body SHA
- `fresh_cookie_only_context=true`
- `local_storage_seeded=false`
- actionable-control inventory before and after bottom scroll
- candidate commit-control inventory
- raw commit-marker counts
- `final_commit_clicked=false`
- `membership_mutation=false`
- `public_mutation=false`
- `zero_gemini_calls=true`
- `notion_writes=0`

A later publication Run may use only an exact, uniquely observed Run318 control; it must not guess a final CTA.

## Live result — 2026-09-09

Workflow run `34349885711`, attempt 2, completed successfully after the first VM-start attempt hit a transient GCP fingerprint race. The retry reached note and made no mutation.

The clean cookie-only browser proved the exact Run317 server-saved source again:

- title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- publish URL: `https://editor.note.com/notes/n284e428c80f4/publish/`
- localStorage seeded: `false`

The current publish-settings DOM exposed the normal settings controls and `AI Intelligence Factory` with `追加`, but **no final commit control at all**. Before and after scrolling to the bottom:

- candidate `更新する` / `更新` controls: `0`
- candidate `公開する` controls: `0`
- candidate `投稿する` / `投稿` controls: `0`
- candidate `保存する` controls: `0`
- raw text occurrences of each of those markers: `0`

Result contract:

- `status=probe_complete_no_mutation`
- `final_commit_clicked=false`
- `membership_mutation=false`
- `public_mutation=false`
- `zero_gemini_calls=true`
- `notion_writes=0`

This falsifies the assumption that the ordinary browser-help `公開に進む` → `更新する` path is currently available for this particular sales-stopped, membership-detached article state. Run319 therefore probes note's separately documented existing-article route: `自分の記事` → exact target article menu → `メンバーシップ特典に追加`, without selecting the action.