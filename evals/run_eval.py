"""Score the planner against evals/questions.jsonl, then check that explanations stay grounded.

Calls the Claude API (about 2 requests per question at low effort), so it needs credentials and
costs money. Usage: python -m evals.run_eval [--limit N]
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from yielddesk import llm
from yielddesk.data import load
from yielddesk.plan import PlanError, QueryPlan, run

HERE = Path(__file__).parent


def score(plan: QueryPlan, expected: dict[str, object]) -> dict[str, bool]:
    got = {"intent": plan.intent, "series": plan.series,
           "start": plan.start and plan.start.isoformat(), "end": plan.end and plan.end.isoformat()}
    if expected["intent"] == "unsupported":
        return {"intent": got["intent"] == "unsupported", "series": True, "dates": True}
    same_series = (got["series"] == expected["series"] if expected["intent"] == "spread"
                   else sorted(got["series"]) == sorted(expected["series"]))  # type: ignore[type-var]
    return {"intent": got["intent"] == expected["intent"], "series": same_series,
            "dates": (got["start"], got["end"]) == (expected["start"], expected["end"])}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cases = [json.loads(line) for line in (HERE / "questions.jsonl").read_text().splitlines()][: args.limit]
    obs = load()
    rows, client = [], llm.default_client()
    for case in cases:
        plan = llm.plan(case["question"], obs, date.fromisoformat(case["today"]), client)
        s = score(plan, case["expected"])
        grounded = None
        if all(s.values()) and plan.intent != "unsupported":
            try:
                answer = run(plan, obs)
                grounded = llm.check_grounding(llm.explain(case["question"], answer, client), answer).grounded
            except PlanError:
                grounded = None
        rows.append({"question": case["question"], **s, "exact": all(s.values()), "grounded": grounded,
                     "plan": plan.model_dump(mode="json")})
        print(("PASS" if all(s.values()) else "FAIL"), case["question"], "" if all(s.values()) else plan.model_dump(mode="json"))
    n = len(rows)
    explained = [r for r in rows if r["grounded"] is not None]
    summary = {
        "questions": n,
        "exact plan": sum(r["exact"] for r in rows) / n,
        **{k: sum(r[k] for r in rows) / n for k in ("intent", "series", "dates")},
        "explanations grounded": (sum(r["grounded"] for r in explained) / len(explained)) if explained else None,
    }
    print(json.dumps(summary, indent=2))
    (HERE / "results.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
