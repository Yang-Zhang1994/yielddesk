import { useState, type FormEvent } from 'react'
import { ask } from './api'
import { Chart } from './components/Chart'
import type { Reply } from './types'

const EXAMPLES = [
  'How much did the 10-year move this week?',
  'Is the curve steepening this month?',
  'What was the high and low for the 2-year this year?',
  "Where is the Bank of Canada's policy rate today?",
]

const INTENT_TEXT: Record<string, string> = {
  latest: 'Latest value', change: 'Change over a period', spread: 'Spread between two series',
  range: 'High, low and average', unsupported: 'Not answerable from this data',
}

export default function App() {
  const [question, setQuestion] = useState('')
  const [reply, setReply] = useState<Reply | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(q: string, e?: FormEvent) {
    e?.preventDefault()
    if (q.trim().length < 3) return
    setQuestion(q)
    setBusy(true)
    setError(null)
    try {
      setReply(await ask(q))
    } catch (err) {
      setReply(null)
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const { plan, answer } = reply ?? {}
  return (
    <main>
      <h1>YieldDesk</h1>
      <p className="sub">Ask about Government of Canada bond yields. Claude turns your question into a query; the numbers come from Bank of Canada data, computed in code.</p>

      <form onSubmit={(e) => submit(question, e)}>
        <input aria-label="Question" value={question} onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. How did 2s10s move last month?" />
        <button disabled={busy}>{busy ? 'Thinking…' : 'Ask'}</button>
      </form>
      <div className="examples">
        {EXAMPLES.map((q) => <button key={q} type="button" className="chip" onClick={() => submit(q)}>{q}</button>)}
      </div>

      {error && <p role="alert" className="error">{error}</p>}

      {reply && plan && answer && (
        <section>
          <p className="explanation">{reply.explanation}</p>
          {!reply.grounding.grounded && (
            <p role="alert" className="warn">
              Check this answer: {reply.grounding.unsupported_numbers.join(', ')} {reply.grounding.unsupported_numbers.length > 1 ? 'are' : 'is'} not in the computed data.
            </p>
          )}
          {answer.lines.length > 0 && <Chart lines={answer.lines} unit={answer.intent === 'spread' ? 'bp' : '%'} />}

          <details open>
            <summary>How I read your question</summary>
            <dl className="plan">
              <dt>Query</dt><dd>{INTENT_TEXT[plan.intent]}</dd>
              {plan.series.length > 0 && <><dt>Series</dt><dd>{plan.series.join(', ')}</dd></>}
              {answer.start && <><dt>Period</dt><dd>{answer.start} to {answer.end}</dd></>}
            </dl>
            {answer.intent !== 'unsupported' && (
              <table>
                <tbody>
                  {Object.entries(answer.facts).map(([k, v]) => <tr key={k}><th>{k}</th><td>{String(v)}</td></tr>)}
                </tbody>
              </table>
            )}
          </details>
        </section>
      )}
      <footer>Data: Bank of Canada Valet API (benchmark bond yields, target overnight rate). Not investment advice.</footer>
    </main>
  )
}
