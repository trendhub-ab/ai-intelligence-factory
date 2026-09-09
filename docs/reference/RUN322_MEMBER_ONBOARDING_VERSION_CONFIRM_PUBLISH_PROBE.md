# Run322 — Member Onboarding Version-Confirm Publish Probe

## Goal

Use only the exact UI proven by live Run321b to reach the latest server-saved onboarding revision through note's existing-article edit route, then inspect publish settings without committing any public change.

## Hard preconditions

- target: `n284e428c80f4`
- exact server-saved title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- exact body SHA-256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- fresh cookie-only browser context
- existing Run321 hard-bound confirmation token

## Proven navigation

1. Re-prove the exact server-saved revision.
2. Open `https://note.com/notes`.
3. Locate only the exact target article card.
4. Open its exact menu and click `編集`.
5. Require the Run321b-proven dialog containing:
   - `公開されていない下書きがあります`
   - `どちらを編集しますか？`
   - `公開した時点の記事`
   - `最新の下書き`
   - `キャンセル`
   - `編集する`
6. Select exact `最新の下書き`.
7. Click exact `編集する`.
8. Require the exact target editor URL.
9. Re-verify title and body SHA before any further navigation.
10. Click `公開に進む`.
11. Require the exact target publish-settings URL.
12. Inventory visible/actionable controls at the top and bottom of publish settings, including candidate final controls such as `更新する`, `公開する`, `投稿する`, or `保存する`.
13. Stop before any final commit.

## Safety contract

- no title/body edits
- no settings edits
- no membership edits
- no final update/publish/save click
- no public mutation
- zero Gemini/model calls
- zero Notion writes

## Workflow compatibility

The existing workflow still invokes `run321b_member_onboarding_edit_route_diagnostic.py`. For least privilege and to avoid adding another privileged ChatOps route, that compatibility runner delegates to Run322 using the same exact confirmation token and preserves the existing no-mutation result contract.
