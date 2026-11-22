from datetime import date

from evals.run_eval import score
from yielddesk.plan import QueryPlan


def p(**kw):
    return QueryPlan(**{"intent": "change", "series": ["10y"], "start": None, "end": None, "reason": None, **kw})


def test_exact_match_needs_intent_series_and_dates():
    exp = {"intent": "change", "series": ["2y", "10y"], "start": "2026-11-16", "end": "2026-11-20"}
    assert score(p(series=["10y", "2y"], start=date(2026, 11, 16), end=date(2026, 11, 20)), exp) == \
        {"intent": True, "series": True, "dates": True}
    assert score(p(series=["10y", "2y"], start=date(2026, 11, 13), end=date(2026, 11, 20)), exp)["dates"] is False


def test_spread_order_matters():
    exp = {"intent": "spread", "series": ["10y", "2y"], "start": None, "end": None}
    assert score(p(intent="spread", series=["2y", "10y"]), exp)["series"] is False


def test_unsupported_only_checks_the_intent():
    exp = {"intent": "unsupported", "series": [], "start": None, "end": None}
    assert all(score(p(intent="unsupported", series=[], reason="no"), exp).values())
