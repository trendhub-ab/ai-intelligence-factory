#!/usr/bin/env python3
"""Run Subscriber Inventory Bootstrap with Run131 profit-aligned portfolio policy.

The mature inventory_bootstrap.py remains authoritative for Evidence, Product
Review, Notion persistence and quota safety. This entry point installs only the
Run131 review-order overlay, then delegates to the original command.

Run131 intentionally ignores the legacy hard source-share cap. Diversity may
reorder only candidates within PORTFOLIO_DIVERSITY_TOLERANCE of the strongest
remaining candidate, so a materially weaker record is never force-promoted.
"""
from __future__ import annotations

import inventory_bootstrap
from technology_portfolio_policy import install_on


def main() -> int:
    install_on(inventory_bootstrap)
    return inventory_bootstrap.main()


if __name__ == "__main__":
    raise SystemExit(main())
