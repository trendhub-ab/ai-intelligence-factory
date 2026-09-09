# Run320 — Exact Member Onboarding Membership-Dialog Probe

## Purpose

Run317 proved that the rewritten onboarding article `n284e428c80f4` is stored on note's server. Run318 proved that this article's current publish-settings page exposes no final update/publish CTA. Run319 then proved that the existing published article's `自分の記事` card exposes the exact menu action `メンバーシップ特典追加・解除`.

Run320 opens only that exact menu action and inventories the resulting membership-selection surface without selecting a membership or confirming any change.

## Exact source contract

Run320 accepts only the server-saved Run317 revision:

- note ID: `n284e428c80f4`
- title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- full Run315 marker/link verification PASS

The source is re-proved in a fresh cookie-only browser before the article list is opened.

## Probe sequence

1. obtain current authenticated `note.com` cookies from the persistent Chrome profile;
2. close the persistent profile;
3. launch a clean non-persistent Chrome context with cookies only;
4. verify the exact Run317 server-saved revision;
5. open `https://note.com/notes`;
6. identify the exact target article card by `/trendhub_biz/n/n284e428c80f4`;
7. open only that card's exact menu;
8. require exactly one visible `menuitem` named `メンバーシップ特典追加・解除`;
9. click that menu item only to open the membership-selection surface;
10. inventory dialogs, controls, membership-name mentions, checked state, and possible final confirmation controls;
11. close the browser without choosing any membership or confirmation action.

## Trigger

Manual token:

`PROBE_MEMBER_ONBOARDING_MEMBERSHIP_DIALOG_N284E428C80F4_SHAAAB9E57B`

Direct exact control-issue command:

`/aiif note onboarding membership-probe`

The issue path is fail-closed to issue `#71`, owner `trendhub-ab`, exact command text, non-PR issue, and first attempt only.

## Safety contract

Run320 does **not**:

- change the title or body;
- click a membership selection;
- click `追加`, `保存`, `決定`, `更新`, or equivalent confirmation;
- attach or detach a membership;
- change article type, magazine, tags, comments, translation, or profile;
- publish or unpublish the article;
- write to Notion;
- call Gemini or any other model.

## Success contract

A successful Run320 returns:

- `status=probe_complete_no_membership_mutation`
- exact source title/body SHA
- `fresh_cookie_only_context=true`
- `local_storage_seeded=false`
- exact target card/menu evidence
- `membership_menu_action=メンバーシップ特典追加・解除`
- dialog/control inventory
- membership-name mentions
- possible final-confirm controls
- `membership_selection_clicked=false`
- `final_confirm_clicked=false`
- `membership_mutation=false`
- `public_mutation=false`
- `zero_gemini_calls=true`
- `notion_writes=0`

Only after this live probe identifies an exact, unique membership selection and exact final confirmation path may a mutation Run be created.
