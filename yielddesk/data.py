"""Bank of Canada Valet data: benchmark bond yields and the policy rate, cached on disk."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal, get_args

import httpx

VALET = "https://www.bankofcanada.ca/valet"
CACHE = Path(__file__).resolve().parents[1] / "data" / "yields.json"

Series = Literal["2y", "3y", "5y", "7y", "10y", "long", "real_return", "policy_rate"]
SERIES: tuple[Series, ...] = get_args(Series)

VALET_IDS: dict[Series, str] = {
    "2y": "BD.CDN.2YR.DQ.YLD",
    "3y": "BD.CDN.3YR.DQ.YLD",
    "5y": "BD.CDN.5YR.DQ.YLD",
    "7y": "BD.CDN.7YR.DQ.YLD",
    "10y": "BD.CDN.10YR.DQ.YLD",
    "long": "BD.CDN.LONG.DQ.YLD",
    "real_return": "BD.CDN.RRB.DQ.YLD",
    "policy_rate": "V39079",
}

LABELS: dict[Series, str] = {
    "2y": "2-year", "3y": "3-year", "5y": "5-year", "7y": "7-year", "10y": "10-year",
    "long": "long-term (30-year)", "real_return": "real return bond", "policy_rate": "policy rate",
}


@dataclass(frozen=True)
class Observations:
    """Daily values in percent, by series. Dates without a value (holidays) are simply absent."""

    values: dict[Series, dict[date, float]]

    @property
    def first(self) -> date:
        return min(min(v) for v in self.values.values() if v)

    @property
    def last(self) -> date:
        return max(max(v) for v in self.values.values() if v)

    def between(self, series: Series, start: date, end: date) -> list[tuple[date, float]]:
        return sorted((d, v) for d, v in self.values[series].items() if start <= d <= end)


def parse_valet(payloads: list[dict[str, Any]]) -> Observations:
    by_id = {v: k for k, v in VALET_IDS.items()}
    values: dict[Series, dict[date, float]] = {s: {} for s in SERIES}
    for payload in payloads:
        for row in payload["observations"]:
            day = date.fromisoformat(row["d"])
            for valet_id, cell in row.items():
                if valet_id in by_id and cell.get("v") not in (None, ""):
                    values[by_id[valet_id]][day] = float(cell["v"])
    return Observations(values)


def fetch(start: date, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    """Download the raw Valet payloads (benchmark bond group plus the policy rate)."""
    http = client or httpx.Client(timeout=30)
    urls = [
        f"{VALET}/observations/group/bond_yields_benchmark/json",
        f"{VALET}/observations/{VALET_IDS['policy_rate']}/json",
    ]
    payloads = []
    for url in urls:
        response = http.get(url, params={"start_date": start.isoformat()})
        response.raise_for_status()
        payloads.append(response.json())
    return payloads


def load(refresh: bool = False, start: date = date(2020, 1, 1)) -> Observations:
    if refresh or not CACHE.exists():
        CACHE.parent.mkdir(exist_ok=True)
        CACHE.write_text(json.dumps(fetch(start)))
    return parse_valet(json.loads(CACHE.read_text()))
