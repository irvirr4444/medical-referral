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

  it('lets an operator change and confirm the suggested case manager', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /2\. Assignment/i }))
    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    await user.click(
      within(stepsPanel).getByRole('button', { name: /Assign Case Manager/i }),
    )

    expect(
      within(stepsPanel).getAllByText(/AI recommendation/i).length,
    ).toBeGreaterThan(0)

    const managerSelect = within(stepsPanel)
      .getAllByLabelText(/Assigned case manager/i)
      .find((select) => !select.hasAttribute('disabled'))!
    await user.selectOptions(managerSelect, 'ndelpelicano@westcoastwound.com')
    expect(managerSelect).toHaveValue('ndelpelicano@westcoastwound.com')

    await user.click(
      within(stepsPanel).getAllByRole('button', {
        name: /^Confirm$/i,
      })[0],
    )
    expect(
      within(stepsPanel).getByText(/^Assigned$/i),
    ).toBeInTheDocument()

    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Notify Case Manager/i,
      }),
    ).not.toBeInTheDocument()
  })

  it('shows case-manager notifications as email messages', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /3\. Handoff/i }))
    const stepsPanel = screen.getByLabelText(/Patient steps/i)

    expect(
      within(stepsPanel).getByRole('button', {
        name: /Notify Case Manager/i,
      }),
    ).toHaveAttribute('aria-current', 'step')
    expect(
      within(stepsPanel).getAllByLabelText(
        /Patient data shared with case manager/i,
      ).length,
    ).toBeGreaterThan(0)
    expect(
      within(stepsPanel).getAllByText(/^Sent to$/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(stepsPanel).getAllByText(/^Subject$/i).length,
    ).toBeGreaterThan(0)

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Create Monday\.com Record/i,
      }),
    )
    expect(
      within(stepsPanel).getAllByText(/^Monday\.com record created$/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(stepsPanel).getAllByLabelText(/Monday\.com record details/i).length,
    ).toBe(6)

    await user.click(
      within(stepsPanel).getByRole('button', { name: /Prepare DRK Chart/i }),
    )
    expect(
      within(stepsPanel).getAllByLabelText(/DRK chart draft details/i).length,
    ).toBe(6)
  })

  it('combines provider discovery and selection into one confirmation step', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /4\. Provider selection/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)

    expect(
      within(stepsPanel).getByRole('button', { name: /^Select Provider$/i }),
    ).toHaveAttribute('aria-current', 'step')
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Find Eligible Providers/i,
      }),
    ).not.toBeInTheDocument()

    const providerSelect =
      within(stepsPanel).getAllByLabelText(/Selected provider/i)[0]
    const alternateProviderId = (
      providerSelect.querySelectorAll('option')[1] as HTMLOptionElement
    ).value
    await user.selectOptions(providerSelect, alternateProviderId)
    expect(providerSelect).toHaveValue(alternateProviderId)
    expect(
      Array.from(providerSelect.querySelectorAll('option')).every((option) =>
        option.textContent?.includes('Los Angeles'),
      ),
    ).toBe(true)
    expect(
      within(stepsPanel).getAllByText(/^Los Angeles, CA 90\d{3}$/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(stepsPanel).getByText(/Patient sent for review to Nicole/i),
    ).toBeInTheDocument()
    await user.click(
      within(stepsPanel).getAllByRole('button', { name: /^Confirm$/i })[0],
    )
    expect(within(stepsPanel).getByText(/^Selected$/i)).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Confirm Provider Availability, new update/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Confirm Provider Availability/i,
      }),
    )
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Confirm Provider Availability, new update/i,
      }),
    ).not.toBeInTheDocument()
    expect(within(stepsPanel).getByText(/^Unread$/i)).toBeInTheDocument()

    const availabilityPanel = within(stepsPanel)
      .getAllByLabelText(/Provider availability response/i)
      .find((panel) =>
        within(panel).queryByRole('button', { name: /Provider confirmed/i }),
      )!
    expect(
      within(availabilityPanel).getByText(/Waiting for provider/i),
    ).toBeInTheDocument()
    expect(within(availabilityPanel).getByText('47 minutes')).toBeInTheDocument()

    await user.click(
      within(availabilityPanel).getByRole('button', {
        name: /Provider confirmed/i,
      }),
    )
    expect(
      within(availabilityPanel.closest('article')!).getByText(
        /confirmed availability/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(availabilityPanel).getByText(
        /Monday\.com and DRK ready to update with the selected provider/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(availabilityPanel).queryByRole('button', {
        name: /No response — place manually/i,
      }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /4\. Provider selection/i }),
    ).toHaveAttribute('aria-current', 'page')
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Update Monday\.com and DRK, new update/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', {
        name: /5\. Scheduling, new update/i,
      }),
    ).not.toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Update Monday\.com and DRK/i,
      }),
    )
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Update Monday\.com and DRK, new update/i,
      }),
    ).not.toBeInTheDocument()
    expect(within(stepsPanel).getByText(/^Unread$/i)).toBeInTheDocument()
    expect(
      within(stepsPanel).getAllByText(/Monday\.com and DRK updated with/i)
        .length,
    ).toBeGreaterThan(0)
    expect(
      within(stepsPanel).getAllByLabelText(/Monday\.com record details/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(stepsPanel).getAllByLabelText(/DRK chart draft details/i).length,
    ).toBeGreaterThan(0)
    expect(within(stepsPanel).getAllByText(/^Assigned provider$/i).length).toBeGreaterThan(0)
    expect(
      screen.getByRole('button', {
        name: /5\. Scheduling, new update/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', {
        name: /5\. Scheduling, new update/i,
      }),
    )
    expect(
      screen.queryByRole('button', {
        name: /5\. Scheduling, new update/i,
      }),
    ).not.toBeInTheDocument()
    const schedulingPanel = screen.getByLabelText(/Patient steps/i)
    expect(within(schedulingPanel).getByText(/^Unread$/i)).toBeInTheDocument()
    expect(
      within(schedulingPanel).getAllByText(/Referral sent to/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(schedulingPanel).getAllByLabelText(/Patient referral details/i)
        .length,
    ).toBeGreaterThan(0)
    expect(
      within(schedulingPanel).getAllByText(
        /DOB \d{4}-\d{2}-\d{2} · Los Angeles, CA \d{5}/i,
      ).length,
    ).toBeGreaterThan(0)
    expect(
      within(schedulingPanel).getByRole('button', {
        name: /Open attachment EC - REFERRAL FORM\.pdf/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /4\. Provider selection/i }),
    )
    await user.click(screen.getByRole('button', { name: /5\. Scheduling/i }))
    expect(
      within(screen.getByLabelText(/Patient steps/i)).queryByText(/^Unread$/i),
    ).not.toBeInTheDocument()
  })

  it('requires completed manual placement before notifying scheduling', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /4\. Provider selection/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    await user.click(
      within(stepsPanel).getAllByRole('button', { name: /^Confirm$/i })[0],
    )
    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Confirm Provider Availability/i,
      }),
    )

    const availabilityPanel = within(stepsPanel)
      .getAllByLabelText(/Provider availability response/i)
      .find((panel) =>
        within(panel).queryByRole('button', {
          name: /No response — place manually/i,
        }),
      )!
    await user.click(
      within(availabilityPanel).getByRole('button', {
        name: /No response — place manually/i,
      }),
    )
    expect(
      within(availabilityPanel.closest('article')!).getByText(
        /did not respond · CM placement needed/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(availabilityPanel).queryByRole('button', {
        name: /Provider confirmed/i,
      }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', {
        name: /5\. Scheduling, new update/i,
      }),
    ).not.toBeInTheDocument()

    await user.click(
      within(availabilityPanel).getByRole('button', {
        name: /Placement completed/i,
      }),
    )
    expect(
      within(availabilityPanel.closest('article')!).getByText(
        /Cho placed manually/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Update Monday\.com and DRK, new update/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', {
        name: /5\. Scheduling, new update/i,
      }),
    ).not.toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Update Monday\.com and DRK/i,
      }),
    )
    expect(
      screen.getByRole('button', {
        name: /5\. Scheduling, new update/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', {
        name: /5\. Scheduling, new update/i,
      }),
    )
    expect(
      within(screen.getByLabelText(/Patient steps/i)).getAllByText(
        /Referral ready to send/i,
      ).length,
    ).toBeGreaterThan(0)
  })

  it('does not notify scheduling after a discharge', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /4\. Provider selection/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    const reviewArticle = within(stepsPanel)
      .getByText(/Patient sent for review to Nicole/i)
      .closest('article')!
    await user.click(
      within(reviewArticle).getByRole('button', { name: /^Discharge$/i }),
    )
    expect(
      within(reviewArticle).getByText(/Patient discharged after Nicole review/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', {
        name: /5\. Scheduling, new update/i,
      }),
    ).not.toBeInTheDocument()
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

  it('shows patient and provider details on fixture referral rows', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /5\. Scheduling/i }))
    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /^Send Referral to Provider$/i,
      }),
    )

    const thomasRow = within(stepsPanel)
      .getAllByRole('article')
      .find((article) =>
        within(article).queryByText(
          /DOB 1955-11-30 · Los Angeles, CA 90027 · \(951\) 555-0143/i,
        ),
      )!
    expect(thomasRow).toBeTruthy()
    expect(
      within(thomasRow).getByText(/Referral sent to Charles Cho/i),
    ).toBeInTheDocument()
    expect(within(thomasRow).getByText(/^Charles Cho$/i)).toBeInTheDocument()
    expect(
      within(thomasRow).getByText(/Los Angeles · NPI 1053512566/i),
    ).toBeInTheDocument()
  })

  it('shows overdue unscheduled patients on end-of-day scheduling check', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /6\. End-of-day check/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)

    expect(within(stepsPanel).queryByText(/Anita Gomez/i)).not.toBeInTheDocument()

    const mariaRow = within(stepsPanel)
      .getAllByRole('article')
      .find((article) =>
        within(article).queryByText(/Not scheduled · 36 hours/i),
      )!
    expect(mariaRow).toBeTruthy()
    expect(
      within(mariaRow).getByText(/Donessa Ruiz notified on Teams automatically/i),
    ).toBeInTheDocument()
    expect(
      within(mariaRow).getByRole('button', { name: /Escalate to Nicole/i }),
    ).toBeInTheDocument()
    expect(
      within(mariaRow).queryByRole('button', { name: /Escalate to management/i }),
    ).not.toBeInTheDocument()

    const thomasRow = within(stepsPanel)
      .getAllByRole('article')
      .find((article) =>
        within(article).queryByText(/Not scheduled · 18 hours/i),
      )!
    expect(thomasRow).toBeTruthy()
    expect(
      within(thomasRow).getByText(
        /Case manager will be notified automatically at 24 hours/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(thomasRow).getByRole('button', {
        name: /Follow up with case manager/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(thomasRow).getByRole('button', { name: /Escalate to Nicole/i }),
    ).toBeInTheDocument()

    await user.click(
      within(thomasRow).getByRole('button', {
        name: /Follow up with case manager/i,
      }),
    )
    expect(
      within(thomasRow).getAllByText(/Donessa Ruiz notified on Teams/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(thomasRow).queryByRole('button', {
        name: /Follow up with case manager/i,
      }),
    ).not.toBeInTheDocument()
    expect(
      within(thomasRow).getByRole('button', { name: /Escalate to Nicole/i }),
    ).toBeInTheDocument()

    const frankRow = within(stepsPanel)
      .getAllByRole('article')
      .find((article) =>
        within(article).queryByText(/Not scheduled · 51 hours/i),
      )!
    expect(frankRow).toBeTruthy()
    expect(
      within(frankRow).getByLabelText(/Unscheduled referral review/i),
    ).toBeInTheDocument()
    expect(
      within(frankRow).getByRole('button', { name: /Escalate to management/i }),
    ).toBeInTheDocument()

    await user.click(
      within(frankRow).getByRole('button', { name: /Escalate to management/i }),
    )
    expect(
      within(frankRow).getAllByText(/Escalated to management/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(stepsPanel).queryByText(/Scheduled Yes · complete blank/i),
    ).not.toBeInTheDocument()
  })

  it('marks step 2 unread after manual case manager follow-up on step 1', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /6\. End-of-day check/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    const thomasRow = within(stepsPanel)
      .getAllByRole('article')
      .find((article) =>
        within(article).queryByText(/Not scheduled · 18 hours/i),
      )!

    await user.click(
      within(thomasRow).getByRole('button', {
        name: /Follow up with case manager/i,
      }),
    )

    const followUpStep = within(stepsPanel)
      .getAllByRole('button')
      .find(
        (button) =>
          button.classList.contains('microstep-list__button') &&
          /Follow Up with Case Manager/i.test(button.textContent ?? ''),
      )!
    expect(
      followUpStep.querySelector('.microstep-list__attention-dot'),
    ).toBeInTheDocument()

    await user.click(followUpStep)

    const thomasStep2 = within(stepsPanel).getByRole('article', {
      name: /Donessa Ruiz notified on Teams · Thomas Reed/i,
    })
    expect(within(thomasStep2).getByText(/Unread/i)).toBeInTheDocument()
    const followUpPanel = within(thomasStep2).getByLabelText(
      /Case manager follow-up/i,
    )
    expect(
      within(followUpPanel).getByText(/^Donessa Ruiz notified on Teams$/i),
    ).toBeInTheDocument()
    expect(
      within(followUpPanel).queryByText(/automatically at 24 hours/i),
    ).not.toBeInTheDocument()
  })

  it('marks step 3 unread after escalation on step 1', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /6\. End-of-day check/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    const mariaRow = within(stepsPanel)
      .getAllByRole('article')
      .find((article) =>
        within(article).queryByText(/Not scheduled · 36 hours/i),
      )!

    await user.click(
      within(mariaRow).getByRole('button', { name: /Escalate to Nicole/i }),
    )

    const escalateStep = within(stepsPanel)
      .getAllByRole('button')
      .find(
        (button) =>
          button.classList.contains('microstep-list__button') &&
          /Escalate Unresolved Cases/i.test(button.textContent ?? ''),
      )!
    expect(
      escalateStep.querySelector('.microstep-list__attention-dot'),
    ).toBeInTheDocument()

    await user.click(escalateStep)

    const mariaStep3 = within(stepsPanel).getByRole('article', {
      name: /Escalated to Nicole · Maria Alvarez/i,
    })
    expect(within(mariaStep3).getByText(/Unread/i)).toBeInTheDocument()
    expect(
      within(mariaStep3).getAllByText(/^Escalated to Nicole$/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(mariaStep3).getByLabelText(/Management escalation email/i),
    ).toBeInTheDocument()
    expect(
      within(mariaStep3).getByText(/Donessa Ruiz/i),
    ).toBeInTheDocument()
  })

  it('shows Teams follow-up panel on end-of-day step 2', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /6\. End-of-day check/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    const followUpStep = within(stepsPanel)
      .getAllByRole('button')
      .find(
        (button) =>
          button.classList.contains('microstep-list__button') &&
          /Follow Up with Case Manager/i.test(button.textContent ?? ''),
      )!
    await user.click(followUpStep)

    expect(within(stepsPanel).queryByText(/Anita Gomez/i)).not.toBeInTheDocument()
    expect(
      within(stepsPanel).queryByText(/Not scheduled · 18 hours/i),
    ).not.toBeInTheDocument()

    const georgeRow = within(stepsPanel).getByRole('article', {
      name: /Carla Bustillo notified on Teams automatically · George Chen/i,
    })
    expect(
      within(georgeRow).getByText(
        /Carla Bustillo notified on Teams automatically$/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(georgeRow).getByLabelText(/Case manager follow-up/i),
    ).toBeInTheDocument()
    expect(
      within(georgeRow).getByText(
        /notified on Teams automatically at 24 hours/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(georgeRow).queryByRole('button', { name: /Follow-up sent on Teams/i }),
    ).not.toBeInTheDocument()
    expect(
      within(georgeRow).queryByText(/Automation is holding/i),
    ).not.toBeInTheDocument()
  })

  it('shows management escalation panel on end-of-day step 3', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /6\. End-of-day check/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Escalate Unresolved Cases/i,
      }),
    )

    const lindaRow = within(stepsPanel).getByRole('article', {
      name: /Escalated to management · still unresolved · Linda Nguyen/i,
    })
    expect(
      within(lindaRow).getByText(/^Escalated to management$/i),
    ).toBeInTheDocument()
    expect(
      within(lindaRow).getByLabelText(/Management escalation email/i),
    ).toBeInTheDocument()
    const emailSection = within(lindaRow).getByLabelText(
      /Management escalation email/i,
    )
    expect(within(emailSection).getByText(/^Patient$/i)).toBeInTheDocument()
    expect(within(emailSection).getByText(/^Linda Nguyen$/i)).toBeInTheDocument()
    expect(within(emailSection).getByText(/^Aaron Currie$/i)).toBeInTheDocument()
    expect(within(emailSection).getByText(/^Nicole Chorvat$/i)).toBeInTheDocument()
    expect(
      within(emailSection).getByText(/Not scheduled · 73 hours/i),
    ).toBeInTheDocument()
    expect(
      within(lindaRow).queryByText(/notified on Teams automatically at 24 hours/i),
    ).not.toBeInTheDocument()
    expect(
      within(lindaRow).queryByRole('button', { name: /Escalate to management/i }),
    ).not.toBeInTheDocument()
    expect(
      within(lindaRow).queryByText(/Automation is holding/i),
    ).not.toBeInTheDocument()
  })

  it('shows weekly visit outcomes and missed-visit actions on step 1', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /7\. Weekly visit cycle/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)

    const gloriaRow = within(stepsPanel)
      .getAllByRole('article')
      .find((article) => within(article).queryByText(/^Patient seen$/i))!
    expect(gloriaRow).toBeTruthy()
    expect(
      within(gloriaRow).getByLabelText(/Weekly visit review/i),
    ).toBeInTheDocument()
    expect(
      within(gloriaRow).queryByText(/marked SEEN on Monday.com/i),
    ).not.toBeInTheDocument()

    const margaretRow = within(stepsPanel)
      .getAllByRole('article')
      .find((article) =>
        within(article).queryByText(/Not seen · 2 consecutive weeks/i),
      )!
    expect(margaretRow).toBeTruthy()
    expect(
      within(margaretRow).getByRole('button', {
        name: /Mark NOT seen · reschedule/i,
      }),
    ).toBeInTheDocument()

    const walterRow = within(stepsPanel)
      .getAllByRole('article')
      .find((article) =>
        within(article).queryByText(/Not seen · 3 consecutive weeks/i),
      )!
    expect(walterRow).toBeTruthy()
    expect(
      within(walterRow).getByRole('button', {
        name: /Escalate for DC \(noncompliance\)/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      within(walterRow).getByRole('button', {
        name: /Escalate for DC \(noncompliance\)/i,
      }),
    )
    expect(
      within(walterRow).getAllByText(/Queued for DC · noncompliance/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(walterRow).getByLabelText(/Discharge review message/i),
    ).toBeInTheDocument()
    expect(
      within(walterRow).queryByRole('button', { name: /Confirm rescheduled/i }),
    ).not.toBeInTheDocument()

    await user.click(
      within(margaretRow).getByRole('button', {
        name: /Mark NOT seen · reschedule/i,
      }),
    )
    expect(
      within(margaretRow).getAllByText(/Marked NOT seen · reschedule weekly/i)
        .length,
    ).toBeGreaterThan(0)
    const teamsSection = within(margaretRow).getByLabelText(
      /Teams reschedule message/i,
    )
    expect(within(teamsSection).getByText(/^Patient$/i)).toBeInTheDocument()
    expect(within(teamsSection).getByText(/^Margaret Ellis$/i)).toBeInTheDocument()
    expect(within(teamsSection).getByText(/^Case manager$/i)).toBeInTheDocument()
    expect(
      within(margaretRow).getByRole('button', { name: /Confirm rescheduled/i }),
    ).toBeInTheDocument()

    await user.click(
      within(margaretRow).getByRole('button', { name: /Confirm rescheduled/i }),
    )
    expect(
      within(margaretRow).getAllByText(/Rescheduled confirmed/i).length,
    ).toBeGreaterThan(0)
    expect(
      within(margaretRow).queryByRole('button', { name: /Confirm rescheduled/i }),
    ).not.toBeInTheDocument()
    expect(
      within(margaretRow).queryByRole('button', {
        name: /Mark NOT seen · reschedule/i,
      }),
    ).not.toBeInTheDocument()
  })

  it('routes healed, expired, and hold patients to their weekly question steps', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /7\. Weekly visit cycle/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)

    const healedStep = within(stepsPanel)
      .getAllByRole('button')
      .find(
        (button) =>
          button.classList.contains('microstep-list__button') &&
          /Is the wound healed/i.test(button.textContent ?? ''),
      )!
    await user.click(healedStep)

    expect(
      within(stepsPanel).queryByText(/^Patient seen$/i),
    ).not.toBeInTheDocument()

    const nancyRow = within(stepsPanel).getByRole('article', {
      name: /Wound healed · Nancy Liu/i,
    })
    expect(
      within(nancyRow).getByRole('button', { name: /Send to QA discharge/i }),
    ).toBeInTheDocument()

    const expiredStep = within(stepsPanel)
      .getAllByRole('button')
      .find(
        (button) =>
          button.classList.contains('microstep-list__button') &&
          /Is the patient expired/i.test(button.textContent ?? ''),
      )!
    await user.click(expiredStep)

    const jamesRow = within(stepsPanel).getByRole('article', {
      name: /Patient expired · James Carter/i,
    })
    expect(
      within(jamesRow).getByRole('button', {
        name: /Remove from schedule · DC/i,
      }),
    ).toBeInTheDocument()

    const holdStep = within(stepsPanel)
      .getAllByRole('button')
      .find(
        (button) =>
          button.classList.contains('microstep-list__button') &&
          /Is the patient on hold/i.test(button.textContent ?? ''),
      )!
    await user.click(holdStep)

    const arthurRow = within(stepsPanel).getByRole('article', {
      name: /On hold · Hospitalization · Arthur Kim/i,
    })
    expect(
      within(arthurRow).getByRole('button', { name: /Move to holds team/i }),
    ).toBeInTheDocument()

    await user.click(
      within(arthurRow).getByRole('button', { name: /Move to holds team/i }),
    )
    expect(
      within(arthurRow).getAllByText(/Moved to holds team · Hospitalization/i)
        .length,
    ).toBeGreaterThan(0)
    expect(
      within(arthurRow).getByText(/Moved to the holds team and holds list/i),
    ).toBeInTheDocument()
    expect(
      within(arthurRow).queryByText(/Automation is holding/i),
    ).not.toBeInTheDocument()
  })
})
