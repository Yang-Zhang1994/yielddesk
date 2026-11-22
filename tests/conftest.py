from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from yielddesk.data import SERIES, Observations


def business_days(start: date, end: date) -> list[date]:
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


@pytest.fixture
def obs() -> Observations:
    """Oct 1 - Nov 20, 2026. 10y rises 1 bp a day from 3.50; 2y falls 1 bp a day from 3.60, so the
    2s10s spread starts inverted at -10 bp and turns positive part way through."""
    days = business_days(date(2026, 10, 1), date(2026, 11, 20))
    values: dict[Any, dict[date, float]] = {s: {} for s in SERIES}
    for i, d in enumerate(days):
        values["10y"][d] = round(3.50 + 0.01 * i, 2)
        values["2y"][d] = round(3.60 - 0.01 * i, 2)
        values["5y"][d] = 3.40
        values["long"][d] = 4.00
        values["policy_rate"][d] = 2.75
    values["10y"][date(2026, 10, 15)] = 4.20  # one spike, for range high
    return Observations(values)


class FakeMessages:
    """Records calls; returns queued responses for parse() and create()."""

    def __init__(self, plans: list[Any] = (), texts: list[str] = (), stop_reason: str = "end_turn") -> None:
        self.plans, self.texts, self.stop_reason = list(plans), list(texts), stop_reason
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.calls.append(("parse", kwargs))
        return SimpleNamespace(stop_reason=self.stop_reason, parsed_output=self.plans.pop(0))

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(("create", kwargs))
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="thinking", thinking=""),
                                        SimpleNamespace(type="text", text=self.texts.pop(0))])
