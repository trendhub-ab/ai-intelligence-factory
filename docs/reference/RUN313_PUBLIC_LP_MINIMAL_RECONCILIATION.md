# Run313 — Public Fixed LP Minimal Reconciliation

## Purpose

Run312で取得したユーザー手動編集済み固定LPを正本として尊重し、**実態と異なる2箇所だけ**を修正する。

対象: `ned673e381ef8`

## Run312 audited state

- title: `「このAI、使える！」を根拠付きで判断する｜Decision Brief + AI意思決定DB`
- body SHA-256: `3e3569378f388634c02d107d11672dd05958bbee4c4b4a6c9a2368af415f4b5c`
- membership CTA: `月額1,980円の内容を見る` → `https://note.com/trendhub_biz/membership`

## Exact corrections

### 1. Malformed duplicated legacy prefix

本文先頭に旧導入文が残り、最後が

`AIやITの大量の情報から、「これは知っておいた`

で途切れている。

この旧prefixだけを削除し、本文を

`「このAI、使える！」を、根拠付きで判断できる。`

から開始する。

### 2. Device-support wording

Live copy:

`PC・スマートフォン対応`

Current paid-member UX contract (Run218):

- PC is the primary member experience.
- Mobile/simple views are secondary fallback surfaces.
- `スマホで見る` is available, but mobile must not be presented as the preferred/equivalent primary environment.

Therefore replace only with:

`PCでの利用を推奨（スマートフォン向け簡易ビューあり）`

## Preserve unchanged

- user-edited structure and wording outside the two targets
- title
- Decision Brief / AI意思決定DB / judgment memo claims
- current source families: GitHub / Hacker News / ArXiv / OfficialVendor
- price: 月額1,980円
- membership CTA and link
- tags, eyecatch, magazine, membership settings

## Fail-closed

Run313 mutates only if the body SHA-256 exactly equals the Run312 audited snapshot. If the user edits the page again before execution, it refuses to overwrite the new state.

The already-corrected state is idempotently verified and does not mutate.

## Cost / safety

- Gemini/model: 0
- Production ONE-SHOT: 0
- Notion write: 0
- Scheduled Daily: PAUSED
- exact fixed note only
