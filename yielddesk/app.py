"""HTTP API: POST /api/ask runs question -> plan -> computed answer -> explanation."""

from __future__ import annotations

from datetime import date
from functools import lru_cache

import anthropic
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import llm
from .data import LABELS, SERIES, Observations, load
from .plan import Answer, PlanError, QueryPlan, run

app = FastAPI(title="YieldDesk")


@lru_cache
def observations() -> Observations:
    return load()


def messages_client() -> llm.MessagesClient:
    return llm.default_client()


def today() -> date:
    return date.today()


class Ask(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class Reply(BaseModel):
    plan: QueryPlan
    answer: Answer
    explanation: str
    grounding: llm.Grounding


@app.get("/api/meta")
def meta(obs: Observations = Depends(observations)) -> dict[str, object]:
    return {"first": obs.first, "last": obs.last, "series": {s: LABELS[s] for s in SERIES}}


@app.post("/api/ask")
def ask(body: Ask, obs: Observations = Depends(observations),
        client: llm.MessagesClient = Depends(messages_client), now: date = Depends(today)) -> Reply:
    try:
        query = llm.plan(body.question, obs, now, client)
        answer = run(query, obs)
        explanation = (answer.facts["reason"] if answer.intent == "unsupported"
                       else llm.explain(body.question, answer, client))
    except PlanError as e:
        raise HTTPException(422, str(e)) from e
    except llm.Refused as e:
        raise HTTPException(422, str(e)) from e
    except anthropic.AuthenticationError as e:
        raise HTTPException(503, "No Anthropic credentials: set ANTHROPIC_API_KEY.") from e
    except anthropic.RateLimitError as e:
        raise HTTPException(429, "Claude is rate limited; try again shortly.") from e
    except anthropic.APIConnectionError as e:
        raise HTTPException(502, "Could not reach the Claude API.") from e
    grounding = (llm.Grounding(grounded=True, unsupported_numbers=[]) if answer.intent == "unsupported"
                 else llm.check_grounding(str(explanation), answer))
    return Reply(plan=query, answer=answer, explanation=str(explanation), grounding=grounding)
