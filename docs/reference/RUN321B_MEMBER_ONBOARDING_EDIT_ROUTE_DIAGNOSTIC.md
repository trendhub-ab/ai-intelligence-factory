# Run321b — Member Onboarding Edit-Route Diagnostic

## Purpose

Run321 reproduced note's documented existing-article route (`自分の記事 -> … -> 編集`) for the exact onboarding article `n284e428c80f4`, but the live browser remained on `https://note.com/notes` after the exact `編集` menu item was clicked. Run321b captured the intermediate UI without public mutation.

## Fixed source state

The live diagnostic independently re-proved the server-saved Run315 revision in a fresh cookie-only browser:

- target note: `n284e428c80f4`
- title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`

## Live result — workflow run 34361159552

The exact `編集` menu item does not navigate immediately. note opens one dialog on `https://note.com/notes`:

`公開されていない下書きがあります`  
`どちらを編集しますか？`

The dialog exposes both revisions and one confirmation button:

- `公開した時点の記事` — 2026年9月1日 21:04, 1526文字
- `最新の下書き` — 2026年9月9日 21:16, 1424文字
- `キャンセル`
- `編集する`

Exact visible counts were one each for `最新の下書き`, `公開した時点の記事`, `編集する`, and `キャンセル`.

Run321b selected `最新の下書き` only. The dialog remained open and the URL remained `https://note.com/notes`. This falsified the previous assumption that selecting `最新の下書き` itself performs navigation. The required route is two-stage:

1. select `最新の下書き`;
2. click `編集する`.

No title/body/settings/membership/public mutation occurred. No final save/update/publish control was clicked. Zero model calls and zero Notion writes.

## Successor

Run322 follows only the newly proven second step: exact `最新の下書き` selection followed by exact `編集する`, then verifies the resulting editor revision and enters `公開に進む` only to inventory the final publish-settings controls. It still stops before any final commit.

The existing hard-bound workflow and ChatOps command remain in use:

`/aiif note onboarding edit-route-probe`
