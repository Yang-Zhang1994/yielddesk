"""Claude turns a question into a QueryPlan, then explains the computed Answer in plain English."""

from __future__ import annotations

import json
import os
import re
from datetime import date
from typing import Any, Protocol, cast

import anthropic
from pydantic import BaseModel

from .data import LABELS, SERIES, Observations
from .plan import Answer, QueryPlan

MODEL = "claude-opus-5-5"
# If a safety classifier declines, the API retries on a fallback model it picks (beta).
FALLBACK = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}


class Refused(RuntimeError):
    pass


class MessagesClient(Protocol):
    """The slice of anthropic.Anthropic().beta.messages this module uses; tests pass a fake."""

    def parse(self, **kwargs: Any) -> Any: ...
    def create(self, **kwargs: Any) -> Any: ...


def load_dotenv(path: str = ".env") -> None:
    """Read KEY=value lines from a git-ignored .env file without overriding the real environment."""
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def default_client() -> MessagesClient:
    load_dotenv()
    # The SDK's overloaded signatures are stricter than this Protocol; the calls below match them.
    return cast(MessagesClient, anthropic.Anthropic().beta.messages)


def planner_system(obs: Observations, today: date) -> str:
    series = "\n".join(f"- {s}: {LABELS[s]}" for s in SERIES)
    return f"""You translate questions about Canadian interest rates into a query plan. You never answer
the question yourself; code runs the plan on Bank of Canada data.

Today is {today.isoformat()} ({today:%A}). Data covers {obs.first.isoformat()} to {obs.last.isoformat()},
business days only, in percent.

Series:
{series}

Date conventions (be exact, the plan is checked against them):
- "this week": Monday of this week to today. "last week": Monday to Friday of the previous week.
- "this month" / "month to date": the 1st of this month to today. "last month": the whole previous month.
- "this year" / "year to date" / "YTD": January 1 of this year to today. "last year": that calendar year.
- "past N days/weeks/months/years": today minus that period, to today.
- A named month or year with no other detail means the whole month or year.
- With no period given, change, spread and range use the past 30 days.
- latest uses null start and end.

Choosing an intent:
- "the curve", "2s10s", "steepening", "inverted" mean spread with [10y, 2y] unless other tenors are named.
- "5s30s" is [long, 5y]. A spread lists the longer tenor first.
- "rates" or "yields" with no tenor means 10y; "the Bank of Canada rate" or "overnight rate" means policy_rate.
- Use unsupported (with a short reason) for anything this data cannot answer: other countries, stocks,
  corporate bonds, mortgages, forecasts or predictions, and dates before the data starts."""


def plan(question: str, obs: Observations, today: date, client: MessagesClient | None = None) -> QueryPlan:
    response = (client or default_client()).parse(
        model=MODEL,
        max_tokens=4000,
        output_config={"effort": "low"},
        output_format=QueryPlan,
        system=planner_system(obs, today),
        messages=[{"role": "user", "content": question}],
        **FALLBACK,
    )
    if response.stop_reason == "refusal":
        raise Refused("Claude declined to plan this question.")
    parsed: QueryPlan = response.parsed_output
    return parsed


EXPLAINER_SYSTEM = """You explain results about Canadian government bond yields to a colleague on a
bond desk. Write two or three plain sentences. Use only the numbers in the facts you are given, written
the same way (you may drop a minus sign when you say "fell"). Say bp for basis points. Do not predict,
give advice, or add numbers, causes or context that are not in the facts."""


def explain(question: str, answer: Answer, client: MessagesClient | None = None) -> str:
    facts = json.dumps({"intent": answer.intent, "start": str(answer.start), "end": str(answer.end), **answer.facts})
    response = (client or default_client()).create(
        model=MODEL,
        max_tokens=2000,
        output_config={"effort": "low"},
        system=EXPLAINER_SYSTEM,
        messages=[{"role": "user", "content": f"Question: {question}\nFacts: {facts}"}],
        **FALLBACK,
    )
    if response.stop_reason == "refusal":
        raise Refused("Claude declined to explain this result.")
    return "".join(b.text for b in response.content if b.type == "text").strip()


class Grounding(BaseModel):
    grounded: bool
    unsupported_numbers: list[str]


_DATE = re.compile(r"\d{4}-\d{2}-\d{2}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}(?:, \d{4})?|\b\d{1,2} (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*(?: \d{4})?")
_TENOR = re.compile(r"\b\d{1,2}(?:-| )?(?:year|yr|y)\b|\b\d{1,2}s\d{1,2}s\b", re.I)
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def check_grounding(text: str, answer: Answer) -> Grounding:
    """Every number in the explanation must be one of the computed facts (dates and tenors aside)."""
    allowed: set[float] = set()
    for value in answer.facts.values():
        if isinstance(value, (int, float)):
            allowed |= {round(abs(value), 2)}
    for d in (answer.start, answer.end):
        if d:
            allowed |= {d.year}
    stripped = _TENOR.sub(" ", _DATE.sub(" ", text))
    bad = [n for n in _NUMBER.findall(stripped) if round(abs(float(n)), 2) not in allowed]
    return Grounding(grounded=not bad, unsupported_numbers=bad)
