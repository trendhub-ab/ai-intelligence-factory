#!/usr/bin/env python3
"""Temporary deterministic Run225 canonical-doc patch helper."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "AI_Intelligence_Factory_最終仕様書.md"
README = ROOT / "README.md"


def insert_once(text: str, anchor: str, addition: str, marker: str) -> str:
    if marker in text:
        return text
    if anchor not in text:
        raise SystemExit(f"required documentation anchor missing: {anchor[:80]}")
    return text.replace(anchor, anchor + addition, 1)


def patch_spec() -> None:
    text = SPEC.read_text(encoding="utf-8")
    text = insert_once(
        text,
        "Article Deterministic Rescue Baseline: **Run224 — zero-model performance multiplier scope rescue**  \n",
        "Stock Lifecycle Baseline: **Run225 — zero-model Fresh/Aging/Evergreen/Archive active-stock management**  \n",
        "Stock Lifecycle Baseline: **Run225",
    )

    section = """
### 3.3 Screening Stock lifecycle — Run225

Screening Stockは履歴資産として保持するが、無期限の現役候補キューにはしない。`run225_stock_lifecycle.py`はGeminiを使わず、一次情報の鮮度と限定的なdurable-source例外だけでActive Stockを管理する。

- **Fresh**: 0〜30日。
- **Aging**: 31〜90日。日付不明/不正もFreshへ推測せずAgingとして扱う。
- **Evergreen**: 91日超でもGitHub/arXivのdurable assetで、明示的な一過性event/news signalがないもの。
- **Archive**: 91日超でEvergreen条件を満たさないもの。
- ArchiveはNotionから削除・trashしない。履歴として保持し、active review queueと会員ホームTop3候補からだけ外す。
- Raw Screening Stockの鮮度は`公開日`を優先し、`分析日`はfallbackに限る。再取込だけでFreshへ戻さない。
- current/human reviewが明示されるmember-product側では、そのreview時刻を最優先anchorとしてFreshへ再昇格できる。
- Content Intelligence DBの`更新状態`は書込量削減のためblankをFreshのcanonical encodingとし、Aging / Evergreen / Archiveだけを必要時にmaterializeする。
- `stock_lifecycle_reconcile.py`は`評価状態=Stocked`だけを対象に`更新状態`以外を変更しない。Score / Decision / Evidence / Article state / URL / source textは不変。
- `run225_portfolio_lifecycle.py`はRun131の後にinstallし、Archiveを除外した後のranking/diversityは既存Run131へ完全委譲する。
- `run225_member_lifecycle_ui.py`はRun170〜Run215のcurrent-copy authorityを置換せず、最終homepage ranking境界だけでFresh/Evergreen→Agingの順に優先しArchiveへrankを与えない。
- `.github/workflows/stock-lifecycle-reconcile.yml`はmanual ONE-SHOTのみ。`plan`はread-only、`apply`は`RECONCILE_STOCK`確認必須。Daily PAUSEDとPublic release human-onlyを変更しない。
- Gemini/model callは0、record deletionは0。

詳細: `docs/reference/RUN225_STOCK_LIFECYCLE.md`

"""
    marker = "### 3.3 Screening Stock lifecycle — Run225"
    if marker not in text:
        anchor = "## 4. 品質・Evidence契約\n"
        if anchor not in text:
            raise SystemExit("Run225 section insertion anchor missing")
        text = text.replace(anchor, section + anchor, 1)

    guard = "- Run225ではScreening Stockを削除せずFresh/Aging/Evergreen/Archiveでzero-model管理し、Archiveだけをactive review / member homepageから外す。Score・Decision・Evidence・Run131・Run170〜Run215 authorityを変更しない。\n"
    if guard not in text:
        anchor = "- Run224ではRun223が確認した性能倍率scope lossだけをzero-modelで局所補完し、倍率・Evidence・Decision・Score・URLを変更せず、通常Gate再評価を迂回しない。\n"
        if anchor not in text:
            raise SystemExit("Run225 docs guard anchor missing")
        text = text.replace(anchor, anchor + guard, 1)

    SPEC.write_text(text, encoding="utf-8")


def patch_readme() -> None:
    text = README.read_text(encoding="utf-8")
    text = insert_once(
        text,
        "- **Current paid member DB hosting baseline:** Run221 — API-host isolation / member-view separation\n",
        "- **Current stock lifecycle baseline:** Run225 — zero-model Fresh/Aging/Evergreen/Archive active-stock management\n",
        "Current stock lifecycle baseline:** Run225",
    )
    runtime_anchor = "- `technology_portfolio_policy.py`, `daily_portfolio_review.py` — portfolio prioritization/review logic\n"
    runtime_add = (
        "- `run225_stock_lifecycle.py`, `stock_lifecycle_reconcile.py` — zero-model Screening Stock freshness lifecycle / source reconciliation\n"
        "- `run225_portfolio_lifecycle.py`, `run225_member_lifecycle_ui.py` — Archive exclusion from active review/member-home ranking without deletion\n"
    )
    text = insert_once(
        text,
        runtime_anchor,
        runtime_add,
        "`run225_stock_lifecycle.py`, `stock_lifecycle_reconcile.py`",
    )
    README.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    patch_spec()
    patch_readme()
