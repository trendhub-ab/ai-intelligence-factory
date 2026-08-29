#!/usr/bin/env python3
"""Run Subscriber Inventory Bootstrap with profit-aligned portfolio and launch policy.

The mature inventory_bootstrap.py remains authoritative for Evidence, Product
Review, Notion persistence and quota safety. This entry point installs only
zero-API policy overlays, then delegates to the original command.

Run131: diversity may reorder only candidates within PORTFOLIO_DIVERSITY_TOLERANCE
of the strongest remaining candidate, so a materially weaker record is never
force-promoted.

Run152: commercial launch readiness is stricter than mere inventory completeness.
It requires a sufficiently deep, AI-relevant, category-balanced member catalog
before launch_ready can become true. It never changes Adoption Score or Product
Review output.
"""
from __future__ import annotations

import inventory_bootstrap
from paid_db_launch_readiness import install_on as install_launch_readiness
from technology_portfolio_policy import install_on as install_portfolio_policy


def main() -> int:
    install_portfolio_policy(inventory_bootstrap)
    install_launch_readiness(inventory_bootstrap)
    return inventory_bootstrap.main()


if __name__ == "__main__":
    raise SystemExit(main())
