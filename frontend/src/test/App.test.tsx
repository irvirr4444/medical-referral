import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import App from '../App'

describe('automation inspection console', () => {
  beforeEach(() => {
    window.sessionStorage.clear()
  })

  it('opens on a concise workflow overview and enters intake operations', async () => {
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
        name: /Referral Intake & Scheduling/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /Objectives/i }),
    ).toBeInTheDocument()
    expect(screen.getByText(/New referrals/i)).toBeInTheDocument()
    expect(screen.getByText(/Patients scheduled/i)).toBeInTheDocument()
    expect(screen.getByText(/^Patients seen$/i)).toBeInTheDocument()
    expect(screen.getByText(/Wounds healed/i)).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^Today$/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByText('18')).toBeInTheDocument()
    expect(screen.getAllByText(/vs yesterday/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/\+3 \(20%\)/)).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /View patients for New referrals/i }),
    )
    const patientDialog = screen.getByRole('dialog', { name: /New referrals/i })
    expect(patientDialog).toBeInTheDocument()
    expect(within(patientDialog).getAllByRole('listitem')).toHaveLength(8)
    await user.click(
      screen.getByRole('button', { name: /Close patient list/i }),
    )

    await user.click(screen.getByRole('tab', { name: /This week/i }))
    expect(screen.getByText('82')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /Pick dates/i }))
    await user.click(screen.getByRole('button', { name: /Confirm/i }))
    expect(screen.getByText('112')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /Seven inspectable stages/i }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^Inspect /i })).toHaveLength(
      7,
    )

    await user.click(
      screen.getByRole('button', { name: /Inspect Referral intake/i }),
    )

    expect(
      screen.getByRole('button', { name: /1\. Referral intake/i }),
    ).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('tab', { name: /^Steps$/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByRole('tab', { name: /^Worklist$/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^History$/i })).toBeInTheDocument()
    expect(screen.getByLabelText(/Patient steps/i)).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: /Automation steps/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Confirm referral partner was contacted/i }),
    ).toHaveAttribute('aria-current', 'step')
    expect(
      screen.getByRole('button', { name: /Receive referral in inbox/i }),
    ).toHaveAttribute('data-status', 'done')
    expect(screen.getAllByText('Butler, Alva').length).toBeGreaterThan(0)
    expect(
      screen.queryByRole('list', { name: /Microstep run history/i }),
    ).not.toBeInTheDocument()
  })

  it('shows Butler step detail by default and opens current step from Worklist', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(
      screen.getByRole('button', { name: /Inspect Referral intake/i }),
    )

    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    expect(
      within(stepsPanel).getByRole('navigation', { name: /Automation steps/i }),
    ).toBeInTheDocument()
    expect(within(stepsPanel).getByText('Butler, Alva')).toBeInTheDocument()
    expect(
      within(stepsPanel).getByLabelText(/Confirm referral partner was contacted for this patient/i),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByText(/Referral partner contact confirmation pending/i),
    ).toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', { name: /Receive referral in inbox/i }),
    )
    expect(
      within(stepsPanel).getByText(/Referral email identified/i),
    ).toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', { name: /Patient list/i }),
    )
    const patientList = screen.getByRole('dialog', {
      name: /Patients in this stage/i,
    })
    expect(
      within(patientList).getByRole('button', { name: /Butler, Alva/i }),
    ).toHaveAttribute('aria-current', 'true')
    await user.click(
      within(patientList).getByRole('button', { name: /Close patient list/i }),
    )

    await user.click(screen.getByRole('tab', { name: /^Worklist$/i }))
    const worklist = screen.getByLabelText(/^Worklist$/i)
    expect(worklist).toBeInTheDocument()
    await user.click(within(worklist).getByText('Butler, Alva'))

    expect(screen.getByRole('tab', { name: /^Steps$/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    const returnedSteps = screen.getByLabelText(/Patient steps/i)
    expect(within(returnedSteps).getByText('Butler, Alva')).toBeInTheDocument()
    expect(
      within(returnedSteps).getByRole('button', {
        name: /Confirm referral partner was contacted/i,
      }),
    ).toHaveAttribute('aria-current', 'step')

    await user.click(screen.getByRole('tab', { name: /^History$/i }))
    const history = screen.getByLabelText(/^History$/i)
    expect(within(history).getByText(/August 10, 2026/i)).toBeInTheDocument()
    expect(within(history).getAllByText('Butler, Alva').length).toBeGreaterThan(0)
  })

  it('shows Worklist and History on later stages', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /5\. Scheduling/i }))
    expect(screen.getByRole('tab', { name: /^Steps$/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByLabelText(/Patient steps/i)).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /^Worklist$/i }))
    expect(screen.getByText(/Awaiting response/i)).toBeInTheDocument()
    expect(screen.getByText('Maria Alvarez')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /^History$/i }))
    const history = screen.getByLabelText(/^History$/i)
    expect(within(history).getAllByText('Maria Alvarez').length).toBeGreaterThan(0)
    expect(
      within(history).getAllByText(/Awaiting provider response/i).length,
    ).toBeGreaterThan(0)
  })

  it('records a human decision, advances the patient, and keeps it in history', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /3\. Assignment/i }))
    const steps = screen.getByLabelText(/Patient steps/i)
    expect(within(steps).getByText('Marcus Feldman')).toBeInTheDocument()

    await user.click(
      within(steps).getByRole('button', {
        name: /Cole Ramirez/i,
      }),
    )

    expect(
      within(steps).getByRole('button', {
        name: /^Assign Owner/i,
      }),
    ).toHaveAttribute('data-status', 'done')

    await user.click(screen.getByRole('tab', { name: /^History$/i }))
    expect(
      screen.getByText(/case-manager or marketer routing decision was recorded/i),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /2\. Handoff/i }))
    await user.click(screen.getByRole('button', { name: /3\. Assignment/i }))
    expect(
      screen.getByRole('button', { name: /^Assign Owner/i }),
    ).toHaveAttribute('data-status', 'done')
  })

  it('records an alternate provider choice in the destination fields', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /4\. Provider selection/i }))
    const steps = screen.getByLabelText(/Patient steps/i)
    await user.click(
      within(steps).getByRole('button', { name: /Dr\. Mina Patel/i }),
    )

    expect(within(steps).getAllByText('Dr. Mina Patel').length).toBeGreaterThan(1)
    expect(
      within(steps).getByRole('button', { name: /^Record Provider Selection/i }),
    ).toHaveAttribute('data-status', 'done')
  })
})
