# Run316 — Member Onboarding Final-CTA Probe

## Purpose

Run315 now has a verified staged onboarding rewrite but cannot safely commit the membership repair because the current note publish-settings UI no longer exposes the inherited exact `更新する` button.

Run316 identifies the current final commit control without guessing and without clicking any final save/update/publish action.

## Exact target

- note ID: `n284e428c80f4`
- membership: `AI Intelligence Factory`
- article type: `無料`

Authorized source states are limited to:

1. Run314 legacy audited state:
   - title: `【最初にお読みください】AI Decision Intelligenceの利用方法`
   - body SHA-256: `4826aabc101f5f5319e2ea441e0e929ce2e7ee382be10a5fd0a976583c49c9f4`
2. Run315 staged state observed by read-only audit after the final-CTA failure:
   - title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
   - body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
   - full Run315 editor marker/link verification must also pass.

## Probe behavior

Run316:

1. opens only the exact onboarding editor;
2. reads title/body and refuses any unrecognized state;
3. does not rewrite title or body;
4. enters the exact publish-settings URL;
5. requires the expected free article and membership surface;
6. records actionable controls before membership selection;
7. uses the existing Run315 exact membership helper to leave the visible `追加` state inside the unsaved publish-settings session;
8. scrolls to the page bottom and inventories up to 300 actionable elements after membership selection, including:
   - tag / role / type;
   - text;
   - aria-label / title;
   - disabled / aria-disabled;
   - CSS visibility;
   - viewport presence;
   - nearby context;
9. records the publish-settings body text;
10. closes the browser context without clicking a final commit control.

## Non-goals

Run316 does not:

- click `更新する`, `公開する`, `投稿する`, `保存する`, or any inferred replacement CTA;
- rewrite the onboarding content;
- publish or update the note;
- persist a membership change intentionally;
- call Gemini or any model;
- write to Notion;
- run Production ONE-SHOT.

After Run316 completes, a read-only Run314 audit should be used if necessary to prove that membership still shows `追加` before any Run315 finalization retry.
