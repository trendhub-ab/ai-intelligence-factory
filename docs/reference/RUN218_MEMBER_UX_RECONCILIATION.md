# Run218 — Paid Member UX Reconciliation

Date: 2026-09-03  
Status: **current paid-member navigation/UI contract; database destination superseded by Run220**  
Gemini/model requests used for this run: **0**

## Purpose

Run218 reconciles the live paid-member Notion experience from the customer's point of view. It fixes navigation and information-architecture errors found after Run217 without changing Decision Intelligence facts, scores, judgments, Evidence, article generation, or model usage.

The core operating assumption is explicit:

**PC is the primary member experience. Mobile/simple views are secondary fallback surfaces only.**

Run220 later corrected the physical presentation-database destination. Run218 remains authoritative for information architecture and UX; Run220 is authoritative for the exact current Database/Data Source IDs.

## Root cause corrected

Run217 created a second home page and audited that new page instead of fully validating the pre-existing customer-facing home. As a result, the live member home still contained:

- a mobile-first important-change callout despite PC-first use
- an empty PC important-change table
- more than one active-looking member home
- an overly broad “導入・お試し候補” list
- internal-looking breadcrumbs through `mlflow/mlflow`
- hard-coded Top3 cards that could drift from the live priority ranking
- redundant search/navigation entries

Run218 corrects those issues in the live workspace and makes the correction a repository contract.

## Canonical member entrypoint

The only current onboarding destination is:

- Title: `AI Decision Intelligence｜会員ホーム`
- Page ID: `3c5479ff-dca9-8103-bff0-f2d5f408d35f`
- URL: `https://app.notion.com/p/3c5479ffdca98103bff0f2d5f408d35f`

The page created by Run217 is superseded:

- Page ID: `3d0479ff-dca9-819e-9da0-c951225de6b3`
- Title: `【旧・統合済み】AI Intelligence｜会員ホーム`
- It must never be used as a new-member invite, bookmark target, LP destination, or operator canonical URL.

## Current member product data

Run220 current destination:

- Current presentation DB ID: `b2787ee0-5b58-4ca7-b4eb-774f60237f1f`
- Current presentation data source ID: `7e4ceaa7-7bdf-4c4b-bf78-c2cccac44404`
- Pre-Run220 presentation DB ID: `d6ca3c1f-cb2c-4686-b442-d9ba3923e5f1`
- Pre-Run220 data source ID: `d1461b6f-0940-4bf9-803a-6686a37c4ba2`
- Legacy 100-row DB ID: `9430d2a5-b9ce-423a-b76e-d9214f3f6204`
- Legacy data source ID: `ec2ac2b3-89b6-4242-89b9-e94060826fca`

The two old presentation generations remain `旧版・使用禁止` / audit-only and are not onboarding or workflow destinations.

The current presentation DB and current Digest are under the canonical member home. A member opening an item should see the customer-facing hierarchy:

`AI Decision Intelligence｜会員ホーム → AI・技術一覧｜判断DB → individual item`

The internal `mlflow/mlflow` source record must not appear in the normal customer breadcrumb.

## PC-first information architecture

### 1. First view: live priority Top3

The home must not depend on manually written fixed cards for Dify or any other product. The first section is a live view using `注目順位 <= 3`, sorted ascending.

Member-facing columns are intentionally limited to decision-useful fields such as:
- AI・技術名
- 判断
- 判断スコア
- これは何？
- 次にやること
- 最終確認日

The title column is frozen and cells wrap for PC comparison.

### 2. High-priority practical shortlist

The old broad “導入・お試し候補” surface could expose over 100 rows and did not function as a shortlist.

The current high-priority practical view is deliberately narrower. Its selection logic is:
- `分類 = 実務判断`
- `判断 IN (ADOPT, TEST)`
- `根拠の確かさ != 低`
- `判断スコア >= 89`
- exclude current Top3 via `注目順位 IS EMPTY OR 注目順位 > 3`

The exact row count may change as the DB changes; customer copy must not hard-code a current count.

### 3. Full search and status/category views

The primary full-inventory surface is the current canonical DB's `すべてから探す` view.

Secondary PC views include:
- `分野から探す`
- `導入を考えてよいもの`
- `まず小さく試したいもの`
- `もう少し様子を見たいもの`
- `今は選ばない方がよいもの`
- `まとめて比べる`
- `最近、評価が上がったもの`
- `これから注目したい新技術`

These views should prioritize fields that help a member decide or act. Internal sync identifiers and other operator-only properties are not part of the default customer surface.

### 4. Mobile/simple views are secondary

`スマホで見る` remains available as a fallback surface, but it is intentionally secondary.

No primary home copy may imply that mobile is the default or preferred usage environment while the product is PC-first.

## Important-change UX contract

Run218 distinguishes **source semantics** from **presentation semantics**.

The source field `今月の重要変化` must not be changed merely to avoid an empty UI.

At the Run218 audit time:
- `今月の重要変化 = true`: 0 rows
- records with `ABS(評価の変化) >= 20`: 10 rows

The corrected presentation shows existing authoritative history where:
- `評価の変化 >= 20`, or
- `評価の変化 <= -20`

This is a **presentation-only fallback**. It does not mark a record as an important change, does not modify the monthly checkbox, and does not invent a score movement.

A primary customer surface must not show an unexplained blank table when a meaningful alternative view can be derived from already-authoritative data. If no relevant rows exist even after the defined presentation fallback, show a clear empty-state explanation rather than a blank primary block.

## Dynamic-copy contract

Member-home copy should avoid hard-coded values that become stale through routine synchronization, including:
- current total row count
- current shortlist count
- hard-coded Top3 product names
- current-month “0件” statements

Snapshot counts may appear in dated audit documentation, but not in evergreen home instructions unless they are dynamically derived.

## Digest placement

Current Digest:
- Title: `会員限定Digest｜2026年9月 初回版`
- Page ID: `3d0479ff-dca9-81de-b614-fef528d2f32c`

It is a child of the canonical member home and linked near the top for time-poor members.

## UX acceptance criteria

A paid member using a PC should be able to:

1. open one canonical home URL
2. understand within the first screen that the product is for decisions, not raw news consumption
3. reach the live Top3 immediately
4. move to a deliberately short high-priority practical list
5. search the full inventory from a clear PC-first entrypoint
6. filter by judgment or category without exposing internal fields
7. see recent large decision changes without encountering an unexplained blank table
8. open an individual record without an internal-source breadcrumb
9. reach the current Digest from the same home
10. use mobile/simple views only when needed

## Safety / non-goals

Run218 / Run220 navigation work does not:
- call Gemini or any model API
- change article-generation logic
- change Decision scores or judgments
- change Evidence or primary-source authority
- rewrite `今月の重要変化` to make the UI look active
- change `評価の変化` values
- resume Daily
- enable public note auto-release

Daily remains PAUSED and public note release remains human-only.

Exact current DB destination contract: `docs/reference/RUN220_MEMBER_DB_CANONICAL_CUTOVER.md`.
