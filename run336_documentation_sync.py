#!/usr/bin/env python3
"""Run336: promote Run335 note customer-surface proof into canonical docs, then retire one-shot audit machinery.

This is a deterministic zero-provider documentation migration. It changes only README/spec/reference
content and removes the completed Run335 audit + this one-shot Run336 sync machinery from the output
branch. It performs no note, Notion, Gemini/model, or network mutation.
"""
from __future__ import annotations

from pathlib import Path

README_BASELINE_OLD = "- **Current paid member note onboarding baseline:** Run326b — Run325 exact latest-draft finalization / Run326b logged-out members-only verification"
README_BASELINE_NEW = "- **Current paid member note onboarding baseline:** Run335 — Run325 article finalization / Run326b logged-out entitlement verification / Run334 membership-copy save / Run335 public+saved-form verification"
README_HEADING_OLD = "### Run325 / Run326b — note member onboarding publication + customer-facing verification"
README_HEADING_NEW = "### Run325 / Run326b / Run335 — note member onboarding publication + customer-facing verification"
README_ANCHOR = "Full contract: `docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md`."
README_RUN335_BLOCK = """**Run334 / Run335 — membership description convergence**

- `AI Decision Intelligence` remains **¥1,980/月**; the existing Decision DB and Digest benefits are unchanged.
- Current plan description is **114 characters** and no longer hard-codes the retired onboarding article title. The durable guidance is `参加後は、メンバー限定の「最初にお読みください」記事をご確認ください。`.
- Run334 used the exact audited plan edit route and one exact `プランを変更する` click. Its immediate public check still observed the legacy copy during note propagation and failed closed; it was **not retried**.
- Run335 then used **0 clicks / 0 fills / 0 saves** and verified `public_state=current`, `edit_state=current`, `public_edit_consistent=true`, plus exact plan-name / ¥1,980 fee / two existing-benefit invariants.
- Therefore Run334's save succeeded; the Run334 failure was a short public-propagation false negative, not a failed save. When the current 114-character copy is present, **do not resave**.
- Run335 used zero Gemini/model calls and zero Notion writes.

Current customer-surface contract: `docs/reference/RUN335_NOTE_ONBOARDING_CUSTOMER_SURFACE_BASELINE.md`.  
Historical article-publication contract: `docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md`."""

SPEC_BASELINE_OLD = "Paid Member note Onboarding Baseline: **Run326b — Run325 exact latest-draft finalization / Run326b logged-out members-only verification**  "
SPEC_BASELINE_NEW = "Paid Member note Onboarding Baseline: **Run335 — Run325 article finalization / Run326b logged-out entitlement verification / Run334 membership-copy save / Run335 public+saved-form verification**  "
SPEC_HEADING_OLD = "### 2.8 note Member Onboarding Publication / Public Verification — Run325 / Run326b"
SPEC_HEADING_NEW = "### 2.8 note Member Onboarding Publication / Public Verification — Run325 / Run326b / Run335"
SPEC_EVIDENCE_OLD = "Production evidence: Run325 workflow `34388876334`; Run326b workflow `34416681984`.  \nFull contract: `docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md`."
SPEC_EVIDENCE_NEW = """**Run334 / Run335 membership-description contract**:

- target plan is exact `AI Decision Intelligence` at `https://note.com/membership/settings/plans/358b94bcb3c6/edit`;
- current description is 114 characters and ends with `参加後は、メンバー限定の「最初にお読みください」記事をご確認ください。`; the legacy `はじめに｜AI Decision Intelligenceの利用方法` reference is absent;
- plan name, `1,980 円/月` fee marker, and the two existing benefits (`AI Decision Intelligence｜会員向け意思決定DB` / `AI Decision Intelligence｜会員向けDigest`) remain unchanged;
- Run334 executed one exact `プランを変更する` click. Its bounded immediate public verification still saw legacy content and failed closed. No automatic or manual retry was issued;
- Run335 subsequently verified `public_state=current`, `edit_state=current`, `public_edit_consistent=true` with zero clicks/fills/saves, proving Run334's save succeeded and the earlier failure was public propagation delay;
- if both public and saved edit state are already current, operator action is **no resave / no mutation**;
- Run335 Gemini/model calls 0, Notion writes 0.

Production evidence: Run325 workflow `34388876334`; Run326b workflow `34416681984`; Run334 workflow `34433539671`; Run335 workflow `34433925788`; Run335 artifact `10135503385`.  
Current customer-surface contract: `docs/reference/RUN335_NOTE_ONBOARDING_CUSTOMER_SURFACE_BASELINE.md`.  
Historical article-publication contract: `docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md`."""

REFERENCE = """# Run335 — note Onboarding Customer Surface Baseline

Status: **Production verified / current**  
Date: **2026-09-10**  
Scope: paid-member note onboarding article + membership-plan customer-facing copy  
Provider cost: **0 Gemini/model calls / 0 Notion writes for verification**

## 1. Current customer-facing state

### Onboarding article

- note ID: `n284e428c80f4`
- public title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- finalized body SHA256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- membership: `AI Decision Intelligence`
- logged-out entitlement proof remains Run326b: members-only gate present and protected deep-body markers absent.

### Membership plan

- plan: `AI Decision Intelligence`
- fee: `¥1,980/月`
- exact owner edit route: `https://note.com/membership/settings/plans/358b94bcb3c6/edit`
- current description length: **114 characters**
- durable final guidance: `参加後は、メンバー限定の「最初にお読みください」記事をご確認ください。`
- legacy article-name reference `はじめに｜AI Decision Intelligenceの利用方法`: **absent**
- existing benefits preserved:
  - `AI Decision Intelligence｜会員向け意思決定DB`
  - `AI Decision Intelligence｜会員向けDigest`

## 2. Convergence proof

### Run334 — exact save

Workflow: `34433539671`

Run334 repaired only the Playwright Locator-to-DOM snapshot transport that had stopped Run333 before mutation. It then reached the exact membership plan, preserved the audited plan/fee/benefit invariants, filled only the authorized description, and executed one exact `プランを変更する` click.

The bounded immediate public verification still returned the legacy copy and the workflow failed closed. Because the final click had already occurred, the updater was **not rerun**.

### Run335 — zero-mutation state audit

Workflow: `34433925788`  
Artifact: `10135503385`  
Artifact SHA256: `8b398e98853b2629ba07d43f47c5d23b316908827e2cb6f73c991a391008872c`

Observed state:

- `public_state=current`
- `edit_state=current`
- `public_edit_consistent=true`
- `plan_name_verified=true`
- `fee_marker_verified=true`
- `benefits_verified=true`
- `description_chars=114`
- clicks `0`
- fills `0`
- saves `0`
- Gemini/model calls `0`
- Notion writes `0`

Conclusion: **Run334 saved successfully.** Its post-save failure was a short public-propagation/cache false negative, not a failed save.

## 3. Production operator contract

1. Do not resave the membership plan merely because an immediate public read briefly shows the prior copy after a confirmed exact save.
2. First compare the server-saved edit form and public customer surface with a read-only audit.
3. If both are current, stop: no additional click, fill, or save is authorized.
4. Any future membership-copy mutation must remain hard-bound to the exact plan, expected prior/current copy, plan-name/fee/benefit invariants, and an explicit manual command.
5. Do not change `すべてのプラン（全員に公開）`, trial-read behavior, plan price, or existing benefits as part of onboarding-copy maintenance.

## 4. Relationship to prior baseline

`docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md` remains the historical/current contract for Run325 article finalization and Run326b logged-out members-only verification. This Run335 reference adds the now-verified membership-plan customer surface and supersedes Run326b **only as the top-level note onboarding customer-surface baseline**; it does not replace the underlying Run325/326b article contracts.
"""

CLEANUP_PATHS = (
    ".github/workflows/note-membership-description-postsave-audit.yml",
    "run335_membership_description_postsave_readonly_audit.py",
    "tests/test_run335_membership_description_postsave_readonly_audit.py",
    ".github/workflows/run336-documentation-sync.yml",
    "run336_documentation_sync.py",
    "tests/test_run336_documentation_sync.py",
)


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Run336 expected exactly one {label}; observed {count}")
    return text.replace(old, new, 1)


def sync_docs(root: Path, *, cleanup: bool) -> None:
    readme_path = root / "README.md"
    spec_path = root / "AI_Intelligence_Factory_最終仕様書.md"
    readme = readme_path.read_text(encoding="utf-8")
    spec = spec_path.read_text(encoding="utf-8")

    readme = _replace_once(readme, README_BASELINE_OLD, README_BASELINE_NEW, "README baseline")
    readme = _replace_once(readme, README_HEADING_OLD, README_HEADING_NEW, "README onboarding heading")
    readme = _replace_once(readme, README_ANCHOR, README_RUN335_BLOCK, "README Run327 anchor")

    spec = _replace_once(spec, SPEC_BASELINE_OLD, SPEC_BASELINE_NEW, "spec baseline")
    spec = _replace_once(spec, SPEC_HEADING_OLD, SPEC_HEADING_NEW, "spec onboarding heading")
    spec = _replace_once(spec, SPEC_EVIDENCE_OLD, SPEC_EVIDENCE_NEW, "spec production evidence")

    readme_path.write_text(readme, encoding="utf-8")
    spec_path.write_text(spec, encoding="utf-8")
    ref = root / "docs" / "reference" / "RUN335_NOTE_ONBOARDING_CUSTOMER_SURFACE_BASELINE.md"
    ref.parent.mkdir(parents=True, exist_ok=True)
    ref.write_text(REFERENCE, encoding="utf-8")

    if cleanup:
        for relative in CLEANUP_PATHS:
            target = root / relative
            if not target.exists():
                raise RuntimeError(f"Run336 cleanup target missing: {relative}")
            target.unlink()


def main() -> None:
    sync_docs(Path("."), cleanup=True)
    print("RUN336_DOCUMENTATION_SYNC=PASS")
    print("zero_gemini_calls=true")
    print("notion_writes=0")


if __name__ == "__main__":
    main()
