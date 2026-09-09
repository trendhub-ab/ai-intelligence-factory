# Run317 — Member Onboarding Server-Save Proof

## Purpose

Run315 rewrote the exact onboarding article `n284e428c80f4`, but later user verification showed that the normal browser still returned the legacy article. The prior audits reused the same persistent Chrome profile, so they could observe local editor state and could not prove that note's server had accepted the rewrite.

Run317 fixes that evidence gap before any publication or membership repair continues.

## Exact target

- note ID: `n284e428c80f4`
- authorized legacy title: `【最初にお読みください】AI Decision Intelligenceの利用方法`
- authorized legacy body SHA-256: `4826aabc101f5f5319e2ea441e0e929ce2e7ee382be10a5fd0a976583c49c9f4`
- authorized new title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- authorized new body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`

## Server-proof sequence

1. Start the persistent Chrome profile only to obtain current authenticated `note.com` cookies.
2. Close the persistent profile. Its article DOM, localStorage, IndexedDB, cache, and unsaved editor state are never trusted as source evidence.
3. Launch a clean non-persistent Chrome browser/context.
4. Add only the authenticated `note.com` cookies; do not import storage state or localStorage.
5. Open the exact editor URL and require either the exact Run314 legacy state or the exact Run315 new state.
6. If the server returns the legacy state, replace the body with the proven Run315 DOM-Range delete-before-paste method and set the exact new title.
7. Verify the full new manuscript, forbidden-old-marker removal, exact links, and exact new body SHA before saving.
8. Click exactly one visible enabled `一時保存` button.
9. Wait for the save attempt, capture refreshed authentication cookies only, then close that browser/context completely.
10. Launch a second fresh browser/context with those cookies only.
11. Reopen the same exact editor URL and require the exact new title, exact new body SHA, required markers, and exact links.
12. Only this second clean-context result counts as server persistence proof.

## Safety contract

Run317 does **not**:

- enter publish settings;
- click `公開に進む`;
- attach or detach membership;
- change article type, tags, magazine, eyecatch, AI translation, comments, profile, or other settings;
- publish or update the public article;
- write to Notion;
- call Gemini or any other model.

If the clean source state is neither the exact Run314 legacy state nor the exact authorized Run315 state, Run317 fails closed before mutation.

## Success contract

The workflow must return:

- `status=server_saved_and_verified`
- `fresh_context_verified=true`
- `fresh_title` equal to the authorized new title
- `fresh_body_sha256=aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- `fresh_context_local_storage_seeded=false`
- `public_release=false`
- `membership_mutation=false`
- `zero_gemini_calls=true`
- `notion_writes=0`

Only after this passes may the publication/membership repair be resumed.
