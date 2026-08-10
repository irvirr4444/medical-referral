import { render, screen, within } from '@testing-library/react'
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
    expect(
      screen.queryByText(/Sample patients for today/i),
    ).not.toBeInTheDocument()
    await user.type(screen.getByRole('searchbox', { name: /Search patients/i }), 'zzzz')
    expect(screen.getByText(/No patients match your search/i)).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: /Close patient list/i }),
    )
    expect(
      screen.queryByRole('dialog', { name: /New referrals/i }),
    ).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /This week/i }))
    expect(screen.getByRole('tab', { name: /This week/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByText('82')).toBeInTheDocument()
    expect(screen.getAllByText(/vs last week/i).length).toBeGreaterThan(0)

    expect(screen.queryByRole('tab', { name: /Last week/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: /Last month/i })).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /Pick dates/i }))
    expect(
      screen.getByRole('dialog', { name: /Select reporting period/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^Day$/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /^Month$/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByRole('tab', { name: /^Year$/i })).toBeInTheDocument()
    expect(
      screen.getByRole('tab', { name: /Custom range/i }),
    ).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Confirm/i }))
    expect(screen.getByText('112')).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Pick dates/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(
      screen.queryByText(/How to use this console/i),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('heading', {
        name: /Inspect, verify, and improve the workflow/i,
      }),
    ).not.toBeInTheDocument()
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
        name: /1\. Referral intake/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: /Automation steps/i }),
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

  it('shows scrollable patient run history for lifecycle microsteps', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /5\. Scheduling/i }))

    const history = screen.getByRole('list', {
      name: /Microstep run history/i,
    })
    expect(history).toBeInTheDocument()
    expect(
      screen.queryByText(/Maria Alvarez - scheduling walkthrough/i),
    ).not.toBeInTheDocument()
    expect(
      within(history).getByText('Maria Alvarez', { selector: 'strong' }),
    ).toBeInTheDocument()
    expect(
      within(history).getByText('Patricia Johnson', { selector: 'strong' }),
    ).toBeInTheDocument()
    expect(
      within(history).getByText('James Carter', { selector: 'strong' }),
    ).toBeInTheDocument()
    expect(within(history).getAllByText(/Input received/i)).toHaveLength(3)
    expect(within(history).getAllByText(/Output produced/i)).toHaveLength(3)

    await user.click(
      screen.getByRole('button', { name: /Classify scheduling outcome/i }),
    )
    const updatedHistory = screen.getByRole('list', {
      name: /Microstep run history/i,
    })
    expect(
      within(updatedHistory).getAllByText(/Confirmed appointment/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(updatedHistory).getByText(/Scheduling exception for Carla/i),
    ).toBeInTheDocument()
  })
})
