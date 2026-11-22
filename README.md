# YieldDesk

Ask about Government of Canada bond yields in plain English — "How much did the 10-year move this
week?", "Is the curve steepening this month?" — and get an answer, a chart, and the exact query that
produced it.

Claude (Opus 5.5) only **translates** the question into a typed query plan. Python code computes the
answer from Bank of Canada data, and Claude then explains the computed numbers. A check flags any
number in the explanation that the data does not contain.

```
question ──► Claude: QueryPlan (structured output, pydantic)
                │  intent: latest | change | spread | range | unsupported
                │  series: 2y 3y 5y 7y 10y long real_return policy_rate
                │  start, end
                ▼
             plan.run(): deterministic code over Bank of Canada Valet data ──► facts + chart lines
                ▼
             Claude: 2–3 sentence explanation of the facts
                ▼
             check_grounding(): every number must be a computed fact (dates and tenors aside)
```

## Design decisions

| Problem | What YieldDesk does |
|---|---|
| LLMs get arithmetic and data wrong | Claude never sees the price series and never computes. It emits a `QueryPlan`; code does the math (basis points, spreads on days both series trade, highs and lows with their dates) |
| Free-text output is hard to trust | The plan is a pydantic model sent as the structured-output schema, so the response always parses. A plan that parses but can't run (a spread with one series, a period before the data) is a 422 with the reason |
| "Last week" means different things to different people | The planner prompt fixes the conventions (this week = Monday to today, last month = the whole previous month, YTD = Jan 1, no period = past 30 days) so plans are checkable |
| Hallucinated numbers in the explanation | `check_grounding` extracts every number from the explanation and requires it to match a computed fact; the UI shows a warning naming any that don't |
| Questions the data can't answer | Forecasts, US yields, mortgages, stocks and dates before 2020 come back as `unsupported` with a reason, and the explainer is skipped |
| Safety classifier declines | Requests use the server-side fallback (`fallbacks: "default"`); a final refusal is surfaced as an error rather than parsed |

## Evaluation

`evals/questions.jsonl` holds 30 questions (latest, change, spread, range and unsupported, across
relative and named periods) with the exact plan each should produce for a fixed "today" of
2026-11-20. `python -m evals.run_eval` scores intent, series and dates separately and checks that
the explanations of correct plans are grounded.

**Not yet run against the live API** (it needs an Anthropic API key, about 60 requests). The scorer
itself is unit-tested.

## Run it

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
echo 'ANTHROPIC_API_KEY=...' > .env          # git-ignored
.venv/bin/uvicorn yielddesk.app:app --reload  # API on :8000; downloads and caches the data on first use

cd web && npm install && npm run dev           # http://localhost:5173
```

## Tests

```bash
.venv/bin/pytest -q    # 25 tests; Claude is replaced by a fake, so no key or network needed
.venv/bin/mypy         # strict
cd web && npx vitest run   # 6 tests
```

| Suite | What it checks |
|---|---|
| `test_plan.py` | Changes in bp, weekend starts snapping to the next trading day, latest values with their dates, range high/low/average with dates, spreads and inverted-day counts, the 30-day default, clamping to the last data day, and five plans that must fail with a readable reason |
| `test_llm.py` | The planner requests the `QueryPlan` schema on Claude Opus 5.5 with fallbacks and the right dates in the prompt; refusals raise; the explainer gets the computed facts; grounding accepts facts, dates and tenors and flags an invented forecast |
| `test_api.py` | The full ask flow, unsupported questions skipping the explainer, 422s for plans that can't run |
| `test_eval_scoring.py` | Exact-match scoring, spread order, unsupported questions |
| `App.test.tsx`, `Chart.test.tsx` | Explanation, chart and plan shown; ungrounded numbers flagged; API errors shown; spreads drawn with a zero line |

## Data

[Bank of Canada Valet API](https://www.bankofcanada.ca/valet/docs): benchmark bond yields (2, 3, 5,
7, 10-year, long-term, real return) and the target for the overnight rate, from 2020. Not investment
advice.
