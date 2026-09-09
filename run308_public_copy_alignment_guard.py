#!/usr/bin/env python3
"""Run308: fail-closed guard for current public/product copy alignment.

This guard is deliberately scoped to CURRENT reader-facing authority. Historical Run268/Run270
material may retain old wording for audit/compatibility. The guard is zero-network, zero-provider,
and never edits or publishes note.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN307_COPY = Path("docs/reference/RUN307_GENERIC_USE_DECISION_PRODUCT.md")
RUN308_HANDOFF = Path("docs/reference/RUN308_PUBLIC_COPY_ALIGNMENT.md")
ARTICLE_CTA = Path("run296_editorial_format_v2.py")
PAID_CONTRACT = Path("PAID_PRODUCT_CONTRACT.md")

CORE_PROMISE = "「このAI、使える！」を、根拠付きで判断できる。"
CURRENT_SOURCES = ("GitHub", "Hacker News", "ArXiv", "OfficialVendor")
CURRENT_CTA_LABEL = "月額1,980円の内容を見る"
LEGACY_VISIBLE_HEADINGS = (
    "顧客にどう答える？",
    "提案できる場面",
    "提案前に確認すること",
    "提案・検証の次の一手",
)


def _section(text: str, start: str, end: str | None = None) -> str:
    if start not in text:
        return ""
    value = text.split(start, 1)[1]
    if end and end in value:
        value = value.split(end, 1)[0]
    return value


def _audit_lp(text: str) -> list[str]:
    failures: list[str] = []
    lp = _section(text, "## Canonical fixed-note LP copy", "## Copy rules")
    if not lp:
        return ["run307_fixed_lp_section_missing"]
    if CORE_PROMISE not in lp:
        failures.append("run307_fixed_lp_core_promise_missing")
    for source in CURRENT_SOURCES:
        if source not in lp:
            failures.append(f"run307_fixed_lp_source_missing:{source}")
    if "Product Hunt" in lp or "ProductHunt" in lp:
        failures.append("run307_fixed_lp_stale_product_hunt")
    for heading in LEGACY_VISIBLE_HEADINGS:
        if heading in lp:
            failures.append(f"run307_fixed_lp_legacy_heading:{heading}")
    for phrase in ("自分の開発", "業務利用", "必要に応じ"):
        if phrase not in lp:
            failures.append(f"run307_fixed_lp_generic_use_missing:{phrase}")
    if CURRENT_CTA_LABEL not in lp:
        failures.append("run307_fixed_lp_current_cta_missing")
    return failures


def _audit_article_cta(text: str) -> list[str]:
    failures: list[str] = []
    if 'CTA_LINK_LABEL = "' + CURRENT_CTA_LABEL + '"' not in text:
        failures.append("article_cta_label_not_current")
    if "このAI、使える！" not in text:
        failures.append("article_cta_core_promise_missing")
    return failures


def _audit_paid_contract(text: str) -> list[str]:
    failures: list[str] = []
    route = _section(text, "## 10. note有料導線", "## 11.")
    if not route:
        return ["paid_contract_note_route_missing"]
    if "このAI、使える！" not in route:
        failures.append("paid_contract_note_route_core_promise_missing")
    if CURRENT_CTA_LABEL not in route:
        failures.append("paid_contract_note_route_current_cta_missing")
    if "human-only" not in route:
        failures.append("paid_contract_public_note_human_only_missing")
    return failures


def _audit_handoff(text: str) -> list[str]:
    failures: list[str] = []
    for source in CURRENT_SOURCES:
        if source not in text:
            failures.append(f"run308_handoff_source_missing:{source}")
    if "Product Hunt" in _section(text, "## 手動反映用・現行プロフィール/署名", "## 反映ルール"):
        failures.append("run308_handoff_profile_stale_product_hunt")
    if CORE_PROMISE not in text:
        failures.append("run308_handoff_core_promise_missing")
    if "公開noteはhuman-only" not in text:
        failures.append("run308_handoff_human_only_missing")
    return failures


def audit(root: Path = ROOT) -> list[str]:
    failures: list[str] = []
    required = {
        RUN307_COPY: _audit_lp,
        ARTICLE_CTA: _audit_article_cta,
        PAID_CONTRACT: _audit_paid_contract,
        RUN308_HANDOFF: _audit_handoff,
    }
    for rel, checker in required.items():
        path = root / rel
        if not path.is_file():
            failures.append(f"run308_current_surface_missing:{rel.as_posix()}")
            continue
        failures.extend(checker(path.read_text(encoding="utf-8")))
    return list(dict.fromkeys(failures))


def main() -> None:
    failures = audit()
    if failures:
        print("RUN308_PUBLIC_COPY_ALIGNMENT=FAIL")
        for item in failures:
            print("-", item)
        raise SystemExit(1)
    print("RUN308_PUBLIC_COPY_ALIGNMENT=PASS")
    print("zero_provider_calls=true")
    print("public_note_mutation=false")


if __name__ == "__main__":
    main()
