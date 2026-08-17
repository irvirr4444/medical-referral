import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
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
    await user.click(screen.getByRole('button', { name: /^Confirm$/i }))
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
      screen.getByRole('button', {
        name: /Extract and verify referral details/i,
      }),
    ).toHaveAttribute('aria-current', 'step')
    expect(screen.getByLabelText(/Step updates/i)).toBeInTheDocument()
    expect(screen.getAllByText(/Gonzalez, Eric/i).length).toBeGreaterThan(0)
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
    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Receive referral in inbox/i,
      }),
    )
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

  it('lets an operator edit extracted referral fields then lock them on confirm', async () => {
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

    const article = within(stepsPanel).getByRole('article', {
      name: /Gonzalez, Eric/i,
    })
    expect(
      within(article).queryByRole('textbox', {
        name: /Home health or hospice agency/i,
      }),
    ).not.toBeInTheDocument()
    expect(
      within(article).getByRole('button', {
        name: /Confirm all information is correct/i,
      }),
    ).toBeEnabled()
    expect(
      within(article).getByRole('button', { name: /^Edit$/i }),
    ).toBeEnabled()
    expect(within(article).getByText('5/7')).toBeInTheDocument()
    expect(
      within(article).getByText(/^Missing$/i).closest('div'),
    ).toHaveTextContent(/Home health or hospice agency/i)

    await user.click(within(article).getByRole('button', { name: /^Edit$/i }))
    expect(
      within(article).getByRole('button', { name: /^Save changes$/i }),
    ).toBeEnabled()
    expect(
      within(article).getByRole('button', {
        name: /Confirm all information is correct/i,
      }),
    ).toBeEnabled()
    const agency = within(article).getByRole('textbox', {
      name: /Home health or hospice agency/i,
    })
    expect(agency).toBeEnabled()

    await user.clear(agency)
    await user.type(agency, 'VNA of Southern California')

    expect(within(article).getByText('5/7')).toBeInTheDocument()
    expect(
      within(article).getByText(/^Missing$/i).closest('div'),
    ).toHaveTextContent(/Home health or hospice agency/i)

    await user.click(
      within(article).getByRole('button', { name: /Show extracted details/i }),
    )
    await user.click(
      within(article).getByRole('button', { name: /Demographics/i }),
    )
    const email = within(article).getByRole('textbox', { name: /^Email$/i })
    expect(email).toBeEnabled()

    await user.click(
      within(article).getByRole('button', { name: /^Save changes$/i }),
    )
    expect(
      within(article).queryByRole('textbox', {
        name: /Home health or hospice agency/i,
      }),
    ).not.toBeInTheDocument()
    expect(within(article).getByText('VNA of Southern California')).toBeInTheDocument()
    expect(within(article).getByText('6/7')).toBeInTheDocument()
    expect(
      within(article).getByText(/^Missing$/i).closest('div'),
    ).toHaveTextContent(/^MissingNone$/i)
    expect(
      within(article).getByRole('button', { name: /^Edit$/i }),
    ).toBeEnabled()

    await user.click(
      within(article).getByRole('button', {
        name: /Confirm all information is correct/i,
      }),
    )

    const confirmedArticle = within(stepsPanel).getByRole('article', {
      name: /Gonzalez, Eric/i,
    })
    expect(
      within(confirmedArticle).queryByRole('textbox', {
        name: /Home health or hospice agency/i,
      }),
    ).not.toBeInTheDocument()
    expect(
      within(confirmedArticle).getByText('VNA of Southern California'),
    ).toBeInTheDocument()
    const confirmed = within(confirmedArticle).getByRole('button', {
      name: /^Confirmed$/i,
    })
    expect(confirmed).toBeDisabled()
    expect(
      within(confirmedArticle).getByRole('button', {
        name: /Add or edit patient information/i,
      }),
    ).toBeEnabled()
    expect(
      within(confirmedArticle).queryByRole('button', { name: /^Edit$/i }),
    ).not.toBeInTheDocument()
    await user.click(confirmed)
    expect(
      within(stepsPanel)
        .getByRole('article', { name: /Gonzalez, Eric/i })
        .textContent,
    ).toContain('VNA of Southern California')

    expect(
      within(stepsPanel).getByRole('button', {
        name: /Check Monday for existing patient.*new update/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Check DRK for existing chart.*new update/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Referral partner contacted.*(new update|overdue)/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Check Monday for existing patient/i,
      }),
    )
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Check Monday for existing patient.*new update/i,
      }),
    ).not.toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Check DRK for existing chart.*new update/i,
      }),
    ).toBeInTheDocument()
    expect(within(stepsPanel).getByText(/^Unread$/i)).toBeInTheDocument()
    const mondayArticle = within(stepsPanel).getByRole('article', {
      name: /Gonzalez, Eric/i,
    })
    expect(within(mondayArticle).getByText(/^Unread$/i)).toBeInTheDocument()
    expect(
      within(mondayArticle).getByText(/No matching Monday\.com candidate found/i),
    ).toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Check DRK for existing chart/i,
      }),
    )
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Check DRK for existing chart.*new update/i,
      }),
    ).not.toBeInTheDocument()
    expect(within(stepsPanel).getByText(/^Unread$/i)).toBeInTheDocument()
    const drkArticle = within(stepsPanel).getByRole('article', {
      name: /Gonzalez, Eric/i,
    })
    expect(
      within(drkArticle).getByText(/No exact DRK chart match found/i),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Referral partner contacted.*(new update|overdue)/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Referral partner contacted/i,
      }),
    )
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Referral partner contacted.*new update/i,
      }),
    ).not.toBeInTheDocument()
    const partnerArticle = within(stepsPanel).getByRole('article', {
      name: /Gonzalez, Eric/i,
    })
    expect(within(partnerArticle).getByText(/^Unread$/i)).toBeInTheDocument()
    expect(
      within(partnerArticle).getByText(/Awaiting partner confirmation/i),
    ).toBeInTheDocument()
  })

  it(
    'lets an operator add and remove intake list rows, then persist them on save',
    async () => {
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

    const article = within(stepsPanel).getByRole('article', {
      name: /Gonzalez, Eric/i,
    })
    expect(within(article).getByText('5/7')).toBeInTheDocument()

    await user.click(within(article).getByRole('button', { name: /^Edit$/i }))
    await user.click(
      within(article).getByRole('button', { name: /Show extracted details/i }),
    )

    await user.click(
      within(article).getByRole('button', { name: /Insurance policies/i }),
    )
    expect(
      within(article).getByRole('button', { name: /Insurance policies1 item/i }),
    ).toBeInTheDocument()
    await user.click(
      within(article).getByRole('button', { name: /Add insurance policy/i }),
    )
    await user.type(
      within(article).getByRole('textbox', {
        name: 'Insurance policies 2 Payer',
      }),
      'Blue Shield PPO',
    )
    await user.type(
      within(article).getByRole('textbox', {
        name: 'Insurance policies 2 Policy number',
      }),
      '998877',
    )

    await user.click(
      within(article).getByRole('button', { name: /^Diagnoses/i }),
    )
    await user.click(
      within(article).getByRole('button', { name: /Add diagnosis/i }),
    )
    await user.type(
      within(article).getByRole('textbox', { name: 'Diagnoses 29 Code' }),
      'I10',
    )
    await user.type(
      within(article).getByRole('textbox', {
        name: 'Diagnoses 29 Description',
      }),
      'Essential hypertension',
    )

    await user.click(
      within(article).getByRole('button', { name: /^Allergies/i }),
    )
    await user.click(
      within(article).getByRole('button', { name: /Add allergy/i }),
    )
    await user.type(
      within(article).getByRole('textbox', { name: 'Allergies 2 Name' }),
      'Penicillin',
    )

    await user.click(
      within(article).getByRole('button', { name: /^Warnings/i }),
    )
    expect(
      within(article).getByRole('button', { name: /Warnings15 items/i }),
    ).toBeInTheDocument()
    await user.click(
      within(article).getByRole('button', { name: 'Remove Warnings 1' }),
    )
    expect(
      within(article).getByRole('button', { name: /Warnings14 items/i }),
    ).toBeInTheDocument()
    await user.click(
      within(article).getByRole('button', { name: /Add warning/i }),
    )
    await user.type(
      within(article).getByRole('textbox', { name: /^Warning 16$/i }),
      'Needs interpreter for follow-up',
    )

    await user.click(
      within(article).getByRole('button', { name: /Processing guardrail/i }),
    )
    await user.click(
      within(article).getByRole('button', { name: /Add field/i }),
    )
    await user.type(
      within(article).getByRole('textbox', { name: /^Processing guardrail$/i }),
      'Reviewed by intake',
    )

    expect(within(article).getByText('5/7')).toBeInTheDocument()
    expect(
      within(article).getByText(/^Missing$/i).closest('div'),
    ).toHaveTextContent(/Home health or hospice agency/i)

    await user.click(
      within(article).getByRole('button', { name: /^Save changes$/i }),
    )

    expect(within(article).getByText('5/7')).toBeInTheDocument()
    expect(within(article).getAllByText('Blue Shield PPO').length).toBeGreaterThan(0)
    expect(within(article).getByText('998877')).toBeInTheDocument()
    expect(within(article).getAllByText('I10').length).toBeGreaterThan(0)
    expect(within(article).getByText('Essential hypertension')).toBeInTheDocument()
    expect(within(article).getAllByText('Penicillin').length).toBeGreaterThan(0)
    expect(
      within(article).getByText('Needs interpreter for follow-up'),
    ).toBeInTheDocument()
    expect(
      within(article).queryByText(/Patient address conflict/i),
    ).not.toBeInTheDocument()
    expect(within(article).getByText('Reviewed by intake')).toBeInTheDocument()
    expect(
      within(article).getByRole('button', { name: /Insurance policies2 items/i }),
    ).toBeInTheDocument()
    expect(
      within(article).getByRole('button', { name: /Warnings15 items/i }),
    ).toBeInTheDocument()
    expect(
      within(article).queryByRole('button', { name: /Add insurance policy/i }),
    ).not.toBeInTheDocument()

    await user.click(
      within(article).getByRole('button', {
        name: /Confirm all information is correct/i,
      }),
    )
    const confirmedArticle = within(stepsPanel).getByRole('article', {
      name: /Gonzalez, Eric/i,
    })
    expect(
      within(confirmedArticle).getByRole('button', { name: /^Confirmed$/i }),
    ).toBeDisabled()

    await user.click(
      within(confirmedArticle).getByRole('button', {
        name: /Add or edit patient information/i,
      }),
    )
    await user.click(
      within(confirmedArticle).getByRole('button', {
        name: /Show extracted details/i,
      }),
    )
    await user.click(
      within(confirmedArticle).getByRole('button', {
        name: /Insurance policies/i,
      }),
    )
    expect(
      within(confirmedArticle).getByRole('textbox', {
        name: 'Insurance policies 2 Payer',
      }),
    ).toHaveValue('Blue Shield PPO')
    await user.click(
      within(confirmedArticle).getByRole('button', { name: /^Diagnoses/i }),
    )
    expect(
      within(confirmedArticle).getByRole('textbox', { name: 'Diagnoses 29 Code' }),
    ).toHaveValue('I10')
    await user.click(
      within(confirmedArticle).getByRole('button', { name: /^Allergies/i }),
    )
    expect(
      within(confirmedArticle).getByRole('textbox', { name: 'Allergies 2 Name' }),
    ).toHaveValue('Penicillin')
    await user.click(
      within(confirmedArticle).getByRole('button', { name: /^Warnings/i }),
    )
    expect(
      within(confirmedArticle).getByRole('textbox', { name: /^Warning 16$/i }),
    ).toHaveValue('Needs interpreter for follow-up')
  },
  15_000,
)

  it('surfaces seeded overdue confirmation timers on nav, banner, and assignment', async () => {
    const user = userEvent.setup()
    render(<App />)

    expect(
      screen.getByRole('button', {
        name: /confirmations need immediate attention/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /2\. Assignment.*overdue/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /1\. Referral intake.*overdue/i }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /2\. Assignment.*overdue/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Assign Case Manager.*overdue/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', {
        name: /1 confirmation needs immediate attention on this step/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Assign Case Manager/i,
      }),
    )
    expect(
      within(stepsPanel).getByRole('heading', {
        name: /Needs immediate attention/i,
      }),
    ).toBeInTheDocument()
    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    expect(
      within(stepsPanel).getByRole('option', {
        name: /^Needs immediate attention$/i,
      }),
    ).toBeInTheDocument()
    await user.click(
      within(stepsPanel).getByRole('option', {
        name: /^Needs immediate attention$/i,
      }),
    )
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Filter by status/i,
      }),
    ).toHaveTextContent(/Needs immediate attention/i)
    expect(
      within(stepsPanel).getByRole('article', { name: /Marcus Feldman/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', { name: /David Ruiz/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).queryByRole('article', { name: /Thomas Reed/i }),
    ).not.toBeInTheDocument()
    const marcus = within(stepsPanel).getByRole('article', {
      name: /Marcus Feldman/i,
    })
    const david = within(stepsPanel).getByRole('article', {
      name: /David Ruiz/i,
    })
    expect(
      within(marcus).getByText(/Immediate attention/i),
    ).toBeInTheDocument()
    expect(within(marcus).getByText(/overdue/i)).toBeInTheDocument()
    expect(within(david).getByText(/Due soon/i)).toBeInTheDocument()
    await user.click(within(marcus).getByRole('button', { name: /^Confirm$/i }))

    expect(
      screen.queryByRole('button', { name: /2\. Assignment.*overdue/i }),
    ).not.toBeInTheDocument()
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Assign Case Manager.*overdue/i,
      }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', {
        name: /needs? immediate attention on this step/i,
      }),
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /1\. Referral intake.*overdue/i }),
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

    const marcus = within(stepsPanel).getByRole('article', {
      name: /Marcus Feldman/i,
    })
    const managerSelect = within(marcus).getByLabelText(/Assigned case manager/i)
    await user.selectOptions(managerSelect, 'ndelpelicano@westcoastwound.com')
    expect(managerSelect).toHaveValue('ndelpelicano@westcoastwound.com')

    await user.click(
      within(marcus).getByRole('button', {
        name: /^Confirm$/i,
      }),
    )
    expect(
      within(
        within(stepsPanel).getByRole('article', { name: /Marcus Feldman/i }),
      ).getByText(/^Assigned$/i),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: /2\. Assignment.*(new update|overdue)/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Notify Case Manager.*new update/i,
      }),
    ).toBeInTheDocument()
    await user.click(
      within(stepsPanel).getByRole('button', { name: /Notify Case Manager/i }),
    )
    expect(
      screen.queryByRole('button', { name: /2\. Assignment.*(new update|overdue)/i }),
    ).not.toBeInTheDocument()
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Notify Case Manager.*new update/i,
      }),
    ).not.toBeInTheDocument()
    expect(within(stepsPanel).getByText(/^Unread$/i)).toBeInTheDocument()
    expect(
      within(stepsPanel).getByText(/^Nadine Pelicano notified$/i),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getAllByText(/ndelpelicano@westcoastwound\.com/i)
        .length,
    ).toBeGreaterThan(0)
    expect(
      within(stepsPanel).getAllByLabelText(
        /Patient data shared with case manager/i,
      ).length,
    ).toBeGreaterThan(0)

    await user.click(
      within(stepsPanel).getByRole('button', { name: /Assign Case Manager/i }),
    )
    await user.click(
      within(stepsPanel).getByRole('button', { name: /Notify Case Manager/i }),
    )
    expect(within(stepsPanel).queryByText(/^Unread$/i)).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', { name: /3\. Handoff.*new update/i }),
    ).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', { name: /3\. Handoff.*new update/i }),
    )
    const handoffPanel = screen.getByLabelText(/Patient steps/i)
    expect(
      within(handoffPanel).getByRole('button', {
        name: /Notify Case Manager.*new update/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(handoffPanel).getByRole('button', {
        name: /Create Monday\.com Record.*new update/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(handoffPanel).getByRole('button', {
        name: /Prepare DRK Chart.*new update/i,
      }),
    ).toBeInTheDocument()
    expect(within(handoffPanel).getByText(/^Unread$/i)).toBeInTheDocument()

    await user.click(
      within(handoffPanel).getByRole('button', {
        name: /Create Monday\.com Record.*new update/i,
      }),
    )
    expect(within(handoffPanel).getByText(/^Unread$/i)).toBeInTheDocument()
    expect(
      within(handoffPanel).getByRole('button', {
        name: /Prepare DRK Chart.*new update/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(handoffPanel).queryByRole('button', {
        name: /Create Monday\.com Record.*new update/i,
      }),
    ).not.toBeInTheDocument()

    expect(
      screen.getByRole('button', {
        name: /4\. Provider selection.*(new update|overdue)/i,
      }),
    ).toBeInTheDocument()
    await user.click(
      screen.getByRole('button', {
        name: /4\. Provider selection.*(new update|overdue)/i,
      }),
    )
    const providerPanel = screen.getByLabelText(/Patient steps/i)
    expect(
      within(providerPanel).getByRole('button', {
        name: /Select Provider.*(new update|overdue)/i,
      }),
    ).toBeInTheDocument()
    expect(within(providerPanel).getByText(/^Unread$/i)).toBeInTheDocument()

    await user.click(
      within(providerPanel).getByRole('button', {
        name: /Select Provider.*(new update|overdue)/i,
      }),
    )
    expect(
      within(providerPanel).queryByRole('button', {
        name: /Select Provider.*new update/i,
      }),
    ).not.toBeInTheDocument()
    expect(within(providerPanel).getByText(/^Unread$/i)).toBeInTheDocument()
  })

  it('carries a partner contact confirmation into the Assignment stage', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /1\. Referral intake/i }))
    const intakePanel = screen.getByLabelText(/Patient steps/i)
    await user.click(
      within(intakePanel).getByRole('button', {
        name: /Referral partner contacted/i,
      }),
    )
    const butlerMessage = within(intakePanel).getByRole('article', {
      name: /BUTLER, ALVA/i,
    })
    await user.click(
      within(butlerMessage).getByRole('button', { name: /contacted/i }),
    )

    await user.click(
      screen.getByRole('button', { name: /2\. Assignment.*(new update|overdue)/i }),
    )
    const assignmentPanel = screen.getByLabelText(/Patient steps/i)
    expect(
      within(assignmentPanel).getByRole('button', {
        name: /Assign Case Manager.*(new update|overdue)/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(assignmentPanel).getByText(
        /Intake approved · referral partner contacted · ready to assign an owner/i,
      ),
    ).toBeInTheDocument()
    expect(within(assignmentPanel).getByText(/^Unread$/i)).toBeInTheDocument()

    await user.click(
      within(assignmentPanel).getByRole('button', {
        name: /Assign Case Manager.*(new update|overdue)/i,
      }),
    )
    expect(
      within(assignmentPanel).queryByRole('button', {
        name: /Assign Case Manager.*new update/i,
      }),
    ).not.toBeInTheDocument()
    expect(within(assignmentPanel).getByText(/^Unread$/i)).toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /2\. Assignment.*new update/i }),
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
      within(stepsPanel).getByRole('button', { name: /^Select Provider(,|$)/i }),
    ).toHaveAttribute('aria-current', 'step')
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Find Eligible Providers/i,
      }),
    ).not.toBeInTheDocument()

    const providerSelect = within(stepsPanel)
      .getAllByLabelText(/Selected provider/i)
      .find((select) =>
        Array.from(select.querySelectorAll('option')).every((option) =>
          option.textContent?.includes('Los Angeles'),
        ),
      )!
    const providerArticle = providerSelect.closest('article')!
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
      within(providerArticle).getByRole('button', { name: /^Confirm$/i }),
    )
    expect(within(providerArticle).getByText(/^Selected$/i)).toBeInTheDocument()
    expect(
      screen.getByRole('button', {
        name: /4\. Provider selection.*(new update|overdue)/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Confirm Provider Availability.*(new update|overdue)/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Confirm Provider Availability/i,
      }),
    )
    expect(
      screen.queryByRole('button', {
        name: /4\. Provider selection.*new update/i,
      }),
    ).not.toBeInTheDocument()
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Confirm Provider Availability.*new update/i,
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
    expect(within(availabilityPanel).getByText(/^\d+:\d{2}$/)).toBeInTheDocument()

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
        name: /Update Monday\.com and DRK.*new update/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', {
        name: /5\. Scheduling.*new update/i,
      }),
    ).not.toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Update Monday\.com and DRK/i,
      }),
    )
    expect(
      within(stepsPanel).queryByRole('button', {
        name: /Update Monday\.com and DRK.*new update/i,
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
        name: /5\. Scheduling.*new update/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', {
        name: /5\. Scheduling.*new update/i,
      }),
    )
    expect(
      screen.queryByRole('button', {
        name: /5\. Scheduling.*new update/i,
      }),
    ).not.toBeInTheDocument()
    const schedulingPanel = screen.getByLabelText(/Patient steps/i)
    await user.click(
      within(schedulingPanel).getByRole('button', {
        name: /Send Referral to Provider/i,
      }),
    )
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
    const helen = within(stepsPanel).getByRole('article', {
      name: /Helen Park/i,
    })
    await user.click(within(helen).getByRole('button', { name: /^Confirm$/i }))
    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Confirm Provider Availability/i,
      }),
    )

    const availabilityPanel = within(
      within(stepsPanel).getByRole('article', { name: /Helen Park/i }),
    ).getByLabelText(/Provider availability response/i)
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
        name: /5\. Scheduling.*new update/i,
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
        name: /Update Monday\.com and DRK.*new update/i,
      }),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', {
        name: /5\. Scheduling.*new update/i,
      }),
    ).not.toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Update Monday\.com and DRK/i,
      }),
    )
    expect(
      screen.getByRole('button', {
        name: /5\. Scheduling.*new update/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', {
        name: /5\. Scheduling.*new update/i,
      }),
    )
    const schedulingPanel = screen.getByLabelText(/Patient steps/i)
    await user.click(
      within(schedulingPanel).getByRole('button', {
        name: /Send Referral to Provider/i,
      }),
    )
    expect(
      within(schedulingPanel).getAllByText(
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
      within(stepsPanel).getByText(/Patient discharged after Nicole review/i),
    ).toBeInTheDocument()
    expect(
      screen.queryByRole('button', {
        name: /5\. Scheduling.*new update/i,
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

  it('lets an operator pick a provider slot and schedule the patient', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /5\. Scheduling/i }))
    const stepsPanel = screen.getByLabelText(/Patient steps/i)
    expect(
      within(stepsPanel).getByRole('button', {
        name: /Schedule Patient.*overdue/i,
      }),
    ).toHaveAttribute('aria-current', 'step')

    const maria = within(stepsPanel).getByRole('article', {
      name: /Maria Alvarez/i,
    })
    expect(
      within(maria).getByRole('region', { name: /^Schedule patient$/i }),
    ).toBeInTheDocument()
    expect(within(maria).getByText(/^Daniel Rowady$/i)).toBeInTheDocument()
    expect(within(maria).getByText(/Availability synced 2 min ago/i)).toBeInTheDocument()
    expect(within(maria).queryByRole('combobox')).not.toBeInTheDocument()
    expect(
      within(maria).getByRole('button', { name: /^Schedule patient$/i }),
    ).toBeDisabled()
    expect(
      within(maria).getByRole('button', {
        name: /Tomorrow 1:30 PM, unavailable/i,
      }),
    ).toBeDisabled()

    await user.click(
      within(maria).getByRole('button', { name: /^Today 3:30 PM$/i }),
    )
    await user.click(
      within(maria).getByRole('button', { name: /^Schedule patient$/i }),
    )

    const scheduled = within(stepsPanel).getByRole('article', {
      name: /Maria Alvarez/i,
    })
    expect(within(scheduled).getAllByText(/^Patient scheduled$/i).length).toBeGreaterThan(0)
    expect(within(scheduled).getAllByText(/August 14, 2026/i).length).toBeGreaterThan(0)
    expect(within(scheduled).getByText(/Monday\.com appointment date updated/i)).toBeInTheDocument()
    expect(
      within(scheduled).queryByRole('button', { name: /^Schedule patient$/i }),
    ).not.toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /6\. End-of-day check/i }),
    )
    const eodPanel = screen.getByLabelText(/Patient steps/i)
    expect(
      within(eodPanel).getByRole('article', {
        name: /Scheduled · Monday fields agree · Maria Alvarez/i,
      }),
    ).toBeInTheDocument()
  })

  it('shows every scheduling scenario without letting the operator reselect a provider', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(screen.getByRole('button', { name: /5\. Scheduling/i }))
    const stepsPanel = screen.getByLabelText(/Patient steps/i)

    const james = within(stepsPanel).getByRole('article', {
      name: /James Carter/i,
    })
    expect(within(james).getByText(/Placed manually/i)).toBeInTheDocument()
    expect(
      within(james).getByRole('button', { name: /^Today 4:45 PM$/i }),
    ).toBeEnabled()

    const linda = within(stepsPanel).getByRole('article', {
      name: /Linda Nguyen/i,
    })
    expect(within(linda).getAllByText(/Patient declined available appointment windows/i).length).toBeGreaterThan(0)
    expect(
      within(linda).queryByRole('button', { name: /^Schedule patient$/i }),
    ).not.toBeInTheDocument()

    const david = within(stepsPanel).getByRole('article', {
      name: /David Ruiz/i,
    })
    expect(
      within(david).getAllByText(/No open slots within 24–48 hours/i).length,
    ).toBeGreaterThan(0)

    const nancy = within(stepsPanel).getByRole('article', {
      name: /Nancy Liu/i,
    })
    expect(within(nancy).getAllByText(/^Patient scheduled$/i).length).toBeGreaterThan(0)
    expect(within(nancy).getAllByText(/August 11, 2026/i).length).toBeGreaterThan(0)

    const thomas = within(stepsPanel).getByRole('article', {
      name: /Thomas Reed/i,
    })
    await user.click(within(thomas).getByRole('button', { name: /No suitable time/i }))
    await user.click(
      within(thomas).getByRole('button', {
        name: /Patient declined available appointment windows/i,
      }),
    )
    expect(
      within(
        within(stepsPanel).getByRole('article', { name: /Thomas Reed/i }),
      ).getAllByText(/Patient declined available appointment windows/i).length,
    ).toBeGreaterThan(0)
  })

  it('shows overdue unscheduled patients on end-of-day scheduling check', async () => {
    const user = userEvent.setup()
    render(<App />)

    await user.click(
      screen.getByRole('button', { name: /6\. End-of-day check/i }),
    )
    const stepsPanel = screen.getByLabelText(/Patient steps/i)

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    expect(
      within(stepsPanel).getByRole('option', { name: /^Scheduled$/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('option', {
        name: /^Not scheduled after 48h$/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('option', {
        name: /^Not scheduled less than 48h$/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('option', {
        name: /^Needs immediate attention$/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).queryByRole('option', { name: /^Needs confirmation$/i }),
    ).not.toBeInTheDocument()
    await user.click(within(stepsPanel).getByRole('option', { name: /^All statuses$/i }))

    expect(within(stepsPanel).getByText(/Anita Gomez/i)).toBeInTheDocument()

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    await user.click(
      within(stepsPanel).getByRole('option', { name: /^Scheduled$/i }),
    )
    expect(within(stepsPanel).getByText(/Anita Gomez/i)).toBeInTheDocument()
    expect(
      within(stepsPanel).queryByText(/Not scheduled · 36 hours/i),
    ).not.toBeInTheDocument()

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    await user.click(
      within(stepsPanel).getByRole('option', {
        name: /^Not scheduled after 48h$/i,
      }),
    )
    expect(
      within(stepsPanel).queryByText(/Anita Gomez/i),
    ).not.toBeInTheDocument()
    expect(
      within(stepsPanel).queryByText(/Not scheduled · 18 hours/i),
    ).not.toBeInTheDocument()
    expect(
      within(stepsPanel).getByText(/Not scheduled · 51 hours/i),
    ).toBeInTheDocument()

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    await user.click(
      within(stepsPanel).getByRole('option', {
        name: /^Not scheduled less than 48h$/i,
      }),
    )
    expect(
      within(stepsPanel).queryByText(/Not scheduled · 51 hours/i),
    ).not.toBeInTheDocument()
    expect(
      within(stepsPanel).getByText(/Not scheduled · 18 hours/i),
    ).toBeInTheDocument()

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    await user.click(within(stepsPanel).getByRole('option', { name: /^All statuses$/i }))

    const anitaRow = within(stepsPanel).getByRole('article', {
      name: /Anita Gomez/i,
    })
    expect(within(anitaRow).getByText(/^Scheduled$/)).toBeInTheDocument()
    expect(within(anitaRow).queryByText(/^Finished$/)).not.toBeInTheDocument()

    const mariaRow = within(stepsPanel)
      .getAllByRole('article')
      .find((article) =>
        within(article).queryByText(/Not scheduled · 36 hours/i),
      )!
    expect(mariaRow).toBeTruthy()
    expect(
      within(mariaRow).getByText(/^Not scheduled less than 48h$/),
    ).toBeInTheDocument()
    expect(within(mariaRow).queryByText(/^Finished$/)).not.toBeInTheDocument()
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
      within(thomasRow).getByText(/^Not scheduled less than 48h$/),
    ).toBeInTheDocument()
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
      within(frankRow).getByText(/^Not scheduled after 48h$/),
    ).toBeInTheDocument()
    expect(within(frankRow).queryByText(/^Finished$/)).not.toBeInTheDocument()
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
      within(stepsPanel).getAllByText(/Escalated to management/i).length,
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

    expect(
      screen.getByRole('button', {
        name: /6\. End-of-day check.*(new update|overdue)/i,
      }),
    ).toBeInTheDocument()

    const followUpStep = within(stepsPanel)
      .getAllByRole('button')
      .find(
        (button) =>
          button.classList.contains('microstep-list__button') &&
          /Follow Up with Case Manager/i.test(button.textContent ?? ''),
      )!
    expect(
      followUpStep.querySelector('.microstep-list__count'),
    ).toBeInTheDocument()

    await user.click(followUpStep)

    expect(
      screen.queryByRole('button', {
        name: /6\. End-of-day check.*(new update|overdue)/i,
      }),
    ).not.toBeInTheDocument()

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
    expect(
      within(followUpPanel).getByLabelText(/^Patient scheduling status$/i),
    ).toHaveTextContent(/^Not scheduled less than 48h$/)
    expect(within(followUpPanel).getByText(/^Thomas Reed$/i)).toBeInTheDocument()
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

    expect(
      screen.getByRole('button', {
        name: /6\. End-of-day check.*(new update|overdue)/i,
      }),
    ).toBeInTheDocument()

    const escalateStep = within(stepsPanel)
      .getAllByRole('button')
      .find(
        (button) =>
          button.classList.contains('microstep-list__button') &&
          /Escalate Unresolved Cases/i.test(button.textContent ?? ''),
      )!
    expect(
      escalateStep.querySelector('.microstep-list__count'),
    ).toBeInTheDocument()

    await user.click(escalateStep)

    expect(
      screen.queryByRole('button', {
        name: /6\. End-of-day check.*(new update|overdue)/i,
      }),
    ).not.toBeInTheDocument()

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
    expect(
      within(mariaStep3).getByLabelText(/^Patient scheduling status$/i),
    ).toHaveTextContent(/^Not scheduled less than 48h$/)
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

    expect(
      within(stepsPanel).getByRole('article', { name: /Marcus Feldman/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', { name: /David Ruiz/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', { name: /Irene Cho/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', { name: /Gloria Bennett/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', { name: /Betty Hayes/i }),
    ).toBeInTheDocument()

    const patriciaRow = within(stepsPanel).getByRole('article', {
      name: /Cole Winfield notified on Teams automatically · Patricia Johnson/i,
    })
    expect(
      within(patriciaRow).getByLabelText(/^Patient scheduling status$/i),
    ).toHaveTextContent(/^Scheduled$/)

    const marcusRow = within(stepsPanel).getByRole('article', {
      name: /Cole Winfield notified on Teams automatically · Marcus Feldman/i,
    })
    expect(
      within(marcusRow).getByLabelText(/^Patient scheduling status$/i),
    ).toHaveTextContent(/^Not scheduled less than 48h$/)

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
    const followUpPanel = within(georgeRow).getByLabelText(
      /Case manager follow-up/i,
    )
    expect(
      within(followUpPanel).getByText(
        /notified on Teams automatically at 24 hours/i,
      ),
    ).toBeInTheDocument()
    expect(
      within(followUpPanel).getByLabelText(/^Patient scheduling status$/i),
    ).toHaveTextContent(/^Not scheduled after 48h$/)
    expect(within(followUpPanel).getByText(/^George Chen$/i)).toBeInTheDocument()
    expect(
      within(georgeRow).queryByRole('button', { name: /Follow-up sent on Teams/i }),
    ).not.toBeInTheDocument()
    expect(
      within(georgeRow).queryByText(/Automation is holding/i),
    ).not.toBeInTheDocument()
  })

  it('scopes the worklist to one patient from the name link', async () => {
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

    const frankRow = within(stepsPanel).getByRole('article', {
      name: /Carla Bustillo notified on Teams automatically · George Chen/i,
    })
    await user.click(
      within(frankRow).getByRole('button', { name: /Show George Chen/i }),
    )

    expect(
      within(stepsPanel).getByRole('button', { name: /Clear patient/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).queryByLabelText(/Search patients/i),
    ).not.toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', { name: /George Chen/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).queryByRole('article', { name: /Frank Owens/i }),
    ).not.toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Escalate Unresolved Cases/i,
      }),
    )
    expect(
      within(stepsPanel).getByText(/George Chen is not on this step yet/i),
    ).toBeInTheDocument()

    await user.click(
      within(stepsPanel).getByRole('button', {
        name: /Check Scheduling Status/i,
      }),
    )
    expect(
      within(stepsPanel).getByRole('article', { name: /George Chen/i }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /1\. Referral intake/i }),
    )
    const intakePanel = screen.getByLabelText(/Patient steps/i)
    expect(
      within(intakePanel).getByRole('button', { name: /Clear patient/i }),
    ).toBeInTheDocument()
    expect(
      within(intakePanel).getByText(/George Chen is not on this step yet/i),
    ).toBeInTheDocument()

    await user.click(
      within(intakePanel).getByRole('button', { name: /Clear patient/i }),
    )
    expect(
      within(intakePanel).queryByRole('button', { name: /Clear patient/i }),
    ).not.toBeInTheDocument()
    expect(
      within(intakePanel).getByLabelText(/Search patients/i),
    ).toBeInTheDocument()
    expect(
      within(intakePanel).getByRole('button', { name: /Show BUTLER, ALVA/i }),
    ).toBeInTheDocument()
    expect(window.location.pathname).toBe('/')
    expect(
      screen.queryByRole('heading', { name: /^George Chen$/i }),
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
      within(emailSection).getByLabelText(/^Patient scheduling status$/i),
    ).toHaveTextContent(/^Not scheduled after 48h$/)
    expect(
      within(emailSection).getByText(/73 hours · provider selected/i),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', { name: /Betty Hayes/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', { name: /Walter Grant/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', { name: /Gloria Bennett/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', { name: /Dorothy Lane/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', { name: /Margaret Ellis/i }),
    ).toBeInTheDocument()

    const arthurRow = within(stepsPanel).getByRole('article', {
      name: /Escalated to Nicole · Arthur Kim/i,
    })
    expect(
      within(arthurRow).getByLabelText(/^Patient scheduling status$/i),
    ).toHaveTextContent(/^Scheduled$/)
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

    expect(
      within(stepsPanel).getByRole('button', { name: /^Seen patients/i }),
    ).toHaveAttribute('aria-current', 'step')
    expect(
      within(stepsPanel).getByRole('button', { name: /^Healed patients/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('button', { name: /^Expired patients/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('button', { name: /^On hold patients/i }),
    ).toBeInTheDocument()

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    expect(
      within(stepsPanel).getByRole('option', { name: /^Seen$/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('option', { name: /^Not seen$/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).queryByRole('option', { name: /^Needs confirmation$/i }),
    ).not.toBeInTheDocument()

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
    const walterAfter = within(stepsPanel)
      .getAllByRole('article')
      .find(
        (article) =>
          within(article).queryAllByText(/Queued for DC · noncompliance/i)
            .length > 0,
      )!
    expect(walterAfter).toBeTruthy()
    expect(
      within(walterAfter).getByLabelText(/Discharge review message/i),
    ).toBeInTheDocument()
    expect(
      within(walterAfter).queryByRole('button', {
        name: /Confirm rescheduled/i,
      }),
    ).not.toBeInTheDocument()

    await user.click(
      within(margaretRow).getByRole('button', {
        name: /Mark NOT seen · reschedule/i,
      }),
    )
    const margaretAfter = within(stepsPanel)
      .getAllByRole('article')
      .find(
        (article) =>
          within(article).queryAllByText(
            /Marked NOT seen · reschedule weekly/i,
          ).length > 0,
      )!
    expect(margaretAfter).toBeTruthy()
    const teamsSection = within(margaretAfter).getByLabelText(
      /Teams reschedule message/i,
    )
    expect(within(teamsSection).getByText(/^Patient$/i)).toBeInTheDocument()
    expect(within(teamsSection).getByText(/^Margaret Ellis$/i)).toBeInTheDocument()
    expect(within(teamsSection).getByText(/^Case manager$/i)).toBeInTheDocument()
    expect(
      within(margaretAfter).getByRole('button', {
        name: /Confirm rescheduled/i,
      }),
    ).toBeInTheDocument()

    await user.click(
      within(margaretAfter).getByRole('button', {
        name: /Confirm rescheduled/i,
      }),
    )
    const margaretDone = within(stepsPanel)
      .getAllByRole('article')
      .find(
        (article) =>
          within(article).queryAllByText(/Rescheduled confirmed/i).length > 0,
      )!
    expect(margaretDone).toBeTruthy()
    expect(
      within(margaretDone).queryByRole('button', {
        name: /Confirm rescheduled/i,
      }),
    ).not.toBeInTheDocument()
    expect(
      within(margaretDone).queryByRole('button', {
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
          /Healed patients/i.test(button.textContent ?? ''),
      )!
    await user.click(healedStep)

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    expect(
      within(stepsPanel).getByRole('option', { name: /^Healed$/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('option', { name: /^Not healed$/i }),
    ).toBeInTheDocument()
    await user.click(within(stepsPanel).getByRole('option', { name: /^Not healed$/i }))

    expect(
      within(stepsPanel).queryByText(/^Patient seen$/i),
    ).not.toBeInTheDocument()

    const nancyRow = within(stepsPanel).getByRole('article', {
      name: /Wound healed · Nancy Liu/i,
    })
    expect(
      within(nancyRow).getByRole('button', { name: /Send to QA discharge/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', {
        name: /Wound healed · Irene Cho/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).queryByRole('article', {
        name: /Healed · QA discharge path · Betty Hayes/i,
      }),
    ).not.toBeInTheDocument()

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    await user.click(within(stepsPanel).getByRole('option', { name: /^Healed$/i }))
    expect(
      within(stepsPanel).getByRole('article', {
        name: /Healed · QA discharge path · Betty Hayes/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', {
        name: /Healed · QA discharge path · David Ruiz/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).queryByRole('article', {
        name: /Wound healed · Nancy Liu/i,
      }),
    ).not.toBeInTheDocument()

    const expiredStep = within(stepsPanel)
      .getAllByRole('button')
      .find(
        (button) =>
          button.classList.contains('microstep-list__button') &&
          /Expired patients/i.test(button.textContent ?? ''),
      )!
    await user.click(expiredStep)

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    await user.click(
      within(stepsPanel).getByRole('option', { name: /^Not expired$/i }),
    )
    const jamesRow = within(stepsPanel).getByRole('article', {
      name: /Patient expired · James Carter/i,
    })
    expect(
      within(jamesRow).getByRole('button', {
        name: /Remove from schedule · DC/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', {
        name: /Patient expired · Maria Alvarez/i,
      }),
    ).toBeInTheDocument()

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    await user.click(within(stepsPanel).getByRole('option', { name: /^Expired$/i }))
    expect(
      within(stepsPanel).getByRole('article', {
        name: /Expired · pending DC approval · Thomas Reed/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', {
        name: /Expired · pending DC approval · Marcus Feldman/i,
      }),
    ).toBeInTheDocument()

    const holdStep = within(stepsPanel)
      .getAllByRole('button')
      .find(
        (button) =>
          button.classList.contains('microstep-list__button') &&
          /On hold patients/i.test(button.textContent ?? ''),
      )!
    await user.click(holdStep)

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    await user.click(within(stepsPanel).getByRole('option', { name: /^Not hold$/i }))
    const arthurRow = within(stepsPanel).getByRole('article', {
      name: /On hold · Hospitalization · Arthur Kim/i,
    })
    expect(
      within(arthurRow).getByRole('button', { name: /Move to holds team/i }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', {
        name: /On hold · Vacation · George Chen/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', {
        name: /On hold · Patient request · Anita Rodriguez/i,
      }),
    ).toBeInTheDocument()

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    await user.click(within(stepsPanel).getByRole('option', { name: /^Hold$/i }))
    expect(
      within(stepsPanel).getByRole('article', {
        name: /Moved to holds team · Facility hold · Linda Nguyen/i,
      }),
    ).toBeInTheDocument()
    expect(
      within(stepsPanel).getByRole('article', {
        name: /Moved to holds team · Family request · Frank Sardina/i,
      }),
    ).toBeInTheDocument()

    await user.click(within(stepsPanel).getByLabelText(/Filter by status/i))
    await user.click(within(stepsPanel).getByRole('option', { name: /^All statuses$/i }))
    const arthurPending = within(stepsPanel).getByRole('article', {
      name: /On hold · Hospitalization · Arthur Kim/i,
    })
    await user.click(
      within(arthurPending).getByRole('button', { name: /Move to holds team/i }),
    )
    const arthurDone = within(stepsPanel).getByRole('article', {
      name: /Moved to holds team · Hospitalization · Arthur Kim/i,
    })
    expect(
      within(arthurDone).getByText(/Moved to the holds team and holds list/i),
    ).toBeInTheDocument()
  })
})

describe('patient profile route', () => {
  afterEach(() => {
    window.history.pushState({}, '', '/')
    vi.restoreAllMocks()
  })

  function jsonResponse(status: number, body: unknown) {
    return Promise.resolve({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    } as Response)
  }

  function mockPatientApi(
    handler: (url: string) => { status: number; body: unknown },
  ) {
    return vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input)
      const { status, body } = handler(url)
      return jsonResponse(status, body)
    })
  }

  const butlerMonday = {
    item_id: 'm1',
    group: 'Working pipeline',
    name: 'BUTLER, ALVA',
    dob: '10/04/1940',
    phone: '813-555-0100',
    address: '123 Main St, Tampa, FL',
    pos: 'SNF',
    case_manager: 'Nicole Chorvat',
    sent_to_cm: 'Yes',
    referral_sent: 'Yes',
    provider: 'Jane Provider',
    due_date: '',
    appointment: '08/20/2026',
    scheduled: 'Scheduled',
    scheduled_complete: 'Yes',
    visit: 'Scheduled',
    sent_by: 'Case Management <casemanagement@tampa-general.org>',
    agency_contact: 'Tampa General',
    stage: 'In intake',
  }

  const butlerDrk = {
    patient_id: '77',
    name: 'Alva Butler',
    first_name: 'Alva',
    last_name: 'Butler',
    dob: '1940-10-04T00:00:00',
    phone: '(813) 555-0100',
    email: '',
    address: 'Tampa',
    city: 'Tampa',
    mrn: 'MRN-77',
    status: 'Active',
    facility: 'Tampa General',
    home_health: '',
    provider: 'Other Provider',
    visit: 'Seen',
    appointment: '08/20/2026',
    observed_at: '',
    sections: [
      {
        id: 'demographics',
        title: 'Demographics',
        defaultExpanded: true,
        fields: [{ label: 'Name', value: 'Alva Butler' }],
      },
      {
        id: 'diagnoses',
        title: 'Diagnoses',
        defaultExpanded: true,
        repeatable: true,
        fields: [
          { label: 'Code', value: 'L89.153', rowId: 'diagnoses.0' },
          { label: 'Description', value: 'Pressure ulcer', rowId: 'diagnoses.0' },
        ],
      },
      {
        id: 'admission',
        title: 'Admission',
        defaultExpanded: true,
        fields: [{ label: 'Facility', value: 'Tampa General' }],
      },
      {
        id: 'medications',
        title: 'Medications',
        defaultExpanded: false,
        repeatable: true,
        fields: [{ label: 'Name', value: 'Mupirocin Topical Ointment 2 %', rowId: 'medications.0' }],
      },
      {
        id: 'notes',
        title: 'Clinical notes',
        defaultExpanded: false,
        repeatable: true,
        fields: [{ label: 'Note', value: 'Called patient', rowId: 'notes.0' }],
      },
      {
        id: 'insurance',
        title: 'Insurance policies',
        defaultExpanded: true,
        repeatable: true,
        fields: [{ label: 'Payer', value: 'Medicare', rowId: 'insurance.0' }],
      },
      {
        id: 'encounters',
        title: 'Encounters',
        defaultExpanded: true,
        repeatable: true,
        fields: [{ label: 'Provider', value: 'Arnaldo Gomez Lotti', rowId: 'encounters.0' }],
      },
      {
        id: 'documents',
        title: 'Documents',
        defaultExpanded: false,
        repeatable: true,
        fields: [{ label: 'File', value: 'Wound photo', rowId: 'documents.0' }],
      },
      {
        id: 'billing',
        title: 'Billing',
        defaultExpanded: false,
        fields: [{ label: 'Collections status', value: 'None' }],
      },
      {
        id: 'pipeline',
        title: 'Pipeline',
        defaultExpanded: true,
        fields: [{ label: 'Stage', value: 'QA' }],
      },
    ],
  }

  it('opens the profile at /patient/:id without a search bar', async () => {
    mockPatientApi((url) => {
      if (url.includes('source=monday')) {
        return {
          status: 200,
          body: {
            monday: butlerMonday,
            drk: null,
            match: null,
            errors: [],
          },
        }
      }
      return {
        status: 200,
        body: {
          monday: butlerMonday,
          drk: butlerDrk,
          match: {
            status: 'mismatch',
            fields: [
              {
                field: 'provider',
                monday: 'Jane Provider',
                drk: 'Other Provider',
                status: 'mismatch',
              },
            ],
          },
          errors: [],
        },
      }
    })
    window.history.pushState({}, '', '/patient/butler-alva')
    render(<App />)

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /BUTLER, ALVA/i }),
      ).toBeInTheDocument()
    })
    expect(screen.queryByLabelText(/Search patients/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: /Primary/i })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Overview$/i })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /^Monday$/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/^Blocker$/i)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Confirm step/i })).not.toBeInTheDocument()
    expect(screen.queryByText(/Extracted details/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Records$/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/^Timeline$/i)).not.toBeInTheDocument()
    expect(screen.getByLabelText(/People/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Open attachment/i })).not.toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByText(/Sent by /i)).toBeInTheDocument()
    })
    await waitFor(() => {
      expect(screen.getByText(/Chart details/i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Diagnoses/i })).toBeInTheDocument()
    })
  })

  it('opens the same profile from /:patientId', async () => {
    mockPatientApi(() => ({
      status: 200,
      body: {
        monday: { ...butlerMonday, name: 'Frank Owens' },
        drk: null,
        match: null,
        errors: [],
      },
    }))
    window.history.pushState({}, '', '/frank-owens')
    render(<App />)

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /Frank Owens/i }),
      ).toBeInTheDocument()
    })
    expect(screen.getByLabelText(/Monday ops/i)).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByLabelText(/DRK chart/i)).toBeInTheDocument()
    })
  })

  it('shows live Monday and DRK together at /alva-butler', async () => {
    mockPatientApi((url) => {
      if (url.includes('source=monday')) {
        return {
          status: 200,
          body: { monday: butlerMonday, drk: null, match: null, errors: [] },
        }
      }
      return {
        status: 200,
        body: {
          monday: butlerMonday,
          drk: butlerDrk,
          match: {
            status: 'mismatch',
            fields: [
              {
                field: 'provider',
                monday: 'Jane Provider',
                drk: 'Other Provider',
                status: 'mismatch',
              },
            ],
          },
          errors: [],
        },
      }
    })
    window.history.pushState({}, '', '/alva-butler')
    render(<App />)

    await waitFor(() => {
      expect(screen.getByLabelText(/Monday ops/i)).toBeInTheDocument()
    })
    expect(screen.getByLabelText(/Monday ops/i)).toHaveTextContent(/Scheduled/)
    expect(screen.getByLabelText(/People/i)).toHaveTextContent(/Jane Provider/)
    expect(screen.getByLabelText(/DRK chart/i)).toHaveTextContent(/MRN-77/)
    expect(screen.getByText(/Chart details/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Diagnoses/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Medications/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Clinical notes/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Insurance policies/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Encounters/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Documents/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Billing/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Pipeline/i })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Open attachment/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: /Primary/i })).not.toBeInTheDocument()

    const workflow = screen.getByRole('region', { name: /Demo workflow/i })
    expect(workflow).toHaveTextContent(/Referral intake/)
    expect(workflow).toHaveTextContent(/Extract and verify/)
    expect(
      within(workflow).getByRole('navigation', { name: /Automation steps/i }),
    ).toBeInTheDocument()
    expect(
      within(workflow).getByRole('list', { name: /Step updates/i }),
    ).toBeInTheDocument()
    expect(
      within(workflow).getByRole('article', {
        name: /Awaiting partner confirmation · BUTLER, ALVA · Needs confirmation/i,
      }),
    ).toBeInTheDocument()

    const user = userEvent.setup()
    await user.click(
      within(workflow).getByRole('button', {
        name: /Extract and verify referral details/i,
      }),
    )
    const stepDetail = within(workflow).getByRole('article', {
      name: /Details extracted · 6 of 7 fields complete/i,
    })
    expect(stepDetail).toHaveTextContent(/BUTLER, ALVA/i)
    expect(stepDetail).toHaveTextContent(/Threshold/i)
    expect(
      within(workflow).queryByRole('button', { name: /Open attachment/i }),
    ).not.toBeInTheDocument()
    expect(
      within(workflow).queryByLabelText(/Search patients/i),
    ).not.toBeInTheDocument()

    await user.click(within(workflow).getByRole('button', { name: /3 Handoff/i }))
    expect(workflow).toHaveTextContent(/No demo updates for this step yet/i)
    expect(workflow).toHaveTextContent(/Referral intake · Referral partner contacted/)
  })

  it('shows not found for an unknown patient URL', async () => {
    mockPatientApi(() => ({
      status: 404,
      body: { monday: null, drk: null, match: null, error: 'not_found' },
    }))
    window.history.pushState({}, '', '/patient/not-a-real-patient')
    render(<App />)

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: /Patient not found/i }),
      ).toBeInTheDocument()
    })
    expect(screen.queryByRole('region', { name: /Demo workflow/i })).not.toBeInTheDocument()
  })
})
