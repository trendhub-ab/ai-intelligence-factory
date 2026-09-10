# Run339b — note Public Purchase Funnel Baseline

Status: **Production verified / current**  
Date: **2026-09-10**  
Scope: fresh logged-out customer path from public membership entry to hydrated purchase surface  
Production mutation: **0 clicks / 0 fills / 0 saves / 0 note mutations**  
Provider cost: **0 Gemini/model calls / 0 Notion writes**

## 1. Current public purchase surface

Entry URL:

`https://note.com/trendhub_biz/membership`

Observed hydrated customer route:

`https://note.com/trendhub_biz/membership/join`

Run339b verified:

- HTTP status: **200**
- page title: `AI Intelligence Factory｜AI Intelligence Factory`
- membership: `AI Decision Intelligence`
- price: `¥1,980 / 月`
- current plan description: **114 characters**
- current durable onboarding guidance: `参加後は、メンバー限定の「最初にお読みください」記事をご確認ください。`
- paid benefits present:
  - `AI Decision Intelligence｜会員向け意思決定DB`
  - `AI Decision Intelligence｜会員向けDigest`
- exact onboarding article link present:
  - `【最初にお読みください】「このAI、使える！」を判断するための使い方`
  - `https://note.com/trendhub_biz/n/n284e428c80f4`
- current creator profile visible
- retired Product Hunt profile copy absent
- legacy onboarding article-name reference absent
- visible `参加手続きへ` candidates: **2**
- `ログイン` and `会員登録` both visible, positively proving the observed browser is logged out
- unavailable/challenge markers: none

## 2. Hydration / route behavior

note's public membership entry is client-rendered. The initial DOM can be a rendering shell and can still report the entry route before the complete customer surface appears.

Historical observations that established the current contract:

- **Run337** read the surface too early and failed because `AI Decision Intelligence` was not yet visible. No customer mutation occurred.
- **Run338** captured multiple checkpoints and classified the fully hydrated page as `public_purchase_surface_current`. It proved the plan, price, current description, benefits, profile, onboarding article and join CTA were present after hydration. Diagnostic artifact: `10136367043`.
- **Run339** added a hydration wait but checked the final `/join` route before that wait and failed on the still-initial `/membership` route. No customer mutation occurred.
- **Run339b** fixes only the ordering: verify HTTP 200 → wait for the hydrated customer markers → then require exact `/membership/join`.

The successful Run339b Production observation required **3,969 ms** to satisfy the hydration contract. This is a single observed value and **not an SLA**. The current audit uses a bounded 12-second hydration window and a 3-second post-hydration route window.

## 3. Logged-out cookie contract

The browser context must start with cookies `[]` and no seeded storage.

Run339b observed these note cookies after public navigation:

- `_note_session_v5`
- `_vid_v1`
- `_vid_v2`
- `fp`
- `note_gql_auth_token`
- `note_web_visitor_id`

`note_gql_auth_token` is **not sufficient evidence of login** in this public flow. It may be treated as an anonymous visitor token only when both conditions hold:

1. the browser began with zero cookies / no seeded storage; and
2. `ログイン` and `会員登録` are both positively visible on the hydrated page.

Any other cookie whose name is auth/token/login/user_id-like remains fail-closed. Run339b observed `explicit_auth_cookie_names_after=[]`.

## 4. Production audit contract

Current manual command:

`/aiif note membership public-audit`

Current workflow:

`.github/workflows/note-membership-public-funnel-audit.yml`

Current implementation:

`run339_membership_public_funnel_audit.py`

The audit is read-only. It must not click the join CTA or any other control. It must not fill forms, register, log in, alter membership settings, publish content, call Gemini/model APIs, or write Notion.

Production evidence:

- workflow run: `34437339132`
- audit job: `102745213582`
- artifact: `10136678201`
- artifact ZIP SHA256: `405a33d168bf4bcac432b5ca9696509022557149da235345ebd3446c6c2faafd`
- `clicks_performed=0`
- `field_filled=false`
- `save_clicked=false`
- `content_mutation=false`
- `settings_mutation=false`
- `membership_mutation=false`
- `public_mutation=false`
- `zero_gemini_calls=true`
- `notion_writes=0`

## 5. Authority boundaries

- Run325 / Run326b remain authority for the onboarding article's exact publication state and logged-out members-only entitlement boundary.
- Run334 / Run335 remain authority for the saved membership-plan description and no-resave convergence rule.
- Run339b is authority for the **fresh logged-out public purchase-funnel rendering and join-page surface**.
- A successful Run339b audit does not authorize any mutation. If a future audit fails, diagnose current note rendering before changing customer state.
