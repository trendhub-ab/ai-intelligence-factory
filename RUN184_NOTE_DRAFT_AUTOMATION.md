# Run184 — note Draft Automation

## Goal

Move one already-approved Ready article from AI Intelligence Factory into a private note draft with its finished 1280×670 eyecatch, then stop for human review.

## Production flow

1. A manual GitHub Actions dispatch requires the literal confirmation `CREATE_NOTE_DRAFT`.
2. The workflow reads only `品質状態=Ready` and `投稿状態=投稿待ち` from the existing note Ready DB.
3. The source Content Intelligence page is resolved by `同期ID`.
4. The persisted `AIIF_MANUSCRIPT:READY` Markdown code blocks are joined without regeneration.
5. The existing `アイキャッチ` file URL is downloaded. No image is regenerated.
6. Playwright opens the normal note web editor using a user-owned saved browser session.
7. The eyecatch, title and article body are inserted.
8. The draft edit URL is obtained, the draft is reopened, and title/body persistence is verified.
9. Only after verification is the note Ready row changed to `投稿準備中`.
10. If Telegram credentials are present, the private draft URL is sent to the operator's Telegram for smartphone review.

The workflow has no public-release action. Final release remains a human action in note.

## Authentication

The only supported browser credential is the GitHub Actions secret `NOTE_STORAGE_STATE_B64`. It is a base64-encoded Playwright storage-state JSON produced by `tools/capture_note_session.py` after the account owner signs in manually.

The storage state is an authentication credential:

- never commit it;
- never paste it into an issue, PR or chat;
- do not store it as a repository variable;
- store it only as the encrypted Actions secret `NOTE_STORAGE_STATE_B64`;
- delete the local `.b64` file after the secret has been registered;
- refresh the secret when note expires the session.

`.gitignore` blocks the local capture filenames as an additional guard.

## Browser policy

Run184 uses ordinary Playwright/Chromium and note's normal web editor (`https://note.com/new`). It does not call an undocumented/private note posting endpoint and does not use stealth or bot-evasion tooling.

The UI layer is intentionally fail-closed. If the login session is invalid, selectors have changed, the rich-text body did not persist, the title did not persist, the eyecatch is missing, or a stable draft edit URL is not obtained, the run fails and the queue row remains `投稿待ち`.

## API / cost contract

Run184 makes zero Gemini/model requests. It reads Notion, downloads the already-generated eyecatch, and drives the note web editor. The article and eyecatch are never regenerated as part of draft creation.

## Manual selection

The workflow accepts an optional Content Intelligence `sync_id`. If omitted, it deterministically chooses the next eligible Ready article: due scheduled rows first, then unscheduled rows. Future scheduled rows are not selected automatically.

## Privacy

The workflow does not upload browser screenshots or the unpublished manuscript as a GitHub Actions artifact. It also suppresses the private note draft URL from standard Actions logs. If Telegram is configured, the draft link is delivered there; otherwise the operator can open note's draft list on the phone.
