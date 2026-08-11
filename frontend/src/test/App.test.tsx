import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from '../App'

describe('automation inspection console', () => {
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
    expect(screen.queryByRole('tab', { name: /^Steps$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: /^Worklist$/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: /^History$/i })).not.toBeInTheDocument()
    expect(screen.getByLabelText(/Patient steps/i)).toBeInTheDocument()
    expect(
      screen.getByRole('navigation', { name: /Automation steps/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Receive referral in inbox/i }),
    ).toHaveAttribute('aria-current', 'step')
    expect(screen.getByLabelText(/Step updates/i)).toBeInTheDocument()
    expect(screen.getAllByText(/BUTLER, ALVA/i).length).toBeGreaterThan(0)
    expect(
      screen.queryByRole('list', { name: /Microstep run history/i }),
    ).not.toBeInTheDocument()
  })

  it('shows open Slack-style messages with Butler PDF proof on step 1', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(
      screen.getByRole('button', { name: /Inspect Referral intake/i }),
    )

    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    expect(within(stepsPanel).getByLabelText(/Step updates/i)).toBeInTheDocument()
    expect(within(stepsPanel).getAllByText(/BUTLER, ALVA/i).length).toBeGreaterThan(0)
    expect(within(stepsPanel).getAllByText(/Gonzalez, Eric/i).length).toBeGreaterThan(0)

    // Open by default — proof fields + Gmail-style attachment chip.
    expect(
      within(stepsPanel).getByLabelText(
        /Referral email identified.*BUTLER, ALVA.*Finished/i,
      ),
    ).toBeInTheDocument()
    expect(within(stepsPanel).getAllByLabelText(/Key proof/i).length).toBeGreaterThan(0)
    expect(
      within(stepsPanel).queryByRole('button', { name: /View pipeline/i }),
    ).not.toBeInTheDocument()
    expect(within(stepsPanel).queryByText(/^ATTACHMENT$/i)).not.toBeInTheDocument()

    const attachment = within(stepsPanel).getByRole('button', {
      name: /Open attachment BUTLER, ALVA demo\.pdf/i,
    })
    expect(attachment).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: /BUTLER, ALVA demo\.pdf/i })).not.toBeInTheDocument()

    await user.click(attachment)
    const pdfDialog = screen.getByRole('dialog', { name: /BUTLER, ALVA demo\.pdf/i })
    expect(pdfDialog).toBeInTheDocument()
    expect(within(pdfDialog).getByLabelText(/Referral PDF/i)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Close attachment/i }))
    expect(
      screen.queryByRole('dialog', { name: /BUTLER, ALVA demo\.pdf/i }),
    ).not.toBeInTheDocument()
  })

  it('shows extract-and-verify decision skim with expandable details', async () => {
    const user = userEvent.setup()
    render(<App />)
    await user.click(
      screen.getByRole('button', { name: /Inspect Referral intake/i }),
    )

    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Extract and verify referral details/i,
      }),
    )

    expect(
      within(stepsPanel).getAllByLabelText(/Key decision/i).length,
    ).toBeGreaterThan(0)
    expect(within(stepsPanel).getAllByText(/^Not met$/i).length).toBeGreaterThan(0)
    expect(within(stepsPanel).getAllByText(/Threshold/i).length).toBeGreaterThan(0)
    expect(within(stepsPanel).getAllByText(/Completeness/i).length).toBeGreaterThan(0)

    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Minimum identity and contact gate/i,
      }),
    ).not.toBeInTheDocument()

    expect(
      within(stepsPanel).getAllByLabelText(/Seven required fields/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(stepsPanel).getAllByText(/^Patient name$/i).length,
    ).toBeGreaterThan(0)

    const expand = within(stepsPanel).getAllByRole('button', {
      name: /Show extracted details/i,
    })[0]
    await user.click(expand)
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Seven required fields/i,
      }),
    ).not.toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Demographics/i,
      }),
    ).toBeInTheDocument()
  })

  it('keeps the step-first feed on later stages', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /5\. Scheduling/i }))
    expect(screen.getByLabelText(/Patient steps/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/Step updates/i)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Filter by status/i }),
    ).toBeInTheDocument()
    expect(screen.getAllByText('Maria Alvarez').length).toBeGreaterThan(0)
  })
})
