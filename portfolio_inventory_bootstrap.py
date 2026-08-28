#!/usr/bin/env python3
"""Run Subscriber Inventory Bootstrap with Run130 Technology Portfolio policy.

The mature inventory_bootstrap.py remains untouched. This entry point installs a
planning-only portfolio policy, then delegates to the original command. This keeps
rollback trivial and preserves all Evidence, Product Review, Notion and quota safety.
"""
from __future__ import annotations

import inventory_bootstrap
from technology_portfolio_policy import install_on


def main() -> int:
    install_on(inventory_bootstrap)
    return inventory_bootstrap.main()


if __name__ == "__main__":
    raise SystemExit(main())
