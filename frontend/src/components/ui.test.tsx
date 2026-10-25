import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { KpiCard, Loadable } from './ui'

describe('KpiCard', () => {
  it('shows label, value and plain-language note', () => {
    render(<KpiCard label="Bias" value="+1,042 MW" note="Forecast was too high by 1,042 MW on average" />)
    expect(screen.getByText('Bias')).toBeInTheDocument()
    expect(screen.getByText('+1,042 MW')).toBeInTheDocument()
    expect(screen.getByText(/too high by 1,042 MW/)).toBeInTheDocument()
  })
})

describe('Loadable', () => {
  it('shows a loading state', () => {
    render(<Loadable state={{ status: 'loading' }}>{() => 'data'}</Loadable>)
    expect(screen.getByRole('status')).toHaveTextContent('Loading')
  })

  it('shows the error message and retries', async () => {
    const retry = vi.fn()
    render(<Loadable state={{ status: 'error', error: '422 bad date' }} retry={retry}>{() => 'data'}</Loadable>)
    expect(screen.getByRole('alert')).toHaveTextContent('422 bad date')
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(retry).toHaveBeenCalledOnce()
  })

  it('shows the empty state when data is empty', () => {
    render(
      <Loadable state={{ status: 'ok', data: [] as number[] }} isEmpty={(d) => d.length === 0}>
        {() => 'data'}
      </Loadable>,
    )
    expect(screen.getByText('No data for this selection.')).toBeInTheDocument()
  })

  it('renders children with the data', () => {
    render(<Loadable state={{ status: 'ok', data: 7 }}>{(n) => `value ${n}`}</Loadable>)
    expect(screen.getByText('value 7')).toBeInTheDocument()
  })
})
