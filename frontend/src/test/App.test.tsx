import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from '../App'

describe('App accessibility framing', () => {
  it('opens on Overview with journey panel; intake shows scenario board only', async () => {
    const user = userEvent.setup()
    render(<App />)
    expect(screen.getByRole('navigation', { name: /Primary/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Overview$/i })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('heading', { name: /^Overview$/i })).toBeInTheDocument()
    expect(screen.getByText(/Patients requiring attention/i)).toBeInTheDocument()
    expect(
      screen.getAllByText(/36 minutes of manual intake → 8 minutes of focused review/i)
        .length,
    ).toBeGreaterThan(0)

    expect(screen.getByRole('region', { name: /Patient journey/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Review acknowledgement →/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Restart journey/i })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Choose patient/i }))
    expect(screen.getByRole('dialog', { name: /Choose a patient/i })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Maria Alvarez.*Acknowledgement prepared/i }),
    ).toHaveAttribute('aria-current', 'true')
    expect(
      screen.getByRole('button', { name: /Linda Nguyen.*Not eligible for handoff/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Robert Williams.*Private review draft prepared/i }),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Close patient list/i }))

    await user.click(screen.getByRole('button', { name: /Open Referral intake actions/i }))
    expect(screen.getByRole('button', { name: /1\. Referral intake/i })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(screen.getByRole('tab', { name: /^Action/i })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: /^Automation impact$/i })).toBeInTheDocument()
    expect(screen.getByText(/Patients requiring action/i)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: /Patient journey/i })).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /^Automation impact$/i }))
    expect(screen.getByRole('tab', { name: /^Automation impact$/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.queryByText(/Patients requiring action/i)).not.toBeInTheDocument()

    expect(screen.getByRole('button', { name: /2\. Handoff$/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /3\. Assignment/i })).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /4\. Provider selection/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /5\. Scheduling/i })).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: /^Action/i }))
    expect(screen.getByText(/Patients requiring action/i)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Process referral inbox/i }),
    ).not.toBeInTheDocument()
  })
})
