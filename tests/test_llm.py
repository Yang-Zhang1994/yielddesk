from datetime import date

import pytest

from yielddesk import llm
from yielddesk.plan import Answer, QueryPlan, run

from .conftest import FakeMessages

PLAN = QueryPlan(intent="change", series=["10y"], start=date(2026, 11, 2), end=date(2026, 11, 6), reason=None)


def test_plan_asks_for_a_typed_plan_with_fallbacks(obs):
    fake = FakeMessages(plans=[PLAN])
    assert llm.plan("How did the 10-year move last week?", obs, date(2026, 11, 12), fake) == PLAN
    kind, kw = fake.calls[0]
    assert kind == "parse" and kw["output_format"] is QueryPlan
    assert kw["model"] == "claude-opus-5-5"
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert "Today is 2026-11-12 (Thursday)" in kw["system"]
    assert "2026-10-01 to 2026-11-20" in kw["system"]


def test_a_refusal_is_raised_not_parsed(obs):
    with pytest.raises(llm.Refused):
        llm.plan("?", obs, date(2026, 11, 12), FakeMessages(plans=[PLAN], stop_reason="refusal"))


def test_explain_sends_the_computed_facts_and_returns_only_text(obs):
    answer = run(PLAN, obs)
    fake = FakeMessages(texts=["The 10-year rose 4.0 bp, from 3.72% to 3.76%."])
    assert llm.explain("q", answer, fake) == "The 10-year rose 4.0 bp, from 3.72% to 3.76%."
    sent = fake.calls[0][1]["messages"][0]["content"]
    assert '"10y change bp": 4.0' in sent and '"10y start %": 3.72' in sent


def answer(**facts):
    return Answer(intent="change", start=date(2026, 11, 2), end=date(2026, 11, 6), facts=facts, lines=[])


def test_grounding_accepts_numbers_from_the_facts_dates_and_tenors():
    a = answer(**{"10y start %": 3.72, "10y end %": 3.76, "10y change bp": -4.0, "trading days": 5})
    text = "From Nov 2 to 2026-11-06 the 10-year yield fell 4 bp, from 3.72% to 3.76%, over 5 trading days in 2026; 2s10s too."
    assert llm.check_grounding(text, a) == llm.Grounding(grounded=True, unsupported_numbers=[])


def test_grounding_flags_a_number_the_model_made_up():
    a = answer(**{"10y change bp": 4.0})
    g = llm.check_grounding("The 10-year rose 4 bp and is likely to reach 4.10% by March.", a)
    assert not g.grounded and g.unsupported_numbers == ["4.10"]
