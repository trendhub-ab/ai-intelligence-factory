# Run312 — Public Fixed LP Live Content Audit

## Purpose

ユーザーが手動更新した公開固定note `ned673e381ef8` を、現在のProduct Contractと照合するための**read-only content snapshot**を取得する。

Run310の自動上書きは行わない。人間が手動更新したnoteを先に観測し、実態と異なる表現だけを特定してから最小修正する。

## Authority

- Live note: `https://note.com/trendhub_biz/n/ned673e381ef8`
- Product positioning: `docs/reference/RUN307_GENERIC_USE_DECISION_PRODUCT.md`
- Commerce fulfillment: `docs/reference/RUN217_ZERO_API_MONETIZATION_READINESS.md` + current superseding member UI/DB contracts

## Read-only snapshot

既存Run309 exact-target auditへ以下を追加する。

- title
- complete visible body text
- SHA-256 of visible body text
- links contained inside the editor body
- existing visible control snapshot

この拡張は入力・保存・公開操作を追加しない。

## Review points

Live noteを以下と照合する。

1. Product promise is `「このAI、使える！」を、根拠付きで判断できる。`
2. 自分の開発 / 業務利用 / 必要に応じた提案を並列に扱う
3. Current source families are GitHub / ArXiv / Hacker News / OfficialVendor
4. Product Huntをcurrent sourceとして売らない
5. Paid promise must not exceed actual fulfillment
6. Current price is 月額1,980円
7. Member-only DB and Digest remain real fulfillment surfaces
8. Run307 Decision Brief / judgment DB / pre-use judgment memo framing may be used only to the extent current member surface actually supplies it
9. Free note remains complete; paid value is repeated decision-time reduction, not a hidden article continuation
10. CTA should resolve to the note membership surface

## Safety / cost

- Note mutation: **0**
- Gemini/model calls: **0**
- Production ONE-SHOT: **0**
- Notion write: **0**
- Scheduled Daily: **PAUSED維持**
