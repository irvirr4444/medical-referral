import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from '../App'

describe('App accessibility framing', () => {
  it('opens on Overview with scenario summary; intake shows scenario board', async () => {
    const user = userEvent.setup()
    render(<App />)
    expect(screen.getByRole('navigation', { name: /Primary/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Overview$/i })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('heading', { name: /^Overview$/i })).toBeInTheDocument()
    expect(screen.getByText(/Live workflow command summary/i)).toBeInTheDocument()
    expect(
      screen.getAllByText(/36 minutes of manual intake → 8 minutes of focused review/i)
        .length,
    ).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: /1\. Referral intake/i }))
    expect(screen.getByText(/Live work queue/i)).toBeInTheDocument()
    expect(
      screen.getByRole('tab', { name: /New source document received/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /New source document received/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /2\. Handoff$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /3\. Assignment/i })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /4\. Provider selection/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /5\. Scheduling/i })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Process referral inbox/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Reset day/i })).toBeInTheDocument()
  })
})
