"""The typed query plan Claude produces, and the deterministic code that answers it.

Claude only translates the question into a QueryPlan. All arithmetic happens here, in code, so a
number in the answer is never something the model made up.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from .data import LABELS, Observations, Series

Intent = Literal["latest", "change", "spread", "range", "unsupported"]


class QueryPlan(BaseModel):
    intent: Intent = Field(description=(
        "latest: most recent value(s); change: how much series moved from start to end; "
        "spread: difference first minus second over the period; range: high, low and average over "
        "the period; unsupported: the data cannot answer the question"))
    series: list[Series] = Field(description="Series in order. spread needs exactly two: [long_end, short_end].")
    start: date | None = Field(description="First day of the period (ISO date), or null for latest")
    end: date | None = Field(description="Last day of the period (ISO date), or null for latest")
    reason: str | None = Field(description="Only for unsupported: why the data cannot answer it")


class PlanError(ValueError):
    """The plan is well-formed JSON but cannot be run (e.g. a spread with one series)."""


class Point(BaseModel):
    date: date
    value: float


class Line(BaseModel):
    series: Series
    label: str
    points: list[Point]


class Answer(BaseModel):
    """Everything the UI shows and the explainer may quote. Values in percent; bp = basis points."""

    intent: Intent
    start: date | None
    end: date | None
    facts: dict[str, int | float | str]
    lines: list[Line]


def bp(pct: float) -> float:
    return round(pct * 100, 1)


def _window(obs: Observations, plan: QueryPlan) -> tuple[date, date]:
    end = min(plan.end or obs.last, obs.last)
    start = plan.start or end - timedelta(days=30)
    if start > end:
        raise PlanError(f"The period starts ({start}) after it ends ({end}).")
    if end < obs.first:
        raise PlanError(f"Data starts on {obs.first}.")
    return max(start, obs.first), end


def run(plan: QueryPlan, obs: Observations) -> Answer:
    if plan.intent == "unsupported":
        return Answer(intent="unsupported", start=None, end=None,
                      facts={"reason": plan.reason or "The data can't answer that."}, lines=[])
    if not plan.series:
        raise PlanError("The plan names no series.")
    if plan.intent == "spread" and len(plan.series) != 2:
        raise PlanError("A spread needs exactly two series.")

    if plan.intent == "latest":
        facts: dict[str, int | float | str] = {}
        for s in plan.series:
            day, value = max(obs.values[s].items())
            facts[f"{s} %"] = value
            facts[f"{s} as of"] = day.isoformat()
        return Answer(intent="latest", start=None, end=obs.last, facts=facts, lines=[])

    start, end = _window(obs, plan)
    lines = [Line(series=s, label=LABELS[s], points=[Point(date=d, value=v) for d, v in obs.between(s, start, end)])
             for s in plan.series]
    for line in lines:
        if len(line.points) < 2:
            raise PlanError(f"Not enough {line.label} data between {start} and {end}.")

    facts = {}
    if plan.intent == "change":
        for line in lines:
            first, last = line.points[0], line.points[-1]
            facts[f"{line.series} start %"] = first.value
            facts[f"{line.series} end %"] = last.value
            facts[f"{line.series} change bp"] = bp(last.value - first.value)
    elif plan.intent == "range":
        for line in lines:
            vals = [p.value for p in line.points]
            hi = max(line.points, key=lambda p: p.value)
            lo = min(line.points, key=lambda p: p.value)
            facts[f"{line.series} high %"] = hi.value
            facts[f"{line.series} high on"] = hi.date.isoformat()
            facts[f"{line.series} low %"] = lo.value
            facts[f"{line.series} low on"] = lo.date.isoformat()
            facts[f"{line.series} average %"] = round(sum(vals) / len(vals), 2)
    else:  # spread: long minus short on days both have a value
        a, b = lines
        b_by_day = {p.date: p.value for p in b.points}
        diffs = [Point(date=p.date, value=bp(p.value - b_by_day[p.date])) for p in a.points if p.date in b_by_day]
        if len(diffs) < 2:
            raise PlanError("The two series have no overlapping days in that period.")
        name = f"{a.series}-{b.series}"
        facts[f"{name} spread start bp"] = diffs[0].value
        facts[f"{name} spread end bp"] = diffs[-1].value
        facts[f"{name} spread change bp"] = round(diffs[-1].value - diffs[0].value, 1)
        facts[f"{name} inverted days"] = sum(1 for d in diffs if d.value < 0)
        lines = [Line(series=a.series, label=f"{a.label} minus {b.label} (bp)", points=diffs)]
    facts["trading days"] = len(lines[0].points)
    return Answer(intent=plan.intent, start=lines[0].points[0].date, end=lines[0].points[-1].date,
                  facts=facts, lines=lines)
