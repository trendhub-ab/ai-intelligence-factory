# Run321b — Member Onboarding Edit-Route Diagnostic

## Purpose

Run321 reproduced note's documented existing-article route (`自分の記事 -> … -> 編集`) for the exact onboarding article `n284e428c80f4`, but the live browser remained on `https://note.com/notes` after the exact `編集` menu item was clicked. Run321b narrows the next step to observation only: capture the intermediate UI and any exact version-choice labels without guessing a follow-up control.

## Fixed source state

Run321b refuses to run unless a fresh cookie-only browser independently proves the server-saved Run315 revision:

- target note: `n284e428c80f4`
- title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`

## Diagnostic route

1. Prove the exact server-saved title/body in a fresh cookie-only context.
2. Open `https://note.com/notes`.
3. Locate the exact target article card.
4. Open only that card's exact menu.
5. Click the exact `編集` menu item.
6. Capture URL, body text, visible dialogs, visible controls, and actionable DOM controls.
7. Record exact visible counts for likely version-choice labels.
8. If and only if Run321's exact `最新の下書き` helper observes its already-authorized version prompt, select that navigation option and capture the resulting state.
9. Stop. Do not enter publish settings and do not publish.

## Safety contract

- no title/body mutation
- no settings mutation
- no membership mutation
- no public mutation
- no final save/update/publish click
- zero Gemini/model calls
- zero Notion writes
- same hard-bound Run321 confirmation token and existing ChatOps command are reused; no broader authorization is added

## Workflow integration

The existing workflow `.github/workflows/note-member-onboarding-official-edit-route-probe.yml` is temporarily narrowed to run the Run321b diagnostic after Run321's live route mismatch. The existing control command remains:

`/aiif note onboarding edit-route-probe`

This avoids adding another privileged workflow/ChatOps command while the exact note UI behavior is still being falsified.
