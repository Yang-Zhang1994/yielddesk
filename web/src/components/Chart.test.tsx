import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { Chart } from './Chart'

const line = (series: string, values: number[]) => ({
  series, label: series, points: values.map((value, i) => ({ date: `2026-11-0${i + 1}`, value })),
})

test('draws one line per series across the full date range', () => {
  const { container } = render(<Chart unit="%" lines={[line('2y', [3.3, 3.2, 3.1]), line('10y', [3.8, 3.85, 3.9])]} />)
  expect(screen.getAllByTestId('series-line')).toHaveLength(2)
  expect(container.querySelector('.zero')).toBeNull()
  expect(screen.getByText('2026-11-01')).toBeInTheDocument()
  expect(screen.getByText('2026-11-03')).toBeInTheDocument()
})

test('spreads include zero so an inversion is visible', () => {
  const { container } = render(<Chart unit="bp" lines={[line('10y', [20, 35, 40])]} />)
  expect(container.querySelector('.zero')).not.toBeNull()
  expect(screen.getByText('0')).toBeInTheDocument()
})

test('a single point draws nothing', () => {
  const { container } = render(<Chart unit="%" lines={[line('10y', [3.8])]} />)
  expect(container.firstChild).toBeNull()
})
