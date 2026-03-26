"""Time / schedule helpers (placeholders for shared TW logic)."""

from __future__ import annotations


def tw_duration(travel: int, service: int) -> int:
    """Total time spent on travel plus service at a stop."""
    return int(travel) + int(service)
