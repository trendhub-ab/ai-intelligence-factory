# Run321 — Member Onboarding Official Edit-Route Probe

## Purpose

Run317 proved that the rewritten onboarding article `n284e428c80f4` is saved on note's server. Run318 then opened that editor URL directly and found no final `更新する`/publish CTA in publish settings.

Current note help documents the existing published-article edit sequence as:

`自分の記事 -> 対象記事の … -> 編集 -> 公開に進む -> 更新する`

Run321 reproduces that exact navigation route before concluding that the final CTA is unavailable.

## Exact source contract

- note ID: `n284e428c80f4`
- title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- full Run315 marker/link verification PASS
- fresh cookie-only Chrome context
- no localStorage/IndexedDB transfer from the persistent Chrome profile

## Probe sequence

1. obtain current note.com authentication cookies only;
2. launch a fresh non-persistent browser;
3. independently prove the exact server-saved Run317 revision;
4. open `https://note.com/notes`;
5. locate the exact article card by `/trendhub_biz/n/n284e428c80f4`;
6. open that card's unique menu;
7. click the exact `編集` menu item;
8. inventory the route immediately after the click;
9. if note presents an exact `最新の下書き` version-choice option, choose only that navigation option;
10. require that the editor now exposes the exact new title/body SHA and all authorized markers/links;
11. inventory editor controls;
12. click exact `公開に進む` only;
13. inventory all visible and hidden actionable DOM controls in publish settings before and after bottom scroll;
14. identify any exact `更新する`/publish/save commit candidate;
15. close the browser without clicking a final commit control.

## Safety contract

Run321 does not:

- edit title/body;
- change article settings;
- change membership association;
- click `更新する`, `公開する`, `投稿する`, `保存する`, or equivalent final action;
- publish or unpublish the article;
- write to Notion;
- call Gemini or any other model.

Choosing `最新の下書き`, if present, is treated only as navigation to the already server-saved revision and is accepted only when exactly one visible exact-label option exists.

## Trigger

Confirmation token:

`PROBE_MEMBER_ONBOARDING_OFFICIAL_EDIT_ROUTE_N284E428C80F4_SHAAAB9E57B`

Control issue command:

`/aiif note onboarding edit-route-probe`

The command is routed through the existing fail-closed ChatOps bridge on issue `#71`.

## Success contract

- `status=probe_complete_no_public_mutation`
- exact server-saved source title/body SHA
- exact article-list target card/menu
- `edit_menu_clicked=true`
- exact routed new title/body SHA
- editor and publish-settings inventories
- candidate final commit controls recorded
- `final_commit_clicked=false`
- `content_mutation=false`
- `settings_mutation=false`
- `membership_mutation=false`
- `public_mutation=false`
- `zero_gemini_calls=true`
- `notion_writes=0`
