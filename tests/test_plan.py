from datetime import date

import pytest

from yielddesk.plan import PlanError, QueryPlan, run


def plan(**kw):
    return QueryPlan(**{"intent": "change", "series": ["10y"], "start": None, "end": None, "reason": None, **kw})


def test_change_in_basis_points(obs):
    a = run(plan(start=date(2026, 11, 2), end=date(2026, 11, 6)), obs)
    assert a.facts["10y start %"] == 3.72 and a.facts["10y end %"] == 3.76
    assert a.facts["10y change bp"] == 4.0
    assert a.facts["trading days"] == 5


def test_a_weekend_start_snaps_to_the_next_trading_day(obs):
    a = run(plan(start=date(2026, 11, 1), end=date(2026, 11, 6)), obs)  # Nov 1 is a Sunday
    assert a.start == date(2026, 11, 2)


def test_latest_reports_the_last_value_and_its_date(obs):
    a = run(plan(intent="latest", series=["10y", "policy_rate"]), obs)
    assert a.facts == {"10y %": 3.86, "10y as of": "2026-11-20", "policy_rate %": 2.75,
                       "policy_rate as of": "2026-11-20"}


def test_range_finds_high_low_and_average(obs):
    a = run(plan(intent="range", start=date(2026, 10, 1), end=date(2026, 10, 31)), obs)
    assert a.facts["10y high %"] == 4.20 and a.facts["10y high on"] == "2026-10-15"
    assert a.facts["10y low %"] == 3.50 and a.facts["10y low on"] == "2026-10-01"


def test_spread_is_long_minus_short_in_bp_and_counts_inverted_days(obs):
    a = run(plan(intent="spread", series=["10y", "2y"], start=date(2026, 10, 1), end=date(2026, 10, 9)), obs)
    assert a.facts["10y-2y spread start bp"] == -10.0
    assert a.facts["10y-2y spread end bp"] == 2.0
    assert a.facts["10y-2y spread change bp"] == 12.0
    assert a.facts["10y-2y inverted days"] == 5  # 7 trading days: -10, -8, -6, -4, -2 bp, then 0, 2
    assert a.lines[0].points[0].value == -10.0


def test_no_period_means_the_past_30_days(obs):
    a = run(plan(), obs)
    assert a.end == date(2026, 11, 20) and a.start == date(2026, 10, 21)


def test_end_past_the_data_is_clamped_to_the_last_day(obs):
    assert run(plan(start=date(2026, 11, 16), end=date(2026, 12, 31)), obs).end == date(2026, 11, 20)


@pytest.mark.parametrize("bad, message", [
    (dict(intent="spread", series=["10y"]), "exactly two"),
    (dict(series=[]), "no series"),
    (dict(start=date(2026, 11, 10), end=date(2026, 11, 1)), "after it ends"),
    (dict(start=date(2019, 1, 1), end=date(2019, 2, 1)), "Data starts"),
    (dict(series=["7y"], start=date(2026, 11, 2), end=date(2026, 11, 6)), "Not enough 7-year data"),
])
def test_plans_that_cannot_run_say_why(obs, bad, message):
    with pytest.raises(PlanError, match=message):
        run(plan(**bad), obs)


def test_unsupported_passes_the_reason_through(obs):
    a = run(plan(intent="unsupported", series=[], reason="No US Treasury data."), obs)
    assert a.facts == {"reason": "No US Treasury data."} and a.lines == []
