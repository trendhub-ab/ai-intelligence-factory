#!/usr/bin/env python3
"""Run340: promote Run339b public purchase-funnel proof into canonical docs and retire Run338 diagnostics.

Deterministic zero-provider documentation migration only. It changes README/spec/reference content,
adds the Run339b purchase-funnel reference, and removes completed one-shot Run338 diagnostics plus
this Run340 sync machinery from the output branch. It performs no note, Notion, Gemini/model, or
other customer-state mutation.
"""
from __future__ import annotations

from pathlib import Path

README_BASELINE_ANCHOR = "- **Current paid member note onboarding baseline:** Run335 — Run325 article finalization / Run326b logged-out entitlement verification / Run334 membership-copy save / Run335 public+saved-form verification"
README_BASELINE_WITH_FUNNEL = README_BASELINE_ANCHOR + "\n- **Current paid member note purchase funnel baseline:** Run339b — hydrated logged-out `/membership` → `/membership/join` purchase-surface verification"
README_HEADING_OLD = "### Run325 / Run326b / Run335 — note member onboarding publication + customer-facing verification"
README_HEADING_NEW = "### Run325 / Run326b / Run335 / Run339b — note member onboarding publication + customer-facing verification"
README_REFS_OLD = """Current customer-surface contract: `docs/reference/RUN335_NOTE_ONBOARDING_CUSTOMER_SURFACE_BASELINE.md`.  
Historical article-publication contract: `docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md`."""
README_RUN339B_AND_REFS = """**Run339b — logged-out public purchase funnel**

- Fresh browser starts with cookie `[]` and navigates to `https://note.com/trendhub_biz/membership`.
- note may first expose a client-rendering shell. Production audit therefore waits for the actual plan/description/price/join/logged-out markers before judging the customer surface; the Run339b live observation hydrated in **3,969 ms**. This is an observation, not an SLA.
- After hydration, the exact customer route is `https://note.com/trendhub_biz/membership/join` with HTTP 200.
- The public purchase surface exposes `AI Decision Intelligence`, **¥1,980/月**, the current 114-character description, both existing paid benefits, the exact current onboarding article link, the current creator profile, and visible `参加手続きへ` actions; legacy onboarding-title/Product Hunt copy is absent.
- A fresh logged-out visitor may receive `note_gql_auth_token`. It is treated as anonymous **only** when the browser began with zero cookies and both `ログイン` and `会員登録` are positively visible. Any other auth/token/login/user_id-like cookie remains fail-closed.
- `/aiif note membership public-audit` is the current read-only purchase-funnel audit. It performs 0 clicks / 0 fills / 0 saves, zero Gemini/model calls, and zero Notion writes.

Current membership-plan saved-state contract: `docs/reference/RUN335_NOTE_ONBOARDING_CUSTOMER_SURFACE_BASELINE.md`.  
Current public purchase-funnel contract: `docs/reference/RUN339B_NOTE_PUBLIC_PURCHASE_FUNNEL_BASELINE.md`.  
Historical article-publication contract: `docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md`."""

SPEC_BASELINE_ANCHOR = "Paid Member note Onboarding Baseline: **Run335 — Run325 article finalization / Run326b logged-out entitlement verification / Run334 membership-copy save / Run335 public+saved-form verification**  "
SPEC_BASELINE_WITH_FUNNEL = SPEC_BASELINE_ANCHOR + "\nPaid Member note Purchase Funnel Baseline: **Run339b — hydrated logged-out `/membership` → `/membership/join` verification**  "
SPEC_HEADING_OLD = "### 2.8 note Member Onboarding Publication / Public Verification — Run325 / Run326b / Run335"
SPEC_HEADING_NEW = "### 2.8 note Member Onboarding Publication / Public Verification — Run325 / Run326b / Run335 / Run339b"
SPEC_REFS_OLD = """Production evidence: Run325 workflow `34388876334`; Run326b workflow `34416681984`; Run334 workflow `34433539671`; Run335 workflow `34433925788`; Run335 artifact `10135503385`.  
Current customer-surface contract: `docs/reference/RUN335_NOTE_ONBOARDING_CUSTOMER_SURFACE_BASELINE.md`.  
Historical article-publication contract: `docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md`."""
SPEC_RUN339B_AND_REFS = """**Run339b logged-out purchase-funnel contract**:

- the audit begins in a fresh browser with navigation-time cookies `[]` and no seeded storage;
- `https://note.com/trendhub_biz/membership` may initially be a client-rendering shell, so customer content is not judged at `DOMContentLoaded` alone;
- bounded hydration waits for the exact membership name, current 114-character description, observed ¥1,980/month price form, a visible join action, and positive logged-out UI;
- only after hydration does the route check require exact `https://note.com/trendhub_biz/membership/join`; Run339b Production observed HTTP 200 and hydration in **3,969 ms** (single observation, not an SLA);
- the hydrated surface must expose both existing paid benefits, the exact current onboarding article link/title, and current creator profile while legacy onboarding-title/Product Hunt copy remains absent;
- note-issued `note_gql_auth_token` is anonymous only when the context started with zero cookies and both `ログイン` / `会員登録` are visible. Any other auth/token/login/user_id-like cookie fails closed;
- `/aiif note membership public-audit` is read-only: clicks/fills/saves 0, content/settings/membership/public mutation 0, Gemini/model calls 0, Notion writes 0.

Production evidence: Run325 workflow `34388876334`; Run326b workflow `34416681984`; Run334 workflow `34433539671`; Run335 workflow `34433925788`; Run335 artifact `10135503385`; Run339b workflow `34437339132`; Run339b artifact `10136678201` (SHA256 `405a33d168bf4bcac432b5ca9696509022557149da235345ebd3446c6c2faafd`).  
Current membership-plan saved-state contract: `docs/reference/RUN335_NOTE_ONBOARDING_CUSTOMER_SURFACE_BASELINE.md`.  
Current public purchase-funnel contract: `docs/reference/RUN339B_NOTE_PUBLIC_PURCHASE_FUNNEL_BASELINE.md`.  
Historical article-publication contract: `docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md`."""

RUN335_RELATIONSHIP_OLD = """`docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md` remains the historical/current contract for Run325 article finalization and Run326b logged-out members-only verification. This Run335 reference adds the now-verified membership-plan customer surface and supersedes Run326b **only as the top-level note onboarding customer-surface baseline**; it does not replace the underlying Run325/326b article contracts.
"""
RUN335_RELATIONSHIP_NEW = RUN335_RELATIONSHIP_OLD + """
Public purchase-funnel rendering and logged-out join-page verification are governed separately by `docs/reference/RUN339B_NOTE_PUBLIC_PURCHASE_FUNNEL_BASELINE.md`. Run339b does not replace Run335 saved-state authority and does not authorize a membership resave.
"""

REFERENCE = """# Run339b — note Public Purchase Funnel Baseline

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
"""

CLEANUP_PATHS = (
    ".github/workflows/note-membership-public-surface-diagnostic.yml",
    "run338_membership_public_surface_diagnostic.py",
    "tests/test_run338_membership_public_surface_diagnostic.py",
    ".github/workflows/run340-documentation-sync.yml",
    "run340_documentation_sync.py",
    "tests/test_run340_documentation_sync.py",
)


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Run340 expected exactly one {label}; observed {count}")
    return text.replace(old, new, 1)


def sync_docs(root: Path, *, cleanup: bool) -> None:
    readme_path = root / "README.md"
    spec_path = root / "AI_Intelligence_Factory_最終仕様書.md"
    run335_path = root / "docs" / "reference" / "RUN335_NOTE_ONBOARDING_CUSTOMER_SURFACE_BASELINE.md"

    readme = readme_path.read_text(encoding="utf-8")
    spec = spec_path.read_text(encoding="utf-8")
    run335 = run335_path.read_text(encoding="utf-8")

    readme = _replace_once(readme, README_BASELINE_ANCHOR, README_BASELINE_WITH_FUNNEL, "README funnel baseline anchor")
    readme = _replace_once(readme, README_HEADING_OLD, README_HEADING_NEW, "README onboarding heading")
    readme = _replace_once(readme, README_REFS_OLD, README_RUN339B_AND_REFS, "README customer-surface references")

    spec = _replace_once(spec, SPEC_BASELINE_ANCHOR, SPEC_BASELINE_WITH_FUNNEL, "spec funnel baseline anchor")
    spec = _replace_once(spec, SPEC_HEADING_OLD, SPEC_HEADING_NEW, "spec onboarding heading")
    spec = _replace_once(spec, SPEC_REFS_OLD, SPEC_RUN339B_AND_REFS, "spec production evidence/reference block")

    run335 = _replace_once(run335, RUN335_RELATIONSHIP_OLD, RUN335_RELATIONSHIP_NEW, "Run335 relationship boundary")

    readme_path.write_text(readme, encoding="utf-8")
    spec_path.write_text(spec, encoding="utf-8")
    run335_path.write_text(run335, encoding="utf-8")

    ref = root / "docs" / "reference" / "RUN339B_NOTE_PUBLIC_PURCHASE_FUNNEL_BASELINE.md"
    ref.parent.mkdir(parents=True, exist_ok=True)
    if ref.exists():
        raise RuntimeError("Run340 refuses to overwrite an existing Run339b reference")
    ref.write_text(REFERENCE, encoding="utf-8")

    if cleanup:
        for relative in CLEANUP_PATHS:
            target = root / relative
            if not target.exists():
                raise RuntimeError(f"Run340 cleanup target missing: {relative}")
            target.unlink()


def main() -> None:
    sync_docs(Path("."), cleanup=True)
    print("RUN340_DOCUMENTATION_SYNC=PASS")
    print("note_mutations=0")
    print("zero_gemini_calls=true")
    print("notion_writes=0")


if __name__ == "__main__":
    main()
