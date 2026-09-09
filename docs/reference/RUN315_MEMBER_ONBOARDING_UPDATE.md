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

## Membership publication repair

Current note help confirms that a free article becomes a member-benefit article when it is added to a membership. If a previously attached free benefit loses its plan association, other users can see a not-for-sale state.

Run315 therefore keeps `記事タイプ=無料`, selects the exact `AI Intelligence Factory` membership via the observed `追加` control, chooses an all-members scope only when an exact visible scope option is presented, then uses the normal `更新する` confirmation.

## Fail-closed safety

- exact note ID only;
- exact Run314 old body SHA or an exact staged Run315 body;
- exact membership name only;
- refuses unexpected title/body/settings;
- never changes tags, magazine, eyecatch, AI translation, AI compensation, comments, or profile;
- post-update public verification must remove the not-for-sale message and expose the new title.

## Cost

- Gemini/model: 0
- Notion writes: 0
- Production ONE-SHOT: 0
- Scheduled Daily: PAUSED
