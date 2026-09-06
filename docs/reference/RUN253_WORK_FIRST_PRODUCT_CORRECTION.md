# Run253 — Work-First Product Correction

Date: 2026-09-06

## Why

Run250–252 successfully converted the paid Notion surface from a broad technical database into a client-action product. Production inspection then exposed a product-strategy error: **「AIの相談をされたとき、答えに困らない」 was a secondary outcome, not the primary user job.**

The primary user motivation is earlier and broader:

> **AIを全部追わなくても、自分の仕事に使えるものがわかる。**

The paid product must help the user:

1. know what changed / what matters,
2. understand what a technology can do,
3. judge whether it is useful in their own work,
4. decide use / test / watch / avoid,
5. optionally reuse that judgment in client proposals.

Client proposal support remains valuable but is explicitly secondary.

## Initial ICP

**Web制作・マーケティング・業務改善・クリエイティブなどでAIを仕事に活用する1〜3名規模の事業者で、自分でツールを選び、試し、導入判断をする人。**

The product does not require that the user already receives AI questions from clients.

## Paid surface

Run253 changes presentation semantics only:

- `案件で使える場面` → `仕事で使える場面`
- `案件への意味（Business Impact）` → `仕事への意味（Business Impact）`
- `提案前に確認すること` → `使う前に確認すること`
- `提案時の次の一手` → `試すときの次の一手`
- Decision Update asks whether the user's **work-use judgment** should change.

Source facts, score, decision, Evidence, Deep Tech inventory, Notion schema and lifecycle authority are unchanged.

## Navigation policy

Work relevance, not client-language frequency, is the current navigation purpose.

- Direct work-use signals such as automation, workflow, browser work, search, content production, design, coding and productivity receive the main relevance weight.
- `顧客` / `クライアント` remain minor positive signals only.
- Deep infrastructure remains in the Intelligence Engine but is not automatically promoted to the paid homepage.
- ICP relevance is navigation-only and never replaces canonical Decision Score.

## Action layer

The member Action Asset becomes **AI活用判断シート｜使う・試す・待つ・避ける**.

Its first use is to evaluate a tool for the user's own work. Client proposal reuse is optional.

Run253 does **not** pivot the business into a prompt/template marketplace.

## Migration / regression contract

A pre-Run253 body containing the old Client Action headings must not be accepted as current merely because source values match.

Current body acceptance requires:

- `いま、どうする？`
- `仕事への意味（Business Impact）`
- `仕事で使える場面` when a use case exists
- `使う前に確認すること` when risk/avoid data exists
- `試すときの次の一手` when an action exists

Run252's script-entrypoint authority remains mandatory: the current builder must bind to the actual `__main__` wrapper used by production.

## Safety / cost

- ZERO new model/provider calls
- ZERO public note release
- No Notion schema change
- No source-score mutation
- No Evidence weakening
- No Deep Tech deletion
- Daily remains PAUSED

## Production acceptance

CI green is necessary but not sufficient.

After merge, Member Presentation Sync must complete and direct Notion inspection must show the Work-First headings on actual records. The member home and Decision Brief must place **自分の仕事で知る・判断する** before client proposal use.
