"""Soft time window penalties (linear) alongside hard :attr:`time_window` bounds."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TimeWindowFlex:
    """Optional soft bounds with linear penalty rates (same time units as hard windows).

    A component is *active* when both the bound and its matching penalty coefficient are set
    and the coefficient is strictly positive.
    """

    soft_earliest: int | None = None
    penalty_per_unit_before_soft_earliest: int | None = None
    soft_latest: int | None = None
    penalty_per_unit_after_soft_latest: int | None = None

    def has_soft_penalties(self) -> bool:
        early = (
            self.soft_earliest is not None and (self.penalty_per_unit_before_soft_earliest or 0) > 0
        )
        late = self.soft_latest is not None and (self.penalty_per_unit_after_soft_latest or 0) > 0
        return early or late
