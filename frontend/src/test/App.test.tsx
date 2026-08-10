import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from '../App'

describe('automation inspection console', () => {
  it('opens on a concise workflow overview and enters the guided intake inspector', async () => {
    const user = userEvent.setup()
    render(<App />)

    expect(
      screen.getByRole('navigation', { name: /Primary/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Overview$/i })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(
      screen.getByRole('heading', {
        name: /Referral Intake Process/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /Seven inspectable stages/i }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^Inspect /i })).toHaveLength(
      7,
    )
    expect(
      screen.queryByText(/Patients requiring attention/i),
    ).not.toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /Inspect Referral intake/i }),
    )

    expect(
      screen.getByRole('button', { name: /1\. Referral intake/i }),
    ).toHaveAttribute('aria-current', 'page')
    expect(
      screen.getByRole('heading', {
        name: /What this stage is responsible for/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: /Automation microsteps/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Discover the referral email/i }),
    ).toHaveAttribute('aria-current', 'step')
    expect(
      screen.getByRole('heading', { name: /Discover the referral email/i }),
    ).toBeInTheDocument()
    expect(document.querySelector('.automation-run-status')).toBeNull()
    expect(
      screen.queryByLabelText(/Inspect workflow run/i),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /Walk through one referral/i }),
    ).not.toBeInTheDocument()
  })

  it('shows Butler walkthrough evidence across microsteps', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(
      screen.getByRole('button', { name: /Inspect Referral intake/i }),
    )

    await user.click(
      screen.getByRole('button', {
        name: /Evaluate the seven required fields/i,
      }),
    )
    const outputPanel = screen.getByLabelText(/Produced output/i)
    expect(outputPanel).toHaveTextContent('Seven-field completeness review')
    expect(outputPanel).toHaveTextContent('Not documented')

    await user.click(
      screen.getByRole('button', {
        name: /Extract referral information/i,
      }),
    )
    expect(screen.getByLabelText(/Produced output/i)).toHaveTextContent(
      'Canonical referral extraction',
    )
    expect(
      screen.queryByRole('button', {
        name: /Open extracted referral workspace/i,
      }),
    ).not.toBeInTheDocument()
  })
})
