#!/usr/bin/env python3
"""Run327 one-time deterministic canonical-doc sync for Run325/326b.

This utility performs text-only documentation edits. It has no network/provider path.
It is intentionally fail-closed: every insertion anchor must occur exactly once unless the
new contract is already present. The temporary workflow that executes this utility deletes
this file and itself from the generated documentation PR branch after applying the sync.
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
README = ROOT / "README.md"
SPEC = ROOT / "AI_Intelligence_Factory_最終仕様書.md"

README_BASELINE = (
    "- **Current paid member note onboarding baseline:** Run326b — "
    "Run325 exact latest-draft finalization / Run326b logged-out members-only verification"
)
SPEC_BASELINE = (
    "Paid Member note Onboarding Baseline: **Run326b — Run325 exact latest-draft finalization / "
    "Run326b logged-out members-only verification**  "
)
REFERENCE = "docs/reference/RUN327_NOTE_ONBOARDING_PRODUCTION_BASELINE.md"


def _insert_once(text: str, anchor: str, insertion: str, *, label: str) -> str:
    if insertion in text:
        return text
    count = text.count(anchor)
    if count != 1:
        raise RuntimeError(f"Run327 {label} anchor count must be 1, got {count}")
    return text.replace(anchor, anchor + insertion, 1)


def _replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Run327 {label} replacement count must be 1, got {count}")
    return text.replace(old, new, 1)


def render_readme(text: str) -> str:
    text = _insert_once(
        text,
        "- **Current paid member commerce/onboarding baseline:** Run217 — zero-API monetization readiness / product fulfillment\n",
        README_BASELINE + "\n",
        label="README baseline",
    )

    section = f"""
### Run325 / Run326b — note member onboarding publication + customer-facing verification

The current paid-member onboarding-note contract is split into a hard-bound maintenance path and a zero-click public audit.

- Canonical note: `n284e428c80f4`
- Current title: `【最初にお読みください】「このAI、使える！」を判断するための使い方`
- Exact finalized body SHA256: `aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`
- Run325 finalizes only through the proven existing-article route: latest draft → `公開に進む` → `試し読みエリアを設定` → **no trial-read line** → one exact `更新する`.
- The article remains attached to `AI Decision Intelligence`; all-plans exposure is not added.
- Run326b audits the public URL from a fresh zero-cookie browser with **zero clicks**, verifies the new title / no not-for-sale state / members-only gate, and proves protected deep-body markers are not exposed logged out.
- `/aiif note onboarding update` is the exact maintenance command; `/aiif note onboarding public-audit` is read-only.
- Zero Gemini/model calls and zero Notion writes on both paths.

Full contract: `{REFERENCE}`.

"""
    text = _insert_once(
        text,
        "Full hosting contract: `docs/reference/RUN221_MEMBER_DB_HOST_ISOLATION.md`.\n\n",
        section,
        label="README Run325/326b section",
    )

    freshness = (
        "- Run325/Run326b paid-member note onboarding must preserve the exact existing-article latest-draft route, "
        "keep the trial-read line unset for full members-only access, retain `AI Decision Intelligence` without all-plans exposure, "
        "and pass the zero-click logged-out public audit before the customer-facing update is considered fully verified.\n"
    )
    text = _insert_once(
        text,
        "- Run272 must keep acquisition/source dates raw until persistence, canonicalize only at the Notion date boundary, defer arXiv health checks after a run-local fetch-error circuit opens without mutating Evidence, and keep Product Review child runtime bounded without extending the global Daily timeout or Gemini budgets.\n",
        freshness,
        label="README freshness",
    )
    return text


def render_spec(text: str) -> str:
    text = _replace_once(
        text,
        "最終更新: 2026-09-09  ",
        "最終更新: 2026-09-10  ",
        label="canonical spec date",
    )
    text = _insert_once(
        text,
        "Paid Member Commerce/Onboarding Baseline: **Run217**  \n",
        SPEC_BASELINE + "\n",
        label="canonical spec baseline",
    )

    section = f"""
### 2.8 note Member Onboarding Publication / Public Verification — Run325 / Run326b

Paid-member onboarding note `n284e428c80f4` is governed by a three-layer proof: exact manuscript state, existing-article public finalization, and logged-out entitlement verification.

Current public title:

`【最初にお読みください】「このAI、使える！」を判断するための使い方`

Exact finalized body SHA256:

`aab9e57bbb152b8be053c54cb2e5782f37b52b98dbbf0eb04313ed96f2063ba6`

**Run325 maintenance contract**:

- existing article → edit → latest draft → `公開に進む` → `試し読みエリアを設定` → **trial-read lineを選択しない** → `更新する`を1回だけ;
- title/body SHAがexact current stateでなければfail closed;
- `AI Decision Intelligence`への特典紐付けを維持し、`すべてのプラン（全員に公開）`は追加しない;
- 既に収束済みならpublic updateを再クリックしないidempotent no-op;
- old Run315 DOM-range route is historical regression coverage only and is not the dispatched Production live route.

**Run326b customer-facing verification contract**:

- fresh browserはnavigation前cookie `[]`; storage/cookieをseedしない;
- noteが匿名visitorへ発行する `_note_session_v5` はseeded authenticationとは扱わない一方、明示的auth/token/login/user-id cookieはfail closed;
- public URLはHTTP 200、新タイトル一致、legacy titleなし、`この記事は現在販売されていません`なし;
- `メンバーシップ` / `メンバー限定` gateを確認し、保護された本文深部markerはlogged-out DOMに露出しない;
- clicks 0、content/settings/membership/public mutation 0;
- Gemini/model call 0、Notion write 0.

Production evidence: Run325 workflow `34388876334`; Run326b workflow `34416681984`.  
Full contract: `{REFERENCE}`.

"""
    anchor = "詳細・反証・Production timingは `docs/reference/RUN271_MEMBER_BODY_DELTA_SYNC.md` を正本とする。2026-09-07の通常delta Production観測では、206件中 `scanned_body_pages=0` / `skipped_by_delta=206` / `sentinel_checked=1` / `delta_fallback_full=false`、本文stepは約**2.34秒**だった。Run270移行時の約13分23秒比で約**343.4倍高速・99.71%短縮**。単一no-change観測でありSLAではない。\n\n"
    text = _insert_once(text, anchor, section, label="canonical spec section 2.8")
    return text


def render() -> tuple[str, str]:
    return render_readme(README.read_text(encoding="utf-8")), render_spec(SPEC.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    readme, spec = render()
    if args.write:
        README.write_text(readme, encoding="utf-8")
        SPEC.write_text(spec, encoding="utf-8")
        print("RUN327_DOCUMENTATION_SYNC=written")
    else:
        print("RUN327_DOCUMENTATION_SYNC=validated")


if __name__ == "__main__":
    main()
