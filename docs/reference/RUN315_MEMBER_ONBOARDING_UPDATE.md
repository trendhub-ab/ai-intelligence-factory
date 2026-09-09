# Run315 — Member Onboarding Rewrite + Membership Re-association

## Target

- note ID: `n284e428c80f4`
- Run314 audited title: `【最初にお読みください】AI Decision Intelligenceの利用方法`
- Run314 audited body SHA-256: `4826aabc101f5f5319e2ea441e0e929ce2e7ee382be10a5fd0a976583c49c9f4`
- current membership: `AI Intelligence Factory`

## Live problem found by Run314

The article is a free article, but the publish-settings surface shows the membership `AI Intelligence Factory` with an exact `追加` action. The article is therefore no longer attached as a current membership benefit. This matches the external `この記事は現在販売されていません` state.

The old body also describes the previous product surface:

- `会員向けDigest`
- English internal properties such as `Short Rationale`, `Main Risk`, `Best For / Avoid For`
- work/client-centric framing

These no longer match Run307 current product/member UX.

## Current onboarding contract

Title:

`【最初にお読みください】「このAI、使える！」を判断するための使い方`

The page must:

1. keep the existing Notion registration route;
2. explain the product as a use-decision service rather than an AI-news archive;
3. present only three member surfaces first: Decision Brief, AI意思決定DB, 判断メモ;
4. teach ADOPT / TEST / WATCH / AVOID with Run307 generic meanings;
5. support self-development, internal/business use, tool selection, and optional proposals without making clients the primary subject;
6. recommend PC and identify mobile as a simple view;
7. state that Notion access ends when note membership eligibility ends, rather than implying immediate loss at the moment a cancellation action is submitted;
8. link to the live registration form and current Notion destinations.

## Existing-body replacement contract

The generic note paste helper uses keyboard `Control+A`, which is suitable for new or empty drafts but is not trusted for this populated legacy article because the editor can keep selection inside only the active block.

Run315 therefore uses a dedicated process-local adapter before executing the existing updater:

1. locate the exact body contenteditable with the existing Run315/base selectors;
2. create a DOM `Range` and call `selectNodeContents(body)`;
3. fail closed unless the resulting selection starts at offset `0` on the body element and ends at `body.childNodes.length` on that same element;
4. only after those exact range boundaries are proven, issue a real keyboard `Backspace` to delete the selected legacy blocks;
5. normalize zero-width/BOM characters and fail closed unless the body is visibly empty after deletion;
6. dispatch the same safe `text/html` + `text/plain` paste payload already used by the shared note helper;
7. leave the shared generic paste helper unchanged for every other note automation;
8. immediately run the existing full-body content verification, required-marker verification, forbidden-old-marker verification, and exact-link verification before entering publish settings.

A synthetic paste event by itself is not treated as deletion. Run315 must prove the legacy body is empty before inserting the new manuscript. If selection, deletion, or post-delete emptiness verification fails, Run315 stops before membership or publish mutation.

## Membership publication repair

Run315 keeps `記事タイプ=無料` and selects the exact `AI Intelligence Factory` membership via the observed `追加` control. An all-members scope is chosen only when an exact visible scope option is presented.

The final publish-settings commit control is NOT assumed by name. The previously inherited `更新する` assumption was falsified against the current live UI on 2026-09-09: after membership selection, no visible button with exact text `更新する` existed. Run316 is therefore used to inventory the exact post-membership actionable DOM without clicking a final commit. Run315 may only be updated to click a final control after Run316 observes an exact, uniquely identifiable current control.

## Fail-closed safety

- exact note ID only;
- exact Run314 old body SHA or an exact staged Run315 body;
- exact body DOM Range boundaries before replacement;
- exact body-empty proof after the authorized deletion;
- exact membership name only;
- refuses unexpected title/body/settings;
- never changes tags, magazine, eyecatch, AI translation, AI compensation, comments, or profile;
- post-update public verification must remove the not-for-sale message and expose the new title.

## Live verification after first DOM-Range attempt

The first Run315 DOM-Range attempt proved that the editor selection covered the exact body but also proved that a synthetic paste event alone did not delete the selected legacy blocks; the forbidden marker `会員向けDigest` remained and Run315 stopped before entering membership mutation.

A subsequent read-only Run314 audit confirmed that note restored the exact audited source state before the next attempt:

- title: `【最初にお読みください】AI Decision Intelligenceの利用方法`
- body SHA-256: `4826aabc101f5f5319e2ea441e0e929ce2e7ee382be10a5fd0a976583c49c9f4`
- membership surface: `AI Intelligence Factory` still showed `追加`

No partially rewritten body or membership change remained.

## Live verification after delete-before-paste attempt

The second Run315 live attempt proved that exact Range deletion plus empty-body verification fixed the populated-editor replacement problem. The new title/body passed all Run315 editor checks and execution advanced through membership selection. It then stopped because the inherited final exact `更新する` selector did not exist in the current publish-settings UI.

A subsequent read-only audit on 2026-09-09 established the persisted state:

- title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- visible body characters: `1524`
- staged body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- all four authorized links remained present
- membership surface still showed `AI Intelligence Factory` + `追加`
- article type remained `無料`

Therefore the content rewrite is safely staged/autosaved, while the membership repair is still uncommitted. Future Run315 execution must accept this exact staged body via its existing `NEW_TITLE` verification path and must not rewrite the body again.

## Cost

- Gemini/model: 0
- Notion writes: 0
- Production ONE-SHOT: 0
- Scheduled Daily: PAUSED
