#!/usr/bin/env python3
"""Fail closed when a paid-member customer surface is unowned or unreviewed."""
from __future__ import annotations

from pathlib import Path
import sys

import member_customer_surface_contract as contract

ROOT = Path(__file__).resolve().parent


def main() -> int:
    failures = contract.validate_repository(ROOT)
    if failures:
        print("MEMBER_SURFACE_COVERAGE=FAIL")
        for failure in failures:
            print("-", failure)
        return 1
    print("MEMBER_SURFACE_COVERAGE=PASS")
    print(f"registered_surfaces={len(contract.SURFACES)}")
    print(f"user_facing_view_contracts={len(contract.VIEW_CONTRACTS)}")
    print("zero_model_calls=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
