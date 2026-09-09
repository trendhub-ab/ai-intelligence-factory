# Run323 — Member Onboarding Publish Surface Deep Probe

## Purpose

Run322 proved that the exact existing-article route can reach the publish-settings URL for note `n284e428c80f4` after selecting `最新の下書き` and confirming with `編集する`. However, the ordinary actionable-control inventory still did not expose the final `更新する` control described by note's current help.

Run323 is a **read-only / no-final-commit diagnostic** that deep-inspects the exact publish-settings surface without changing content, publish settings, membership association, or public state.

## Hard-bound source state

- Target note: `n284e428c80f4`
- Expected title: Run315 `NEW_TITLE`
- Expected body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- Exact existing-article route:
  1. article list
  2. exact target card menu
  3. `編集`
  4. `最新の下書き`
  5. `編集する`
  6. exact revision re-verification
  7. `公開に進む`
  8. exact publish-settings URL

The probe fails closed if the title, body SHA, target card, route, or publish URL drifts.

## Diagnostic coverage

At several settle times and at both the top and bottom of the page, Run323 inventories:

- broad interactive nodes: `button`, `input`, `select`, `textarea`, links, role/tabindex/onclick/contenteditable/test-id nodes;
- hidden and disabled controls;
- fixed and sticky layers;
- HTML forms and their controls;
- text and attribute matches for `更新する`, `更新`, `公開する`, `投稿する`, `保存する`, `publish`, `update`, and `save`;
- candidate control labels derived from text, `aria-label`, `title`, and `value`;
- a full-page screenshot when an output path is supplied.

## Mutation contract

Run323 must always report:

- `final_commit_clicked = false`
- `content_mutation = false`
- `settings_mutation = false`
- `membership_mutation = false`
- `public_mutation = false`
- `zero_gemini_calls = true`
- `notion_writes = 0`

It does not click `更新する`, `公開する`, `投稿する`, or any equivalent final commit control.

## Success criterion

A successful Run323 means the exact publish-settings surface was inspected deeply enough to determine whether the final update control exists as visible, hidden, disabled, form-backed, fixed/sticky, delayed, or text/attribute-only UI. It is diagnostic evidence only and must not be interpreted as publication completion.
