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
        name: /Understand every step from referral to visit review/i,
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
      screen.getByRole('button', { name: /Walk through one referral/i }),
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
  })

  it('switches run evidence, records contextual feedback, and opens the referral workspace', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(
      screen.getByRole('button', { name: /Walk through one referral/i }),
    )

    await user.click(
      screen.getByRole('button', {
        name: /Evaluate the seven required fields/i,
      }),
    )
    expect(screen.getByText('7 of 7 fields complete')).toBeInTheDocument()

    await user.selectOptions(
      screen.getByLabelText(/Inspect workflow run/i),
      'synthetic-exception',
    )
    expect(
      screen.getByText('6 of 7 complete; insurance missing'),
    ).toBeInTheDocument()

    await user.selectOptions(
      screen.getByLabelText(/Feedback type/i),
      'missing-context',
    )
    await user.type(
      screen.getByLabelText(/^Comment$/i),
      'Show the insurance page evidence here.',
    )
    await user.click(screen.getByRole('button', { name: /Add feedback/i }))
    expect(
      screen.getByText('Show the insurance page evidence here.'),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', {
        name: /Open extracted referral workspace/i,
      }),
    )
    expect(
      screen.getByRole('dialog', { name: /Maria Alvarez/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('tab', { name: /Monday\.com/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /DRK draft/i })).toBeInTheDocument()
    expect(
      screen.getByRole('tab', { name: /Confirmation/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('tab', { name: /Audit timeline/i }),
    ).toBeInTheDocument()
  })
})
