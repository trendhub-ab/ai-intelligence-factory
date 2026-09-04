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

Run164: high-precision relevance vocabulary is calibrated against the expanded
catalog before the launch gate is installed. Bare agent/model/GPU/ML tokens stay
excluded so generic software cannot gain AI relevance accidentally.

Run225: Screening Stock is historical inventory, not an infinite active queue.
Records classified Archive (>90 days unless durable Evergreen) are excluded from
active review planning without deleting or mutating the underlying Notion asset.
"""
from __future__ import annotations

import sys

import inventory_bootstrap
import paid_db_launch_readiness
import run203_runtime_state_channel
from paid_db_launch_readiness import install_on as install_launch_readiness
from run164_ai_relevance_calibration import install_on as install_ai_relevance_calibration
from run225_portfolio_lifecycle import install_on as install_stock_lifecycle
from technology_portfolio_policy import install_on as install_portfolio_policy


def main() -> int:
    # Manual bootstrap apply also launches the authoritative pipeline directly, so it
    # must use the same protected-main state isolation as ONE-SHOT. Plan mode remains
    # read-only and therefore does not perform the write preflight.
    run203_runtime_state_channel.apply_runtime_state_env()
    if len(sys.argv) > 1 and str(sys.argv[1]).lower() == "apply":
        run203_runtime_state_channel.preflight_runtime_state_channel()

    install_portfolio_policy(inventory_bootstrap)
    # Install after Run131 so lifecycle only removes Archive records; all remaining
    # ranking/diversity semantics stay owned by the existing authoritative planner.
    install_stock_lifecycle(inventory_bootstrap)
    install_ai_relevance_calibration(paid_db_launch_readiness)
    install_launch_readiness(inventory_bootstrap)
    return inventory_bootstrap.main()


if __name__ == "__main__":
    raise SystemExit(main())
