# Run254 — Neutral-Subject Product Copy

Date: 2026-09-06

## Why

Run253 correctly moved the paid product from Client-First to Work-First, but production review exposed a second overcorrection: repeating `自分の` made the product sound more narrowly personal than necessary.

Japanese does not need an explicit possessive subject when the context is already clear.

Current centre message:

> **AIを全部追わなくても、仕事に使えるものがわかる。**

not:

> AIを全部追わなくても、自分の仕事に使えるものがわかる。

## Language policy

Prefer the shortest natural subject-neutral form:

- `自分の仕事に使える` → `仕事に使える`
- `自分の仕事で知っておく` → `仕事で知っておく`
- `自分の利用条件` → `利用条件`
- `自分の作業時間` → `作業時間`
- `自分の環境` → `利用環境`

This is not a ban on `自分`. Keep it where the contrast itself carries information, for example `自分だけ / 少人数 / チーム`.

## Product meaning

Run254 does not change the ICP or return to a broad generic audience. It only removes unnecessary first-person possessives from the member-facing Japanese surface.

The product remains Work-First:

1. know what matters,
2. understand what a technology can do,
3. judge whether it is useful at work,
4. use / test / watch / avoid,
5. optionally reuse that judgment in client work.

Client proposal support remains secondary.

## Runtime changes

`member_client_action_alignment.py` adds a deterministic display-only neutral-subject transformer. It does not modify canonical Notion source properties.

`run250_member_client_action_product.py` applies that transformer to generated member-body summary/topic/use-case/impact/check/action/update copy.

A Run253 body can have the correct Work-First headings but still contain redundant first-person wording. Run254 therefore adds a migration guard: such generated bodies are rebuilt once instead of being accepted as current.

## Preserved contracts

- Source score unchanged
- Decision unchanged
- Evidence unchanged
- Deep Tech inventory unchanged
- Notion schema unchanged
- Navigation-only relevance unchanged
- Run252 `__main__` production binding unchanged
- ZERO Gemini/model/provider calls
- Daily remains PAUSED
- Public note release remains human-only

## Notion surface

The member home, Decision Brief and AI活用判断シート are updated to the same neutral-subject rule.

`自分だけ` is intentionally retained in the judgment sheet where it distinguishes a real user-count condition from `少人数` and `顧客・一般公開`.

## Production acceptance

CI green is necessary but not sufficient.

After merge:

1. Member Presentation Sync must succeed on main.
2. A direct Notion record inspection must show Work-First headings.
3. Generated body copy must not reintroduce unnecessary `自分の仕事` / `自分の利用条件` / `自分の環境` phrasing.
4. Source score / Decision / Evidence must remain unchanged.
