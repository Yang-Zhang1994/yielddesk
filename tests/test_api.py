from datetime import date

import pytest
from fastapi.testclient import TestClient

from yielddesk import app as appmod
from yielddesk.plan import QueryPlan

from .conftest import FakeMessages


@pytest.fixture
def client(obs):
    fake = FakeMessages()
    appmod.app.dependency_overrides = {
        appmod.observations: lambda: obs,
        appmod.messages_client: lambda: fake,
        appmod.today: lambda: date(2026, 11, 20),
    }
    yield TestClient(appmod.app), fake
    appmod.app.dependency_overrides = {}


def test_ask_returns_plan_answer_chart_and_grounded_explanation(client):
    http, fake = client
    fake.plans.append(QueryPlan(intent="spread", series=["10y", "2y"], start=date(2026, 10, 1), end=date(2026, 10, 9), reason=None))
    fake.texts.append("The 2s10s spread went from -10.0 bp to 2.0 bp, a 12.0 bp steepening; it was inverted on 5 days.")
    r = http.post("/api/ask", json={"question": "Did the curve un-invert in early October?"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["plan"]["intent"] == "spread"
    assert body["answer"]["facts"]["10y-2y spread change bp"] == 12.0
    assert len(body["answer"]["lines"][0]["points"]) == 7
    assert body["grounding"] == {"grounded": True, "unsupported_numbers": []}


def test_unsupported_questions_skip_the_explainer(client):
    http, fake = client
    fake.plans.append(QueryPlan(intent="unsupported", series=[], start=None, end=None, reason="This data has no US Treasury yields."))
    r = http.post("/api/ask", json={"question": "What's the US 10-year?"})
    assert r.status_code == 200
    assert r.json()["explanation"] == "This data has no US Treasury yields."
    assert [c[0] for c in fake.calls] == ["parse"]


def test_a_plan_that_cannot_run_is_a_422_with_the_reason(client):
    http, fake = client
    fake.plans.append(QueryPlan(intent="spread", series=["10y"], start=None, end=None, reason=None))
    r = http.post("/api/ask", json={"question": "10y spread?"})
    assert r.status_code == 422 and "exactly two" in r.json()["detail"]


def test_meta_reports_the_data_range(client):
    http, _ = client
    assert http.get("/api/meta").json()["first"] == "2026-10-01"
