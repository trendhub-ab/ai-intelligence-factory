"""Isolated X -> Factory discovery ingestion PoC.

All records produced by this package are discovery signals only. They are never
promoted to Factory evidence by this package.
"""

from .models import DiscoveryCandidate, DiscoverySignal
from .providers import ApifyProvider, FixtureProvider, XDiscoveryProvider

__all__ = [
    "ApifyProvider",
    "DiscoveryCandidate",
    "DiscoverySignal",
    "FixtureProvider",
    "XDiscoveryProvider",
]
