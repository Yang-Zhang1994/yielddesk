export type Intent = 'latest' | 'change' | 'spread' | 'range' | 'unsupported'

export interface QueryPlan {
  intent: Intent
  series: string[]
  start: string | null
  end: string | null
  reason: string | null
}

export interface Line {
  series: string
  label: string
  points: { date: string; value: number }[]
}

export interface Answer {
  intent: Intent
  start: string | null
  end: string | null
  facts: Record<string, number | string>
  lines: Line[]
}

export interface Reply {
  plan: QueryPlan
  answer: Answer
  explanation: string
  grounding: { grounded: boolean; unsupported_numbers: string[] }
}
