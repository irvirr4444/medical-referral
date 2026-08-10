import { render, screen, waitFor, within } from '@testing-library/react'
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

    await user.click(
      screen.getByRole('button', { name: /Open profile for Alva Butler/i }),
    )
    expect(
      screen.queryByRole('dialog', { name: /New referrals/i }),
    ).not.toBeInTheDocument()
    expect(
      screen.queryByRole('navigation', { name: /Primary/i }),
    ).not.toBeInTheDocument()
    const profilePage = screen.getByRole('main', { name: /Alva Butler/i })
    expect(profilePage).toBeInTheDocument()
    expect(window.location.pathname).toBe('/patients/butler-alva')
    expect(profilePage).toHaveTextContent('BUTLER, ALVA')
    expect(profilePage).toHaveTextContent('(260) 438-4646')
    expect(profilePage).toHaveTextContent('MEDICARE PART B')
    expect(profilePage).toHaveTextContent(
      /No requested services documented in the canonical referral/i,
    )
    expect(profilePage).toHaveTextContent(/Not in Monday.com yet/i)
    expect(profilePage).toHaveTextContent(/Not in DRK yet/i)
    expect(profilePage).toHaveTextContent(/1\. Referral intake/i)
    expect(profilePage).toHaveTextContent(
      /Step 12 of 13: Interpret the reviewer reply/i,
    )
    expect(
      screen.queryByRole('button', { name: /Back to list/i }),
    ).not.toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /Open clinical summary details/i }),
    )
    const clinicalDialog = screen.getByRole('dialog', {
      name: /Clinical summary/i,
    })
    expect(clinicalDialog).toHaveTextContent(/cardiopulmonary/i)
    expect(clinicalDialog).toHaveTextContent(/Clinical notes/i)
    await user.click(screen.getByRole('button', { name: /Close details/i }))
    expect(
      screen.queryByRole('dialog', { name: /Clinical summary/i }),
    ).not.toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /Open diagnosis details/i }),
    )
    const diagnosesDialog = screen.getByRole('dialog', {
      name: /^Diagnosis$/i,
    })
    expect(diagnosesDialog).toHaveTextContent('I25.10')
    expect(diagnosesDialog).toHaveTextContent(/12 documented diagnoses/i)
    expect(diagnosesDialog).toHaveTextContent(/Primary/i)
    await user.click(screen.getByRole('button', { name: /Close details/i }))

    await user.click(
      screen.getByRole('button', { name: /Open insurance details/i }),
    )
    const insuranceDialog = screen.getByRole('dialog', {
      name: /^Insurance$/i,
    })
    expect(insuranceDialog).toHaveTextContent('MEDICARE PART B')
    expect(insuranceDialog).toHaveTextContent(/2 insurance records/i)
    await user.click(screen.getByRole('button', { name: /Close details/i }))

    window.history.back()
    await waitFor(() => {
      expect(window.location.pathname).toBe('/')
    })
    expect(
      screen.getByRole('navigation', { name: /Primary/i }),
    ).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: /View patients for New referrals/i }),
    )
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
})
