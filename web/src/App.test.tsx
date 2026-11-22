import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'
import type { Reply } from './types'

const spread: Reply = {
  plan: { intent: 'spread', series: ['10y', '2y'], start: '2026-11-01', end: '2026-11-20', reason: null },
  answer: {
    intent: 'spread', start: '2026-11-02', end: '2026-11-19',
    facts: { '10y-2y spread start bp': 48, '10y-2y spread end bp': 51, '10y-2y spread change bp': 3, 'trading days': 14 },
    lines: [{ series: '10y', label: '10-year minus 2-year (bp)', points: [{ date: '2026-11-02', value: 48 }, { date: '2026-11-19', value: 51 }] }],
  },
  explanation: 'The 2s10s spread widened 3 bp, from 48 bp to 51 bp.',
  grounding: { grounded: true, unsupported_numbers: [] },
}

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body })
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => vi.unstubAllGlobals())

test('an example question shows the explanation, chart and how it was read', async () => {
  const fetch = mockFetch(200, spread)
  render(<App />)
  fireEvent.click(screen.getByText('Is the curve steepening this month?'))
  expect(await screen.findByText(/widened 3 bp/)).toBeInTheDocument()
  expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ question: 'Is the curve steepening this month?' })
  expect(screen.getAllByTestId('series-line')).toHaveLength(1)
  expect(screen.getByText('basis points')).toBeInTheDocument()
  expect(screen.getByText('Spread between two series')).toBeInTheDocument()
  expect(screen.getByText('2026-11-02 to 2026-11-19')).toBeInTheDocument()
  expect(screen.queryByText(/Check this answer/)).not.toBeInTheDocument()
})

test('numbers the data does not support are flagged', async () => {
  mockFetch(200, { ...spread, explanation: 'Widened 3 bp; expect 60 bp soon.', grounding: { grounded: false, unsupported_numbers: ['60'] } })
  render(<App />)
  fireEvent.change(screen.getByLabelText('Question'), { target: { value: 'curve this month?' } })
  fireEvent.click(screen.getByText('Ask'))
  expect(await screen.findByText(/Check this answer: 60 is not in the computed data/)).toBeInTheDocument()
})

test('a question the API cannot run shows its reason', async () => {
  mockFetch(422, { detail: 'A spread needs exactly two series.' })
  render(<App />)
  fireEvent.click(screen.getByText('Is the curve steepening this month?'))
  expect(await screen.findByRole('alert')).toHaveTextContent('A spread needs exactly two series.')
})
