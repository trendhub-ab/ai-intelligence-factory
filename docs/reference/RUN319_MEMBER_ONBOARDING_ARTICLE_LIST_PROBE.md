# Run319 — Exact Article-List Membership Route Probe

## Purpose

Run317 proved the rewritten onboarding article `n284e428c80f4` is persisted on note's server. Run318 then proved that the current publish-settings page for this special sales-stopped, membership-detached article exposes no `更新する`, `公開する`, `投稿する`, or `保存する` final control.

note's current help separately documents an existing-article membership route from the article list: open `自分の記事`, use the target article's `…` menu, then choose `メンバーシップ特典に追加` / equivalent current membership-add action.

Run319 observes that exact route without selecting any menu action.

## Exact source contract

Run319 accepts only the Run317 server-saved onboarding revision:

- note ID: `n284e428c80f4`
- title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- full Run315 marker/link verification PASS

Before opening the article list, Run319 reopens the exact editor in a clean cookie-only context and proves that source contract.

## Probe route

- article list URL: `https://note.com/notes`
- exact target public path: `/trendhub_biz/n/n284e428c80f4`

Run319:

1. uses the persistent Chrome profile only to collect current authenticated `note.com` cookies;
2. closes the persistent profile;
3. launches a clean non-persistent browser and cookie-only context;
4. proves the exact Run317 server-saved revision in the editor;
5. opens `https://note.com/notes`;
6. locates a visible anchor containing the exact target public path;
7. climbs only within that target article's DOM card and inventories its controls;
8. identifies a menu control only when it is uniquely evidenced by menu semantics/glyphs, with a narrow one-empty-SVG-button fallback;
9. may click that exact target card's menu button to expose its menu;
10. inventories the resulting actionable DOM and searches for current membership-add labels such as `メンバーシップ特典に追加`;
11. never selects the membership-add action or any other menu action;
12. closes the browser with no persistent mutation.

## Trigger and authorization

The workflow supports manual `workflow_dispatch` with the exact confirmation token:

`PROBE_MEMBER_ONBOARDING_ARTICLE_LIST_N284E428C80F4_SHAAAB9E57B`

It also accepts exactly one direct control-issue command:

`/aiif note onboarding list-probe`

The direct issue path is fail-closed to:

- issue `#71` only;
- a non-PR issue;
- owner user `trendhub-ab` as both comment author and actor;
- exact command text only;
- first workflow attempt only.

This direct trigger avoids modifying the existing central ChatOps bridge and does not require `actions: write` or a GitHub API dispatch token.

## Safety contract

Run319 does **not**:

- rewrite the article;
- enter or change publish settings;
- click `メンバーシップ特典に追加` or any equivalent menu action;
- attach or detach membership;
- change article type, tags, magazine, settings, translation, comments, or profile;
- publish/update the public article;
- write to Notion;
- call Gemini or another model.

Opening an exact target-card menu is treated as transient UI inspection only.

## Success contract

A successful probe returns:

- `status=probe_complete_no_mutation`
- exact source title/body SHA
- `fresh_cookie_only_context=true`
- `local_storage_seeded=false`
- target article card discovery result
- exact-menu discovery/open result
- actionable controls before/after menu open
- membership-menu match inventory
- `menu_action_clicked=false`
- `membership_mutation=false`
- `public_mutation=false`
- `zero_gemini_calls=true`
- `notion_writes=0`

If the target card or menu cannot be uniquely identified, Run319 reports the observed controls and stops without mutation. A later mutation Run may use only a uniquely observed existing-article membership route.